# Mac Docker Setup Guide for O-Ocr

This guide provides Mac-specific instructions for setting up and running the O-Ocr image-to-text conversion application using Docker.

## Prerequisites

### 1. Install Docker Desktop for Mac

Download and install Docker Desktop from the official website:
- Visit: https://www.docker.com/products/docker-desktop/
- Download the appropriate version for your Mac (Intel or Apple Silicon)
- Follow the installation wizard
- Start Docker Desktop and ensure it's running

### 2. Install Homebrew (if not already installed)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 3. Install Required Dependencies

For PDF support on macOS:
```bash
brew install poppler
```

## Project Setup

### 1. Clone and Navigate to Project

```bash
git clone <your-repository-url>
cd O-Ocr
```

### 2. Create Environment File

Create a `.env` file in the project root:
```bash
cp .env.example .env
```

Edit the `.env` file and add your Groq API key:
```
GROQ_API_KEY=your_groq_api_key_here
```

### 3. Create Local Directory Structure

Before running Docker, create the required directory structure on your Mac:

```bash
# Create the main project directory
mkdir -p ~/O-Ocr

# Create subdirectories
mkdir -p ~/O-Ocr/uploads
mkdir -p ~/O-Ocr/converted_poems
mkdir -p ~/O-Ocr/converted_images

# Set proper permissions (important for Mac)
chmod -R 755 ~/O-Ocr
```

### 4. Mac-Specific Volume Mounting

The `docker-compose.yml` file is configured with Mac-specific volume mounting:

```yaml
volumes:
  - ~/O-Ocr:/app/O-Ocr
```

This maps your local `~/O-Ocr` directory to the container's `/app/O-Ocr` directory, allowing:
- Persistent file storage
- Direct access to uploaded images and converted text
- Real-time file synchronization between host and container

**Important:** The Docker Compose configuration automatically creates missing directories on startup to prevent permission errors.

## Running the Application

### 1. Start the Main Application

```bash
docker-compose up -d image-to-text
```

The application will be available at: http://localhost:5002

### 2. Run Batch Processing (Optional)

For batch processing of multiple files:
```bash
docker-compose --profile batch up batch-processor
```

### 3. View Logs

```bash
# View main application logs
docker-compose logs -f image-to-text

# View batch processor logs
docker-compose logs -f batch-processor
```

## Mac-Specific Considerations

### File Permissions

Docker Desktop for Mac handles file permissions automatically, but if you encounter issues:

1. Ensure your user has read/write access to the `~/O-Ocr` directory:
```bash
chmod -R 755 ~/O-Ocr
```

2. If needed, fix ownership:
```bash
sudo chown -R $(whoami):staff ~/O-Ocr
```

### Performance Optimization

For better performance on Mac:

1. **Enable VirtioFS** (Docker Desktop 4.6+):
   - Go to Docker Desktop → Settings → General
   - Enable "Use the new Virtualization framework"
   - Enable "Enable VirtioFS accelerated directory sharing"

2. **Allocate Sufficient Resources**:
   - Go to Docker Desktop → Settings → Resources
   - Recommended: 4GB RAM, 2 CPUs minimum

3. **Use .dockerignore**:
   Ensure you have a `.dockerignore` file to exclude unnecessary files:
   ```
   .git
   .gitignore
   README.md
   .env
   .DS_Store
   __pycache__
   *.pyc
   venv/
   node_modules/
   ```

### Directory Structure

The application expects this directory structure in `~/O-Ocr`:

```
~/O-Ocr/
├── uploads/              # Upload directory for images/PDFs
├── converted_poems/      # Output directory for converted text
├── converted_images/     # Directory for processed images
└── logs/                # Application logs (if enabled)
```

These directories will be created automatically when the application starts.

## Troubleshooting

### Common Issues on Mac

1. **Permission Denied Error** (`Cannot create converted directory: [Errno 13] Permission denied`):
   ```bash
   # Stop the containers first
   docker-compose down
   
   # Create directories with proper permissions
   mkdir -p ~/O-Ocr/{uploads,converted_poems,converted_images}
   chmod -R 755 ~/O-Ocr
   
   # Rebuild and restart
   docker-compose up --build
   ```

2. **Port Already in Use**:
   ```bash
   # Check what's using port 5002
   lsof -i :5002
   
   # Kill the process if needed
   kill -9 <PID>
   ```

3. **Docker Desktop Not Running**:
   - Ensure Docker Desktop is started and running
   - Check the Docker icon in your menu bar

4. **Volume Mount Issues**:
   ```bash
   # Verify the directory exists
   ls -la ~/O-Ocr
   
   # Create if it doesn't exist
   mkdir -p ~/O-Ocr/{uploads,converted_poems,converted_images}
   
   # Fix ownership if needed
   sudo chown -R $(whoami):staff ~/O-Ocr
   ```

4. **Memory Issues**:
   - Increase Docker Desktop memory allocation
   - The application is limited to 1GB RAM by default (configurable in docker-compose.yml)

5. **Apple Silicon (M1/M2) Compatibility**:
   - The application should work natively on Apple Silicon
   - If you encounter issues, try adding platform specification:
   ```yaml
   services:
     image-to-text:
       platform: linux/amd64  # Add this line if needed
   ```

### Health Check

The application includes a health check endpoint. Verify it's working:
```bash
curl -f http://localhost:5002/health
```

### Logs and Debugging

View detailed logs:
```bash
# All services
docker-compose logs

# Specific service with follow
docker-compose logs -f image-to-text

# Last 100 lines
docker-compose logs --tail=100 image-to-text
```

## Stopping the Application

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (careful - this deletes data!)
docker-compose down -v

# Stop specific service
docker-compose stop image-to-text
```

## Updating the Application

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d image-to-text
```

## Support

If you encounter Mac-specific issues:

1. Check Docker Desktop logs: Docker Desktop → Troubleshoot → Get support
2. Verify system requirements are met
3. Ensure you have the latest version of Docker Desktop
4. Check the application logs for specific error messages

For application-specific issues, check the main README.md file for general troubleshooting steps.