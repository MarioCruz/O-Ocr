from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
import base64
import os
from groq import Groq
import json
from datetime import datetime
from werkzeug.utils import secure_filename
from pdf2image import convert_from_path
import shutil
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')

# Simple authentication decorator
def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

# Initialize Groq client
client = None

# Global variables
current_images = []
current_index = 0

def extract_images_from_pdf(pdf_path):
    """Extract images from PDF and save them"""
    try:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        if os.path.getsize(pdf_path) == 0:
            raise ValueError("PDF file is empty")
        
        pages = convert_from_path(pdf_path, dpi=200)
        if not pages:
            raise ValueError("No pages found in PDF")
        
        extracted_files = []
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        
        for i, page in enumerate(pages):
            try:
                image_path = f"{os.environ.get('UPLOAD_DIRECTORY', os.getcwd())}/{base_name}_page_{i+1}.png"
                page.save(image_path, 'PNG')
                extracted_files.append(image_path)
            except Exception as page_error:
                print(f"Error saving page {i+1}: {page_error}")
                continue
        
        return extracted_files
    except Exception as e:
        print(f"Error extracting PDF {pdf_path}: {e}")
        return []

def get_image_files():
    """Get all image files from the directory"""
    directory = os.environ.get('UPLOAD_DIRECTORY', os.getcwd())
    supported_formats = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff')
    
    try:
        if not os.path.exists(directory):
            os.makedirs(directory)
            return []
        
        image_files = []
        for file in os.listdir(directory):
            file_path = os.path.join(directory, file)
            
            try:
                if file.lower().endswith(supported_formats):
                    if os.path.getsize(file_path) > 0:
                        image_files.append(file_path)
                elif file.lower().endswith('.pdf'):
                    extracted = extract_images_from_pdf(file_path)
                    image_files.extend(extracted)
            except (OSError, PermissionError) as e:
                print(f"Error accessing file {file}: {e}")
                continue
        
        return image_files
    except Exception as e:
        print(f"Error reading directory: {e}")
        return []

def image_to_base64(image_path):
    """Convert image to base64 string"""
    try:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        if os.path.getsize(image_path) == 0:
            raise ValueError("Image file is empty")
        
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        raise Exception(f"Error converting image to base64: {e}")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        # Simple password check - use proper authentication in production
        if password == os.environ.get('APP_PASSWORD', 'admin123'):
            session['authenticated'] = True
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('login'))

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200

@app.route('/get_models', methods=['POST'])
def get_models():
    api_key = request.json.get('api_key') if request.json else None
    if not api_key:
        return jsonify({'error': 'API key required'})
    
    try:
        temp_client = Groq(api_key=api_key)
        print("Fetching available models...")
        models = temp_client.models.list()
        print(f"Models response type: {type(models)}")
        print(f"Models response: {models}")
        
        # Try different ways to access models
        if hasattr(models, 'data'):
            model_list = models.data
            print(f"Using models.data - Found {len(model_list)} models")
        else:
            model_list = models
            print(f"Using models directly - Found {len(model_list)} models")
            
        all_models = [model.id for model in model_list]
        print(f"All models: {all_models}")
        # Include models that can handle vision tasks
        vision_keywords = ['vision', 'scout', 'llama-4', 'llama-3.3', 'llama3-70b', 'compound']
        vision_models = [model.id for model in model_list if any(keyword in model.id.lower() for keyword in vision_keywords)]
        print(f"Vision models: {vision_models}")
        return jsonify({'models': vision_models})
    except Exception as e:
        print(f"Error fetching models: {str(e)}")
        return jsonify({'error': f'Failed to fetch models: {str(e)}'})

@app.route('/batch_process', methods=['POST'])
def batch_process():
    # Get API key from request
    api_key = request.json.get('api_key') if request.json else None
    if not api_key:
        return jsonify({'error': 'API key required for batch processing'})
    
    try:
        from batch_processor import BatchImageProcessor
        
        upload_dir = os.environ.get('UPLOAD_DIRECTORY', os.getcwd())
        output_dir = os.environ.get('OUTPUT_DIRECTORY', os.getcwd())
        
        # Set API key in environment for batch processor
        os.environ['GROQ_API_KEY'] = api_key
        
        processor = BatchImageProcessor(upload_dir)
        results = processor.process_directory(upload_dir, output_dir)
        
        return jsonify({
            'success': f'Processed {len(results)} images',
            'results': len(results)
        })
        
    except Exception as e:
        return jsonify({'error': f'Batch processing failed: {str(e)}'}), 500

@app.route('/')
def index():
    global current_images, current_index
    current_images = get_image_files()
    current_index = 0
    return render_template('index.html')

@app.route('/get_image_info')
def get_image_info():
    global current_images, current_index
    
    if not current_images:
        return jsonify({'error': 'No images found'})
    
    if 0 <= current_index < len(current_images):
        image_path = current_images[current_index]
        image_base64 = image_to_base64(image_path)
        
        return jsonify({
            'image_base64': image_base64,
            'filename': os.path.basename(image_path),
            'index': current_index + 1,
            'total': len(current_images)
        })
    
    return jsonify({'error': 'Invalid image index'})

@app.route('/navigate', methods=['POST'])
def navigate():
    global current_index, current_images
    
    direction = request.json.get('direction')
    
    if direction == 'next' and current_index < len(current_images) - 1:
        current_index += 1
    elif direction == 'prev' and current_index > 0:
        current_index -= 1
    
    return get_image_info()

@app.route('/convert_text', methods=['POST'])
def convert_text():
    global current_images, current_index
    
    if not current_images or current_index >= len(current_images):
        return jsonify({'error': 'No image selected'})
    
    # Get API key and model from request
    api_key = request.json.get('api_key') if request.json else None
    model = request.json.get('model', 'meta-llama/llama-4-scout-17b-16e-instruct') if request.json else 'meta-llama/llama-4-scout-17b-16e-instruct'
    if not api_key:
        return jsonify({'error': 'API key required'})
    
    try:
        # Initialize client with provided API key
        temp_client = Groq(api_key=api_key)
        if current_index >= len(current_images):
            return jsonify({'error': 'Invalid image index'})
        
        image_path = current_images[current_index]
        
        try:
            base64_image = image_to_base64(image_path)
        except Exception as img_error:
            return jsonify({'error': f'Image processing failed: {str(img_error)}'})
        
        try:
            print(f"Making API call with model: {model}")
            chat_completion = temp_client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Transcribe everything in this image including student name, school name at the top, and the complete poem below. Preserve exact formatting, line breaks, and punctuation. Use [?] for unclear words. At the end, add exactly these 4 lines with no additional text:\nPOEM_TITLE: [actual title]\nPOEM_THEME: [one word: family, nature, friendship, school, emotions, seasons, or miami]\nPOEM_LANGUAGE: [language name]\nConfidence: X/10"
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                model=model,
                temperature=0.1,
                max_tokens=1000,
                timeout=30
            )
            
            if not chat_completion.choices:
                return jsonify({'error': 'No response from AI model'})
            
            converted_text = chat_completion.choices[0].message.content
            print(f"API Response length: {len(converted_text)}")
            print(f"API Response preview: {converted_text[:200]}...")
            if not converted_text:
                return jsonify({'error': 'Empty response from AI model'})
            
            # Extract student name, school, poem title, and theme for better filename
            lines = converted_text.split('\n')
            student_name = ""
            school_name = ""
            poem_title = ""
            poem_theme = ""
            
            # Look for student name and school in first few lines
            for line in lines[:5]:
                line = line.strip()
                if 'School:' in line or 'school' in line.lower():
                    school_name = line.split(':')[-1].strip() if ':' in line else line
                    school_name = school_name.replace('School', '').replace('school', '').strip()
                elif line and not line.startswith('Grade'):
                    if 'Name:' in line:
                        student_name = line.split('Name:')[-1].strip()
                    elif not student_name and len(line.split()) <= 4:  # Likely a name
                        student_name = line
            
            # Extract poem title, theme, and language from AI response
            poem_language = ""
            for line in lines:
                if line.startswith('POEM_TITLE:'):
                    poem_title = line.replace('POEM_TITLE:', '').strip()
                elif line.startswith('POEM_THEME:'):
                    poem_theme = line.replace('POEM_THEME:', '').strip()
                elif line.startswith('POEM_LANGUAGE:'):
                    poem_language = line.replace('POEM_LANGUAGE:', '').strip()
            

            
            # Extract confidence score
            confidence_score = ""
            for line in lines:
                if line.startswith('Confidence:'):
                    confidence_score = line.strip()
                    break
            
            # Remove only confidence from text for saving
            clean_text = '\n'.join([line for line in lines 
                                   if not line.startswith('Confidence:')])
            
            return jsonify({
                'text': clean_text,
                'student_name': student_name,
                'school_name': school_name,
                'poem_title': poem_title,
                'poem_theme': poem_theme,
                'poem_language': poem_language,
                'confidence_score': confidence_score
            })
            
        except Exception as api_error:
            error_msg = str(api_error)
            if 'rate limit' in error_msg.lower():
                return jsonify({'error': 'API rate limit exceeded. Please wait and try again.'})
            elif 'timeout' in error_msg.lower():
                return jsonify({'error': 'API request timed out. Please try again.'})
            elif 'authentication' in error_msg.lower():
                return jsonify({'error': 'API authentication failed. Check your API key.'})
            else:
                return jsonify({'error': f'API error: {error_msg}'})
        
    except Exception as e:
        return jsonify({'error': f'Unexpected error: {str(e)}'})

@app.route('/upload_image', methods=['POST'])
def upload_image():
    global current_images, current_index
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file selected'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'})
    
    if file:
        try:
            filename = secure_filename(file.filename)
            if not filename:
                return jsonify({'error': 'Invalid filename'})
            
            upload_path = f"{os.environ.get('UPLOAD_DIRECTORY', os.getcwd())}/{filename}"
            
            # Check file size efficiently using Content-Length header
            file_size = request.content_length
            if file_size is None:
                # Fallback to file size check if Content-Length not available
                file.seek(0, 2)
                file_size = file.tell()
                file.seek(0)
            
            if file_size > 50 * 1024 * 1024:
                return jsonify({'error': 'File too large (max 50MB)'})
            
            if file_size == 0:
                return jsonify({'error': 'File is empty'})
            
            file.save(upload_path)
            
            # If PDF, extract images
            if filename.lower().endswith('.pdf'):
                extracted = extract_images_from_pdf(upload_path)
                if not extracted:
                    return jsonify({'error': 'Failed to extract images from PDF'})
            
            # Refresh image list and find the uploaded file
            current_images = get_image_files()
            if not current_images:
                return jsonify({'error': 'No valid images found after upload'})
            
            # Find the uploaded file in the list
            uploaded_file = upload_path
            if filename.lower().endswith('.pdf'):
                # For PDFs, show the first extracted page
                base_name = os.path.splitext(filename)[0]
                uploaded_file = f"{os.environ.get('UPLOAD_DIRECTORY', os.getcwd())}/{base_name}_page_1.png"
            
            # Set current_index to the uploaded file
            try:
                current_index = current_images.index(uploaded_file)
            except ValueError:
                current_index = 0
            
            return get_image_info()
            
        except Exception as e:
            return jsonify({'error': f'Upload failed: {str(e)}'})

@app.route('/save_text', methods=['POST'])
def save_text():
    text = request.json.get('text', '')
    student_name = request.json.get('student_name', '')
    school_name = request.json.get('school_name', '')
    poem_title = request.json.get('poem_title', '')
    poem_theme = request.json.get('poem_theme', '')
    poem_language = request.json.get('poem_language', '')
    filename = request.json.get('filename', 'converted_text.txt')
    
    if not text.strip():
        return jsonify({'error': 'No text to save'})
    
    try:
        # Create meaningful filename from student name, school, poem title, and theme
        parts = []
        if school_name:
            clean_school = ''.join(c for c in school_name if c.isalnum() or c in ' -').strip().replace(' ', '_')
            parts.append(clean_school)
        if student_name:
            clean_student = ''.join(c for c in student_name if c.isalnum() or c in ' -').strip().replace(' ', '_')
            parts.append(clean_student)
        if poem_title:
            clean_poem = ''.join(c for c in poem_title if c.isalnum() or c in ' -').strip().replace(' ', '_')
            parts.append(clean_poem)
        if poem_theme:
            parts.append(poem_theme)
        
        if parts:
            base_name = '_'.join(parts)
        else:
            base_name = os.path.splitext(filename)[0]
        
        save_path = f"{os.environ.get('OUTPUT_DIRECTORY', os.getcwd())}/{base_name}.txt"
        
        # Create backup if file exists
        if os.path.exists(save_path):
            backup_path = f"{save_path}.backup"
            shutil.copy2(save_path, backup_path)
        
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        # Verify file was written correctly
        if not os.path.exists(save_path) or os.path.getsize(save_path) == 0:
            return jsonify({'error': 'File save verification failed'})
        
        return jsonify({'success': f'Text saved to {base_name}.txt'})
        
    except PermissionError:
        return jsonify({'error': 'Permission denied. Cannot write to directory.'})
    except OSError as e:
        return jsonify({'error': f'File system error: {str(e)}'})
    except Exception as e:
        return jsonify({'error': f'Save failed: {str(e)}'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)