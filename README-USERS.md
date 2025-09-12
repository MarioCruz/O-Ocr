# Quick Start Guide

## Requirements
- Docker Desktop installed
- Groq API key

## Setup (2 minutes)

1. **Download files:**
   - `docker-compose-distribution.yml`
   - `.env.example`

2. **Create API key file:**
   ```bash
   echo "GROQ_API_KEY=your_api_key_here" > .env
   ```

3. **Start the app:**
   ```bash
   docker-compose -f docker-compose-distribution.yml up -d
   ```

4. **Open:** http://localhost:5002

## File Locations
- **Upload files to:** `~/Documents/O-Ocr/uploads/`
- **Results saved to:** `~/Documents/O-Ocr/converted_poems/`

## Stop the app
```bash
docker-compose -f docker-compose-distribution.yml down
```