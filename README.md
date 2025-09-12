# Image to Text Verification Interface

A production-ready Docker application for converting handwritten student poems to digital text using Groq's AI vision model. Features intelligent filename generation with school names, student names, poem titles, and themes.

## 🚀 Features

### Core Functionality
- **Split-screen web interface**: Original image on left, editable text on right
- **Groq AI integration**: Uses `meta-llama/llama-4-scout-17b-16e-instruct` for accurate OCR
- **Real-time editing**: Edit and correct transcribed text immediately
- **PDF support**: Automatically extracts pages from PDF files and moves PDFs to processed folder
- **HEIC/HEIF support**: Automatic conversion to JPEG for Apple device photos
- **Batch processing**: Process multiple images with one click
- **Smart navigation**: Browse through images with Previous/Next buttons
- **Image rotation**: Rotate images left/right for better readability

### Performance Optimizations
- **Automatic image resizing**: Images resized to 1024x1024 for faster processing
- **LRU caching**: Intelligent caching of converted images for better performance
- **Optimized PDF processing**: Reduced DPI (150) for faster PDF-to-image conversion
- **Memory management**: Efficient handling of large files and batch operations

### Intelligent File Naming
AI automatically identifies and extracts:
- **School name**: Lincoln Elementary, Roosevelt Middle School
- **Student name**: Maria Garcia, John Smith
- **Poem title**: Ocean Dreams, My Family
- **Theme detection**: nature, family, friendship, emotions, seasons, school
- **Confidence scoring**: Shows AI confidence level (e.g., 8/10) in interface

### Production Features
- **Docker containerized**: Easy deployment and scaling
- **Health monitoring**: Built-in health checks
- **Resource limits**: Memory and CPU constraints
- **Comprehensive logging**: Detailed logging with error tracking and debugging
- **Security**: Non-root user, input validation
- **Automatic file management**: Processed files moved to separate directories
- **Session management**: Robust session handling with automatic cleanup
- **Error recovery**: Graceful handling of file operations and API failures

### User Experience
- **Loading indicators**: Spinners for upload, convert, and save operations
- **Auto-save drafts**: Text automatically saved every 30 seconds
- **Draft management**: Manual cleanup of stored drafts
- **Zoom functionality**: Click images to zoom in/out
- **Keyboard shortcuts**: Arrow keys for navigation, Ctrl+Enter to convert, Ctrl+S to save
- **localStorage cleanup**: Automatic cleanup of old drafts and manual clear option

## 📁 File Structure

### Generated Filenames
Files are automatically named using AI-extracted information:
```
{School}_{Student}_{Poem_Title}_{Theme}.txt
```

**Examples:**
- `Lincoln_Elementary_Maria_Garcia_Ocean_Dreams_nature.txt`
- `Roosevelt_Middle_John_Smith_My_Family_family.txt`
- `Washington_High_Sarah_Johnson_Best_Friend_friendship.txt`
- `Central_School_Alex_Chen_Happy_Day_emotions.txt`

### File Contents
Saved text files include:
- Complete transcribed poem with original formatting
- `POEM_TITLE: [AI-identified title]`
- `POEM_THEME: [AI-identified theme]`
- `POEM_LANGUAGE: [detected language]`
- For Zip Ode mode: ZIP_CODE and explanation
- Confidence score displayed in interface (not saved in file)

### AI Theme Detection
The AI automatically categorizes poems into themes:
- **family**: poems about relatives, parents, siblings
- **nature**: poems about outdoors, animals, weather, plants
- **friendship**: poems about friends, playing together, kindness
- **school**: poems about learning, teachers, classroom activities
- **emotions**: poems expressing feelings, moods, reactions
- **seasons**: poems about weather, seasonal activities, holidays
- **miami**: poems about Miami, Florida, beaches, city life, local culture
- **sun**: poems about sunshine, warmth, light

### Directory Structure
```
project/
├── uploads/                    # New files for processing
│   ├── new_student_worksheet.pdf
│   ├── new_maria_poem.jpg
│   └── new_class_poems.pdf
├── converted_images/           # Processed images and PDFs
│   ├── processed_student_worksheet.pdf
│   ├── processed_maria_poem.jpg
│   └── extracted_page_images.png
├── converted_poems/            # Generated text files
│   ├── Lincoln_Elementary_Maria_Garcia_Ocean_Dreams_nature.txt
│   ├── Roosevelt_Middle_John_Smith_My_Family_family.txt
│   └── batch_results.json
├── docs/                       # Documentation
│   └── mac-docker-setup.md     # Mac-specific Docker setup guide
├── docker-compose.yml
├── Dockerfile
└── README.md
```

**File Flow:**
1. **Upload**: Files go to `uploads/` directory
2. **PDF Processing**: PDFs converted to images, then moved to `converted_images/`
3. **Image Processing**: After text is saved, images moved to `converted_images/`
4. **Text Output**: Generated text files saved to `converted_poems/`

## 🐳 Docker Setup (Recommended)

### Quick Start
```bash
# Clone and navigate to project
cd your-project-directory

# Build and start
docker-compose up --build

# Access the application
open http://localhost:5002
```

### Mac Users
For Mac-specific Docker setup instructions, including volume mounting and performance optimization, see:
📖 **[Mac Docker Setup Guide](docs/mac-docker-setup.md)**

### Environment Variables
Create `.env` file:
```env
GROQ_API_KEY=your_groq_api_key_here
APP_PASSWORD=your_admin_password
SECRET_KEY=your_secret_key
```

### Production Deployment
```bash
# Production mode with enhanced resources
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up --build
```

## 💻 Local Development

### Prerequisites
- Python 3.11+
- poppler-utils (for PDF processing)

### Installation
```bash
# Install dependencies
pip install -r requirements.txt

# For macOS PDF support
brew install poppler

# Set environment variables
export GROQ_API_KEY="your_api_key"
export UPLOAD_DIRECTORY="./uploads"
export OUTPUT_DIRECTORY="./converted_poems"

# Run the application
python web_app.py
```

## 🎯 Usage

### Web Interface
1. **Upload files**: Click "Upload Image" to add PDFs or images
2. **Select mode**: Choose processing mode (Student Poems, Free Form OCR, Zipcode, Custom)
3. **Navigate**: Use Previous/Next to browse through files
4. **Convert**: Click "Convert to Text" to transcribe current image
5. **Review confidence**: Check AI confidence score next to "Converted Text"
6. **Edit**: Modify the transcribed text in the right panel
7. **Save**: Click "Save Text" to create the final file with metadata
8. **Batch process**: Click "Batch Process All" to convert all uploaded files at once

### Batch Processing

**From Web Interface (Recommended):**
1. Upload multiple images/PDFs to the uploads folder
2. Click "Batch Process All" button
3. Confirm the action in the dialog
4. Wait for processing to complete
5. Check converted_poems folder for results

**From Command Line:**
```bash
# Process all files in uploads directory
docker-compose run --rm batch-processor

# Or run on existing container
docker-compose exec image-to-text python batch_processor.py
```

**Bulk Conversion Features:**
- Processes all images and PDFs in uploads folder
- AI automatically identifies student names, schools, poem titles, and themes
- Creates meaningful filenames for each converted text
- Includes POEM_TITLE and POEM_THEME metadata in saved files
- Generates batch_results.json with processing summary
- Handles errors gracefully - continues processing if individual files fail
- Shows progress and completion status

## 📋 Supported Formats

### Input Files
- **Images**: PNG, JPG, JPEG, GIF, BMP, TIFF, HEIC, HEIF
- **Documents**: PDF (automatically extracts pages and moves PDF to processed folder)

### Output Files
- **Text files**: UTF-8 encoded .txt files
- **Batch results**: JSON summary with metadata

### File Processing
- **HEIC/HEIF**: Automatically converted to JPEG during upload
- **Large images**: Automatically resized to 1024x1024 for optimal processing
- **PDFs**: Converted to PNG images at 150 DPI, original PDF moved to converted folder
- **Processed files**: All processed images and PDFs moved to separate directory

## 🔧 Configuration

### Docker Volumes
- `./uploads:/app/uploads` - Input files
- `./converted_poems:/app/output` - Output files

### Resource Limits
- **Memory**: 1GB (2GB in production)
- **CPU**: 0.5 cores (1.0 in production)
- **File size**: 50MB maximum

### Health Monitoring
```bash
# Check application health
curl http://localhost:5000/health

# View container logs
docker-compose logs -f
```

## 🛠️ Development

### Project Structure
```
├── web_app.py              # Main Flask application
├── batch_processor.py      # Batch processing logic
├── templates/
│   ├── index.html          # Main web interface
│   └── login.html          # Authentication page
├── Dockerfile              # Multi-stage container build
├── docker-compose.yml      # Development configuration
├── docker-compose.prod.yml # Production overrides
├── requirements.txt        # Python dependencies
└── .dockerignore          # Docker build exclusions
```

### Key Components
- **Flask web server**: Handles HTTP requests and file uploads
- **Groq AI client**: Processes images using vision model
- **PDF processor**: Extracts individual pages from PDFs
- **Theme detector**: Analyzes poem content for categorization
- **Filename generator**: Creates meaningful file names

## 🔒 Security

- **Non-root container**: Runs as unprivileged user
- **Input validation**: Sanitizes filenames and paths
- **File size limits**: Prevents resource exhaustion
- **Path traversal protection**: Validates file access
- **Environment variables**: Secrets stored outside code

## 📊 Monitoring

- **Health checks**: Automatic container health monitoring
- **Log rotation**: Prevents log files from growing too large
- **Resource monitoring**: CPU and memory usage tracking
- **Restart policies**: Automatic recovery from failures

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with Docker
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🆘 Troubleshooting

### Common Issues

**Container won't start:**
```bash
# Check logs
docker-compose logs

# Rebuild from scratch
docker-compose down
docker-compose up --build --force-recreate
```

**API errors:**
- Verify GROQ_API_KEY is set correctly
- Check API rate limits
- Ensure internet connectivity

**File permission errors:**
```bash
# Fix directory permissions
sudo chown -R $USER:$USER uploads converted_poems
```

**PDF processing fails:**
- Ensure poppler-utils is installed in container
- Check PDF file isn't corrupted
- Verify file size is under 50MB limit

**Images not moving after save:**
- Check Docker volume permissions for converted_images directory
- Verify CONVERTED_IMAGES_DIRECTORY environment variable is set
- Check application logs for move operation errors

**Performance issues:**
- Images are automatically resized to 1024x1024 for faster processing
- PDF DPI reduced to 150 for optimal speed
- LRU cache implemented for repeated image access
- Use SSD storage for better I/O performance

### Performance Optimization

- **Automatic optimizations**: Images resized, PDFs processed at optimal DPI
- **Caching**: LRU cache for frequently accessed images
- **Memory management**: Efficient handling of large files
- **File organization**: Automatic cleanup prevents directory bloat
- Use SSD storage for better I/O performance
- Increase memory limits for large batch jobs
- Monitor CPU usage during processing
- Consider horizontal scaling for high volume

---

**Built with ❤️ for educators digitizing student work**