#!/bin/bash

# Replace with your Docker Hub username
DOCKER_USERNAME="marioacruz"
IMAGE_NAME="o-ocr"
TAG="latest"

# Build the image
docker build -t $DOCKER_USERNAME/$IMAGE_NAME:$TAG .

# Login to Docker Hub (you'll be prompted for credentials)
docker login

# Push to Docker Hub
docker push $DOCKER_USERNAME/$IMAGE_NAME:$TAG

echo "Image pushed to Docker Hub: $DOCKER_USERNAME/$IMAGE_NAME:$TAG"