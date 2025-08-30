import os
import base64
from groq import Groq
import json
from datetime import datetime

class BatchImageProcessor:
    def __init__(self, base_directory="/Users/mariocruz/FC/O"):
        self.client = Groq(api_key=os.environ.get('GROQ_API_KEY', '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'))
        self.base_directory = os.path.abspath(base_directory)
    
    def _validate_path(self, file_path):
        """Validate path is within base directory"""
        abs_path = os.path.abspath(file_path)
        if not abs_path.startswith(self.base_directory):
            raise ValueError(f"Path traversal detected: {file_path}")
        return abs_path
    
    def image_to_base64(self, image_path):
        """Convert image to base64 string"""
        validated_path = self._validate_path(image_path)
        with open(validated_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def extract_student_info(self, text):
        """Extract student name, school, poem title, and theme from converted text"""
        lines = text.split('\n')
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
        
        # Extract poem title and theme from AI response
        for line in lines:
            if line.startswith('POEM_TITLE:'):
                poem_title = line.replace('POEM_TITLE:', '').strip()
            elif line.startswith('POEM_THEME:'):
                poem_theme = line.replace('POEM_THEME:', '').strip()
        

        
        return student_name, school_name, poem_title, poem_theme
    
    def create_filename(self, student_name, school_name, poem_title, poem_theme, fallback_name):
        """Create meaningful filename from student info"""
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
        
        return '_'.join(parts) if parts else fallback_name
    
    def convert_image_to_text(self, image_path):
        """Convert single image to text using Groq API"""
        try:
            base64_image = self.image_to_base64(image_path)
            
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Transcribe everything in this image including student name, school name at the top, and the complete poem below. Preserve exact formatting, line breaks, and punctuation. Use [?] for unclear words. At the end, add: 'POEM_TITLE: [title of the poem]' and 'POEM_THEME: [theme like family, nature, friendship, school, emotions, seasons, or miami]'."
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
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                temperature=0.1,
                max_tokens=1000
            )
            
            return chat_completion.choices[0].message.content
            
        except Exception as e:
            return f"Error processing {image_path}: {str(e)}"
    
    def process_directory(self, directory_path, output_directory=None, output_file="batch_results.json"):
        if output_directory is None:
            output_directory = directory_path
        """Process all images in a directory"""
        supported_formats = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff')
        results = []
        
        image_files = [f for f in os.listdir(directory_path) 
                      if f.lower().endswith(supported_formats)]
        
        print(f"Found {len(image_files)} image files to process...")
        
        for i, filename in enumerate(image_files, 1):
            image_path = os.path.join(directory_path, filename)
            print(f"Processing {i}/{len(image_files)}: {filename}")
            
            converted_text = self.convert_image_to_text(image_path)
            
            # Extract student info for meaningful filename
            student_name, school_name, poem_title, poem_theme = self.extract_student_info(converted_text)
            fallback_name = os.path.splitext(filename)[0]
            meaningful_name = self.create_filename(student_name, school_name, poem_title, poem_theme, fallback_name)
            
            result = {
                "filename": filename,
                "image_path": image_path,
                "converted_text": converted_text,
                "student_name": student_name,
                "school_name": school_name,
                "poem_title": poem_title,
                "poem_theme": poem_theme,
                "saved_as": f"{meaningful_name}.txt",
                "processed_at": datetime.now().isoformat()
            }
            
            results.append(result)
            
            # Save individual text file with meaningful name
            text_filename = f"{meaningful_name}.txt"
            text_path = os.path.join(output_directory, text_filename)
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(converted_text)
            
            print(f"  Saved as: {text_filename}")
        
        # Save batch results as JSON
        output_path = os.path.join(output_directory, output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        with open(validated_output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\nBatch processing completed. Results saved to {output_path}")
        print(f"Created {len(results)} text files with meaningful names")
        return results

def main():
    upload_dir = os.environ.get('UPLOAD_DIRECTORY', os.getcwd())
    output_dir = os.environ.get('OUTPUT_DIRECTORY', os.getcwd())
    
    processor = BatchImageProcessor(upload_dir)
    
    # Process all images in the directory
    results = processor.process_directory(upload_dir, output_dir)
    
    print(f"Successfully processed {len(results)} images")

if __name__ == "__main__":
    main()