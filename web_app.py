from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
import base64
import os
from utils import _filename_clean_pattern
from groq import Groq
import json
from datetime import datetime
from werkzeug.utils import secure_filename
from pdf2image import convert_from_path
import shutil
from functools import wraps, lru_cache
from PIL import Image
import pillow_heif
import re
import logging
import io
from student_info import StudentInfo
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB limit
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 300  # 5 minutes cache

# Simple authentication decorator
def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


# Session management
class SessionManager:
    @staticmethod
    def get_current_images():
        return session.get('current_images', [])
    
    @staticmethod
    def set_current_images(images):
        session['current_images'] = images
    
    @staticmethod
    def get_current_index():
        return session.get('current_index', 0)
    
    @staticmethod
    def set_current_index(index):
        session['current_index'] = index

def extract_images_from_pdf(pdf_path):
    """Extract images from PDF and save them, then move PDF to processed directory"""
    try:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        if os.path.getsize(pdf_path) == 0:
            raise ValueError("PDF file is empty")
        
        pages = convert_from_path(pdf_path, dpi=150)
        if not pages:
            raise ValueError("No pages found in PDF")
        
        extracted_files = []
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        upload_dir = os.environ.get('UPLOAD_DIRECTORY', os.getcwd())
        
        for i, page in enumerate(pages):
            try:
                image_path = os.path.join(upload_dir, f"{base_name}_page_{i+1}.png")
                page.save(image_path, 'PNG')
                extracted_files.append(image_path)
            except (IOError, OSError) as page_error:
                logging.error(f"Error saving page {i+1}: {page_error}")
                continue
        
        # Move PDF to processed directory after successful extraction
        if extracted_files:
            try:
                processed_dir = os.environ.get('CONVERTED_IMAGES_DIRECTORY', '/app/O-Ocr/converted_images')
                os.makedirs(processed_dir, exist_ok=True)
                
                pdf_filename = os.path.basename(pdf_path)
                processed_pdf_path = os.path.join(processed_dir, pdf_filename)
                
                # Handle duplicate PDF names
                if os.path.exists(processed_pdf_path):
                    base_pdf_name = os.path.splitext(pdf_filename)[0]
                    counter = 1
                    while os.path.exists(processed_pdf_path):
                        processed_pdf_path = os.path.join(processed_dir, f"{base_pdf_name}_{counter}.pdf")
                        counter += 1
                
                shutil.move(pdf_path, processed_pdf_path)
                logging.info(f"PDF moved from {pdf_path} to {processed_pdf_path}")
                
            except Exception as move_error:
                logging.error(f"Could not move PDF {pdf_path}: {move_error}")
                # Don't fail the entire operation if PDF move fails
        
        return extracted_files
    except (FileNotFoundError, ValueError, IOError, OSError) as e:
        logging.error(f"Error extracting PDF {pdf_path}: {e}")
        return []

def get_image_files():
    """Get all image files from the directory"""
    directory = os.environ.get('UPLOAD_DIRECTORY', os.getcwd())
    supported_formats = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.heic', '.heif')
    
    try:
        if not os.path.exists(directory):
            logging.info(f"Creating upload directory: {directory}")
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
                logging.error(f"Cannot access file {file}: {e}")
                logging.error(f"Check Docker file sharing permissions for: {directory}")
                continue
        
        return image_files
    except PermissionError as e:
        logging.error(f"Permission denied accessing directory {directory}: {e}")
        logging.error("Docker file sharing may not be configured. Add ~/O-Ocr to Docker Desktop > Settings > Resources > File Sharing")
        return []
    except Exception as e:
        logging.error(f"Cannot read directory {directory}: {e}")
        return []

@lru_cache(maxsize=32)  # Cache up to 32 images
def image_to_base64(image_path):
    """Convert image to base64 string"""
    try:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")

        if os.path.getsize(image_path) == 0:
            raise ValueError("Image file is empty")

        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except (IOError, OSError) as e:
        raise IOError(f"Error converting image to base64: {e}") from e

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
        logging.info("Fetching available models...")
        models = temp_client.models.list()
        logging.debug(f"Models response type: {type(models)}")
        logging.debug(f"Models response: {models}")
        
        # Try different ways to access models
        if hasattr(models, 'data'):
            model_list = models.data
            print(f"Using models.data - Found {len(model_list)} models")
        else:
            model_list = models
            logging.info(f"Using models directly - Found {len(model_list)} models")
            
        all_models = [model.id for model in model_list]
        logging.info(f"All models: {all_models}")
        # Include models that can handle vision tasks
        vision_keywords = ['vision', 'scout', 'llama-4', 'llama-3.3', 'llama3-70b', 'compound']
        vision_models = [model.id for model in model_list if any(keyword in model.id.lower() for keyword in vision_keywords)]
        print(f"Vision models: {vision_models}")
        
        # Add processing modes
        processing_modes = [
            {'value': 'poem', 'label': 'Student Poems (SUN Room)'},
            {'value': 'freeform', 'label': 'Free Form OCR'},
            {'value': 'zip_ode_explain', 'label': 'Zipcode (Zip Ode)'},
            {'value': 'custom_poem', 'label': 'Custom Poem'},
            {'value': 'postcard_poem', 'label': 'Post Card Poem'},
            {'value': 'worksheet_poem', 'label': 'Worksheet Poem'},
            {'value': 'survey_form', 'label': 'Non-Poem Survey Form'}
        ]
        
        return jsonify({'models': vision_models, 'processing_modes': processing_modes})
    except Exception as e:
        logging.error(f"Error fetching models: {str(e)}")
        return jsonify({'error': f'Failed to fetch models: {str(e)}'})

@app.route('/get_custom_settings', methods=['GET'])
def get_custom_settings():
    try:
        with open('custom_poem_settings.json', 'r') as f:
            data = json.load(f)
        return jsonify(data['custom_poem'])
    except (FileNotFoundError, KeyError):
        return jsonify({
            "name": "Custom Poem",
            "description": "User-defined poem structure and content",
            "structure": "Free verse with custom requirements",
            "document_contains": ["Student name", "School name", "Poem text"]
        })

@app.route('/save_custom_settings', methods=['POST'])
def save_custom_settings():
    try:
        settings = request.json
        settings['prompt_template'] = (
            "Transcribe everything in this image including {document_contains}. "
            "Preserve exact formatting, line breaks, and punctuation. "
            "Use [?] for unclear words. At the end, add exactly these lines:\n"
            "POEM_TITLE: [actual title]\n"
            "POEM_THEME: [theme]\n"
            "POEM_LANGUAGE: [language]\n"
            "CUSTOM_STRUCTURE: {structure}\n"
            "Confidence: X/10"
        )
        
        data = {'custom_poem': settings}
        with open('custom_poem_settings.json', 'w') as f:
            json.dump(data, f, indent=2)
        
        return jsonify({'success': 'Settings saved successfully'})
    except Exception as e:
        return jsonify({'error': f'Failed to save settings: {str(e)}'}), 500

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
    # Ensure required directories exist
    upload_dir = os.environ.get('UPLOAD_DIRECTORY', os.getcwd())
    converted_dir = os.environ.get('CONVERTED_IMAGES_DIRECTORY', os.getcwd())
    
    for directory in [upload_dir, converted_dir]:
        try:
            os.makedirs(directory, exist_ok=True)
            logging.info(f"Created directory: {directory}")
        except Exception as e:
            logging.warning(f"Could not create directory {directory}: {e}")
    
    # Initialize session with current images
    current_images = get_image_files()
    logging.info(f"Initializing session with {len(current_images)} images")
    SessionManager.set_current_images(current_images)
    SessionManager.set_current_index(0)
    
    return render_template('index.html')



@app.route('/get_image_info')
def get_image_info():
    current_images = SessionManager.get_current_images()
    current_index = SessionManager.get_current_index()
    
    # If no images in session, refresh from disk
    if not current_images:
        logging.info("No images in session, refreshing from disk")
        fresh_images = get_image_files()
        SessionManager.set_current_images(fresh_images)
        current_images = fresh_images
        current_index = 0
        SessionManager.set_current_index(current_index)
    
    if not current_images:
        return jsonify({'error': 'No images found'})
    
    # Validate current index
    if current_index >= len(current_images):
        current_index = 0
        SessionManager.set_current_index(current_index)
    
    if 0 <= current_index < len(current_images):
        image_path = current_images[current_index]
        
        # Check if file exists, if not refresh the list
        if not os.path.exists(image_path):
            logging.warning(f"Image file no longer exists: {image_path}, refreshing list")
            fresh_images = get_image_files()
            SessionManager.set_current_images(fresh_images)
            
            if not fresh_images:
                return jsonify({'error': 'No images found'})
            
            # Reset to first image
            current_index = 0
            SessionManager.set_current_index(current_index)
            image_path = fresh_images[0]
        
        try:
            image_base64 = image_to_base64(image_path)
            return jsonify({
                'image_base64': image_base64,
                'filename': os.path.basename(image_path),
                'index': current_index + 1,
                'total': len(current_images)
            })
        except Exception as e:
            logging.error(f"Error loading image {image_path}: {e}")
            return jsonify({'error': f'Error loading image: {str(e)}'})
    
    return jsonify({'error': 'Invalid image index'})

@app.route('/navigate', methods=['POST'])
def navigate():
    current_images = SessionManager.get_current_images()
    current_index = SessionManager.get_current_index()
    
    direction = request.json.get('direction')
    
    if direction == 'next' and current_index < len(current_images) - 1:
        SessionManager.set_current_index(current_index + 1)
    elif direction == 'prev' and current_index > 0:
        SessionManager.set_current_index(current_index - 1)
    
    return get_image_info()

@app.route('/convert_text', methods=['POST'])
def convert_text():
    current_images = SessionManager.get_current_images()
    current_index = SessionManager.get_current_index()
    
    if not current_images or current_index >= len(current_images):
        return jsonify({'error': 'No image selected'})
    
    # Get API key, model, and processing mode from request
    req_json = request.json or {}
    api_key = req_json.get('api_key')
    model = req_json.get('model', 'meta-llama/llama-4-scout-17b-16e-instruct')
    processing_mode = req_json.get('processing_mode', 'poem')
    if not api_key:
        return jsonify({'error': 'API key required'})
    
    try:
        from batch_processor import BatchImageProcessor
        
        image_path = current_images[current_index]
        
        # Use BatchImageProcessor for consistent logic
        processor = BatchImageProcessor(os.path.dirname(image_path), api_key)
        converted_text = processor.convert_image_to_text(image_path, model, processing_mode)
        
        if converted_text.startswith('Error processing'):
            return jsonify({'error': converted_text})
        
        # Extract student info using appropriate logic based on processing mode
        if processing_mode == "zip_ode_explain":
            parsed = processor.parse_zip_ode_response(converted_text)
            info = StudentInfo(
                student_name=parsed["student_name"],
                school_name=parsed["school_name"],
                poem_title=parsed["poem_title"],
                poem_theme=parsed["poem_theme"],
                poem_language=parsed["poem_language"]
            )
        else:
            info = processor.extract_student_info_legacy(converted_text)
        
        # Extract confidence score and clean text in single pass
        lines = converted_text.split('\n')
        confidence_score = ""
        clean_lines = []
        
        for line in lines:
            if line.startswith('Confidence:') or line.strip().startswith('(Confidence:'):
                confidence_score = line.strip()
            else:
                clean_lines.append(line)
        
        clean_text = '\n'.join(clean_lines)
        
        return jsonify({
            'text': clean_text,
            'student_name': info.student_name,
            'school_name': info.school_name,
            'poem_title': info.poem_title,
            'poem_theme': info.poem_theme,
            'poem_language': info.poem_language,
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
                return jsonify({'error': 'The filename contains invalid characters. Please use only letters, numbers, spaces, and hyphens.'})
            
            upload_dir = os.environ.get('UPLOAD_DIRECTORY', os.getcwd())
            try:
                os.makedirs(upload_dir, exist_ok=True)
            except PermissionError as e:
                logging.error(f"Cannot create upload directory {upload_dir}: {e}")
                logging.error("Docker file sharing may not be configured. Add ~/O-Ocr to Docker Desktop > Settings > Resources > File Sharing")
                return jsonify({'error': 'Upload directory not accessible. Check Docker file sharing settings.'})
            upload_path = os.path.join(upload_dir, filename)
            
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
            
            # Convert HEIC/HEIF to JPEG during upload for display compatibility
            if filename.lower().endswith(('.heic', '.heif')):
                try:
                    pillow_heif.register_heif_opener()
                    with Image.open(file) as image:
                        if image.mode != 'RGB':
                            image = image.convert('RGB')
                        # Change filename to .jpg
                        base_name = os.path.splitext(filename)[0]
                        filename = f"{base_name}.jpg"
                        upload_path = os.path.join(upload_dir, filename)
                        image.save(upload_path, 'JPEG', quality=95)
                except Exception as e:
                    return jsonify({'error': f'HEIC conversion failed: {str(e)}'})
            else:
                file.save(upload_path)

            # Resize image (but not for PDFs)
            if not filename.lower().endswith('.pdf'):
                try:
                    with Image.open(upload_path) as img:
                        max_size = (1024, 1024)
                        img.thumbnail(max_size)
                        img.save(upload_path, 'JPEG', quality=95)
                except Exception as e:
                    logging.error(f"Error resizing image: {e}")

            # If PDF, extract images
            if filename.lower().endswith('.pdf'):
                extracted = extract_images_from_pdf(upload_path)
                if not extracted:
                    return jsonify({'error': 'Failed to extract images from PDF'})

            # Refresh image list and find the uploaded file
            current_images = get_image_files()
            SessionManager.set_current_images(current_images)
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
                SessionManager.set_current_index(current_images.index(uploaded_file))
            except ValueError:
                SessionManager.set_current_index(0)
            
            return get_image_info()
            
        except Exception as e:
            return jsonify({'error': f'Upload failed: {str(e)}'})

@app.route('/rotate_image', methods=['POST'])
def rotate_image():
    current_images = SessionManager.get_current_images()
    current_index = SessionManager.get_current_index()
    
    if not current_images or current_index >= len(current_images):
        return jsonify({'error': 'No image selected'})
    
    direction = request.json.get('direction', 'right')  # 'left' or 'right'
    
    try:
        image_path = current_images[current_index]
        
        with Image.open(image_path) as img:
            # Rotate 90 degrees clockwise or counterclockwise
            if direction == 'right':
                rotated = img.rotate(-90, expand=True)
            else:  # left
                rotated = img.rotate(90, expand=True)
            
            rotated.save(image_path)
        
        # Clear the cache for this image to force refresh
        image_to_base64.cache_clear()
        
        return get_image_info()
        
    except Exception as e:
        return jsonify({'error': f'Rotation failed: {str(e)}'})

@app.route('/download_file/<filename>')
def download_file(filename):
    try:
        output_dir = '/app/output'
        file_path = os.path.join(output_dir, secure_filename(filename))
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download_all_zip')
def download_all_zip():
    try:
        import zipfile
        import tempfile
        
        output_dir = '/app/output'
        if not os.path.exists(output_dir):
            return jsonify({'error': 'No files found'}), 404
            
        files = [f for f in os.listdir(output_dir) if f.endswith('.txt')]
        if not files:
            return jsonify({'error': 'No files found'}), 404
            
        # Create temporary zip file
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        with zipfile.ZipFile(temp_zip.name, 'w') as zip_file:
            for filename in files:
                file_path = os.path.join(output_dir, filename)
                zip_file.write(file_path, filename)
                
        return send_file(temp_zip.name, as_attachment=True, download_name='converted_poems.zip')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download_and_cleanup', methods=['POST'])
def download_and_cleanup():
    try:
        output_dir = '/app/output'
        if os.path.exists(output_dir):
            for filename in os.listdir(output_dir):
                if filename.endswith('.txt'):
                    file_path = os.path.join(output_dir, filename)
                    os.remove(file_path)
                    logging.info(f"Cleaned up file: {file_path}")
        return jsonify({'success': 'Files cleaned up'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/list_files')
def list_files():
    try:
        output_dir = '/app/output'
        files = []
        if os.path.exists(output_dir):
            for f in os.listdir(output_dir):
                if f.endswith('.txt'):
                    file_path = os.path.join(output_dir, f)
                    file_size = os.path.getsize(file_path)
                    file_time = os.path.getmtime(file_path)
                    files.append({
                        'name': f,
                        'size': file_size,
                        'modified': file_time
                    })
        return jsonify({'files': files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
            clean_school = _filename_clean_pattern.sub('', school_name).strip().replace(' ', '_')
            parts.append(clean_school)
        if student_name:
            clean_student = _filename_clean_pattern.sub('', student_name).strip().replace(' ', '_')
            parts.append(clean_student)
        if poem_title:
            clean_poem = _filename_clean_pattern.sub('', poem_title).strip().replace(' ', '_')
            parts.append(clean_poem)
        if poem_theme:
            parts.append(poem_theme)
        
        fallback_name = os.path.splitext(filename)[0] if filename else 'converted_text'
        base_name = '_'.join(parts) if parts else fallback_name
        
        # Ensure base_name is not empty - use date and counter
        if not base_name or base_name.strip() == '':
            from datetime import datetime
            date_str = datetime.now().strftime('%Y%m%d')
            counter = 1
            base_name = f'{date_str}_{counter:03d}'
            # Check if file exists and increment counter
            while os.path.exists(os.path.join(output_dir, f"{base_name}.txt")):
                counter += 1
                base_name = f'{date_str}_{counter:03d}'
        
        output_dir = '/app/output'
        
        # Create the output directory if it doesn't exist
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as dir_error:
            logging.error(f"Cannot create output directory {output_dir}: {dir_error}")
            return jsonify({'error': f'Cannot create output directory: {str(dir_error)}'})
        
        save_path = os.path.join(output_dir, f"{base_name}.txt")
        
        # Create backup if file exists
        if os.path.exists(save_path):
            backup_path = f"{save_path}.backup"
            shutil.copy2(save_path, backup_path)
        
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        # Verify file was written correctly
        if os.path.getsize(save_path) == 0:
            return jsonify({'error': 'File save verification failed'})
        
        # Move processed image from uploads to converted_images folder
        current_images = SessionManager.get_current_images()
        current_index = SessionManager.get_current_index()
        if current_images and current_index < len(current_images):
            current_image_path = current_images[current_index]
            upload_dir = os.environ.get('UPLOAD_DIRECTORY', os.getcwd())
            converted_dir = os.environ.get('CONVERTED_IMAGES_DIRECTORY', '/app/O-Ocr/converted_images')
            
            # Ensure converted directory exists and is accessible
            try:
                os.makedirs(converted_dir, exist_ok=True)
                logging.info(f"Converted directory: {converted_dir}")
            except Exception as dir_error:
                logging.error(f"Cannot create converted directory {converted_dir}: {dir_error}")
                return jsonify({'error': f'Cannot create converted directory: {str(dir_error)}'})
            
            image_filename = os.path.basename(current_image_path)
            new_image_path = os.path.join(converted_dir, image_filename)
            
            try:
                # Check if source file exists before moving
                if not os.path.exists(current_image_path):
                    logging.error(f"Source image does not exist: {current_image_path}")
                    return jsonify({'error': f'Source image not found: {current_image_path}'})
                
                # Check if destination already exists and handle it
                if os.path.exists(new_image_path):
                    logging.warning(f"Destination file already exists, will overwrite: {new_image_path}")
                    os.remove(new_image_path)
                
                logging.info(f"Moving image from {current_image_path} to {new_image_path}")
                logging.info(f"Source exists: {os.path.exists(current_image_path)}")
                logging.info(f"Source size: {os.path.getsize(current_image_path) if os.path.exists(current_image_path) else 'N/A'}")
                logging.info(f"Destination dir exists: {os.path.exists(converted_dir)}")
                logging.info(f"Destination dir writable: {os.access(converted_dir, os.W_OK) if os.path.exists(converted_dir) else 'N/A'}")
                
                shutil.move(current_image_path, new_image_path)
                
                # Verify the move was successful
                if os.path.exists(new_image_path) and not os.path.exists(current_image_path):
                    logging.info(f"Image moved successfully from {current_image_path} to {new_image_path}")
                else:
                    logging.error(f"Move verification failed. Source exists: {os.path.exists(current_image_path)}, Dest exists: {os.path.exists(new_image_path)}")
                    return jsonify({'error': 'Image move verification failed'})
                
                # Clear image cache since file path changed
                image_to_base64.cache_clear()
                
                # Update session with new image list
                updated_images = get_image_files()
                logging.info(f"Before update - Current images: {len(current_images)}")
                logging.info(f"After move - Updated images: {len(updated_images)}")
                logging.info(f"Current index: {current_index}")
                
                # Debug: Log the actual image paths
                logging.info(f"Old image list: {[os.path.basename(img) for img in current_images[:3]]}")  # First 3 for brevity
                logging.info(f"New image list: {[os.path.basename(img) for img in updated_images[:3]]}")  # First 3 for brevity
                
                SessionManager.set_current_images(updated_images)
                
                # Adjust index if needed
                if not updated_images:
                    SessionManager.set_current_index(0)
                    logging.info("No images remaining, set index to 0")
                    # Return special response when no more images to process
                    return jsonify({
                        'success': f'Text saved to {base_name}.txt',
                        'refresh': True,
                        'message': 'All images processed! No more images in upload directory.',
                        'no_more_images': True
                    })
                elif current_index >= len(updated_images):
                    # If current index is beyond the new list, go to the last image
                    new_index = len(updated_images) - 1
                    SessionManager.set_current_index(new_index)
                    logging.info(f"Adjusted index from {current_index} to {new_index}")
                else:
                    # Keep the same index, but the image at that index should be different now
                    logging.info(f"Keeping index {current_index}, but image should be different")
                    
            except PermissionError as perm_error:
                logging.error(f"Permission denied moving image: {perm_error}")
                return jsonify({'error': f'Permission denied: {str(perm_error)}. Check Docker volume permissions.'})
            except FileNotFoundError as fnf_error:
                logging.error(f"File not found during move: {fnf_error}")
                return jsonify({'error': f'File not found: {str(fnf_error)}'})
            except Exception as move_error:
                logging.error(f"Could not move image: {move_error}")
                logging.error(f"Error type: {type(move_error).__name__}")
                return jsonify({'error': f'Could not move image to converted directory: {str(move_error)}'})
        
        return jsonify({
            'success': f'Text saved to {base_name}.txt',
            'refresh': True,
            'message': 'File saved and image moved to completed folder'
        })
        
    except PermissionError:
        return jsonify({'error': 'Permission denied. Cannot write to directory.'})
    except OSError as e:
        return jsonify({'error': f'File system error: {str(e)}'})
    except Exception as e:
        return jsonify({'error': f'Save failed: {str(e)}'})

def cleanup_old_files():
    """Clean up files older than 24 hours"""
    try:
        output_dir = '/app/output'
        converted_dir = os.environ.get('CONVERTED_IMAGES_DIRECTORY', '/app/converted_images')
        
        current_time = time.time()
        cutoff_time = current_time - (48 * 60 * 60)  # 48 hours ago
        
        for directory in [output_dir, converted_dir]:
            if not os.path.exists(directory):
                continue
                
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                try:
                    if os.path.getmtime(file_path) < cutoff_time:
                        os.remove(file_path)
                        logging.info(f"Cleaned up old file: {file_path}")
                except Exception as e:
                    logging.error(f"Error cleaning up {file_path}: {e}")
    except Exception as e:
        logging.error(f"Error during cleanup: {e}")

# Run cleanup every hour
import threading
def periodic_cleanup():
    while True:
        time.sleep(3600)  # 1 hour
        cleanup_old_files()

cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
cleanup_thread.start()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)