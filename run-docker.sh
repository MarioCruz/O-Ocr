#!/bin/bash

# Create directories if they don't exist
mkdir -p ~/Documents/O-Ocr/{uploads,converted_poems,converted_images}

# Run the Docker container
docker run -d \
  --name ocr-app \
  -p 5002:5002 \
  -v ~/Documents/O-Ocr:/app/O-Ocr \
  -e GROQ_API_KEY="${GROQ_API_KEY}" \
  -e UPLOAD_DIRECTORY=/app/O-Ocr/uploads \
  -e OUTPUT_DIRECTORY=/app/O-Ocr/converted_poems \
  -e CONVERTED_IMAGES_DIRECTORY=/app/O-Ocr/converted_images \
  marioacruz/o-ocr:latest

echo "OCR app running at http://localhost:5002"
echo "Files will be saved to ~/Documents/O-Ocr/"