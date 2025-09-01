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

# Session helpers
def get_current_images():
    return session.get('current_images', [])

def set_current_images(images):
    session['current_images'] = images

def get_current_index():
    return session.get('current_index', 0)

def set_current_index(index):
    session['current_index'] = index

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
        
        processor = BatchImageProcessor(upload_dir, api_key)
        results = processor.process_directory(upload_dir, output_dir)
        
        return jsonify({
            'success': f'Processed {len(results)} images',
            'results': len(results)
        })
        
    except Exception as e:
        return jsonify({'error': f'Batch processing failed: {str(e)}'}), 500

@app.route('/')
def index():
    set_current_images(get_image_files())
    set_current_index(0)
    return render_template('index.html')

@app.route('/get_image_info')
def get_image_info():
    current_images = get_current_images()
    current_index = get_current_index()
    
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
    current_images = get_current_images()
    current_index = get_current_index()
    
    direction = request.json.get('direction')
    
    if direction == 'next' and current_index < len(current_images) - 1:
        set_current_index(current_index + 1)
    elif direction == 'prev' and current_index > 0:
        set_current_index(current_index - 1)
    
    return get_image_info()

@app.route('/convert_text', methods=['POST'])
def convert_text():
    current_images = get_current_images()
    current_index = get_current_index()
    
    if not current_images or current_index >= len(current_images):
        return jsonify({'error': 'No image selected'})
    
    # Get API key and model from request
    api_key = request.json.get('api_key') if request.json else None
    model = request.json.get('model', 'meta-llama/llama-4-scout-17b-16e-instruct') if request.json else 'meta-llama/llama-4-scout-17b-16e-instruct'
    if not api_key:
        return jsonify({'error': 'API key required'})
    
    try:
        from batch_processor import BatchImageProcessor
        
        if current_index >= len(current_images):
            return jsonify({'error': 'Invalid image index'})
        
        image_path = current_images[current_index]
        
        # Use BatchImageProcessor for consistent logic
        processor = BatchImageProcessor(os.path.dirname(image_path), api_key)
        converted_text = processor.convert_image_to_text(image_path, model)
        
        if converted_text.startswith('Error processing'):
            return jsonify({'error': converted_text})
        
        # Extract student info using centralized logic
        student_name, school_name, poem_title, poem_theme, poem_language = processor.extract_student_info(converted_text)
        
        # Extract confidence score
        lines = converted_text.split('\n')
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
        
    except Exception as e:
        error_msg = str(e)
        if 'rate limit' in error_msg.lower():
            return jsonify({'error': 'API rate limit exceeded. Please wait and try again.'})
        elif 'timeout' in error_msg.lower():
            return jsonify({'error': 'API request timed out. Please try again.'})
        elif 'authentication' in error_msg.lower():
            return jsonify({'error': 'API authentication failed. Check your API key.'})
        else:
            return jsonify({'error': f'Error: {error_msg}'})

@app.route('/upload_image', methods=['POST'])
def upload_image():
    
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
            set_current_images(current_images)
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
                set_current_index(current_images.index(uploaded_file))
            except ValueError:
                set_current_index(0)
            
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
        # Create meaningful filename from student info (centralized logic)
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
        
        fallback_name = os.path.splitext(filename)[0]
        base_name = '_'.join(parts) if parts else fallback_name
        
        output_dir = os.environ.get('OUTPUT_DIRECTORY', os.getcwd())
        save_path = os.path.join(output_dir, f"{base_name}.txt")
        
        # Validate path to prevent directory traversal
        abs_save_path = os.path.abspath(save_path)
        abs_output_dir = os.path.abspath(output_dir)
        if not abs_save_path.startswith(abs_output_dir):
            return jsonify({'error': 'Invalid file path: Path traversal detected'})
        
        # Create backup if file exists
        if os.path.exists(save_path):
            backup_path = f"{save_path}.backup"
            shutil.copy2(save_path, backup_path)
        
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        # Verify file was written correctly
        if not os.path.exists(save_path) or os.path.getsize(save_path) == 0:
            return jsonify({'error': 'File save verification failed'})
        
        # Move processed image from uploads to converted_images folder
        current_images = get_current_images()
        current_index = get_current_index()
        if current_images and current_index < len(current_images):
            current_image_path = current_images[current_index]
            upload_dir = os.environ.get('UPLOAD_DIRECTORY', os.getcwd())
            converted_dir = os.environ.get('CONVERTED_IMAGES_DIRECTORY', os.path.join(os.path.dirname(upload_dir), 'converted_images'))
            os.makedirs(converted_dir, exist_ok=True)
            
            image_filename = os.path.basename(current_image_path)
            new_image_path = os.path.join(converted_dir, image_filename)
            
            try:
                shutil.move(current_image_path, new_image_path)
                # Update session with new image list
                updated_images = get_image_files()
                set_current_images(updated_images)
                # Adjust index if needed
                if current_index >= len(updated_images) and updated_images:
                    set_current_index(len(updated_images) - 1)
                elif not updated_images:
                    set_current_index(0)
            except Exception as move_error:
                print(f"Warning: Could not move image: {move_error}")
        
        return jsonify({'success': f'Text saved to {base_name}.txt', 'refresh': True})
        
    except PermissionError:
        return jsonify({'error': 'Permission denied. Cannot write to directory.'})
    except OSError as e:
        return jsonify({'error': f'File system error: {str(e)}'})
    except Exception as e:
        return jsonify({'error': f'Save failed: {str(e)}'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)