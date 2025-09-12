import os
import base64
from utils import _filename_clean_pattern
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
from groq import Groq
import json
from datetime import datetime, timezone
from student_info import StudentInfo

# -----------------------------
# Helpers for local validation
# -----------------------------
_WORD_RE = re.compile(r"[A-Za-z0-9']+")

def word_count(s: str) -> int:
    return len(_WORD_RE.findall(s or ""))

def zip_digits(zipcode: str):
    if not zipcode or not isinstance(zipcode, str):
        return []
    return [int(d) for d in zipcode if d.isdigit()]

def validate_poem_lines(lines, zipcode: str):
    """Local validator (optional, independent of the model's table)"""
    zip_pattern = zip_digits(zipcode) if zipcode and zipcode.isdigit() else []
    rows = []
    for i, need in enumerate(zip_pattern, start=1):
        line = lines[i - 1] if i - 1 < len(lines) else ""
        have = word_count(line)
        ok = (have == need if need > 0 else have == 0)
        rows.append(
            {"line": i, "expected": need, "actual": have, "ok": ok, "text": line}
        )
    overall = bool(zip_pattern) and len(lines) == len(zip_pattern) and all(r["ok"] for r in rows)
    return {"rows": rows, "overall_ok": overall}


class BatchImageProcessor:
    def __init__(self, base_directory="/Users/mariocruz/FC/O", api_key=None):
        if api_key is None:
            api_key = os.environ.get('GROQ_API_KEY')
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is required")
        self.client = Groq(api_key=api_key)
        self.base_directory = os.path.abspath(base_directory)
        # Pre-compile regex patterns for performance
        self._field_pattern_cache = {}
        self._label_pattern_cache = {}
        self._filename_clean_pattern = re.compile(r'[^a-zA-Z0-9 -]')
    

    
    def image_to_base64(self, image_path):
        """Convert image to base64 string with compression for API limits"""
        from PIL import Image
        import io
        
        try:
            # Always compress images for API compatibility
            with Image.open(image_path) as img:
                # Convert to RGB if needed
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize if too large
                max_size = (1024, 1024)
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # Compress to JPEG
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=75, optimize=True)
                return base64.b64encode(buffer.getvalue()).decode('utf-8')
                
        except Exception as e:
            # Fallback to original method if PIL fails
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')

    # -----------------------------
    # Parsing helpers for model output
    # -----------------------------
    def _get_field(self, text: str, key: str, default: str = "Unknown") -> str:
        """
        Extracts single-line fields like:
        KEY: value
        Returns 'default' if not found.
        """
        # anchor on line starts to avoid grabbing similar words elsewhere
        m = re.search(rf"(?mi)^\s*{re.escape(key)}\s*:\s*(.*)$", text)
        if m:
            return m.group(1).strip() or default
        return default

    def _block_after_label(self, text: str, label: str, stop_labels):
        """
        Extract the block of text after a label line (exact match), until the next label in stop_labels.
        """
        # Use cached patterns for performance
        cache_key = (label, tuple(stop_labels) if stop_labels else ())
        if cache_key not in self._label_pattern_cache:
            self._label_pattern_cache[cache_key] = {
                'start': re.compile(rf"(?mi)^\s*{re.escape(label)}\s*:\s*$"),
                'inline': re.compile(rf"(?mi)^\s*{re.escape(label)}\s*:\s*(.+)$"),
                'stop': re.compile(rf"(?mi)^\s*({'|'.join(re.escape(lab) for lab in stop_labels)})\s*:") if stop_labels else None
            }
        
        patterns = self._label_pattern_cache[cache_key]
        
        start = patterns['start'].search(text)
        if not start:
            # Also try "LABEL:" followed directly by content on same line
            m_inline = patterns['inline'].search(text)
            return (m_inline.group(1).strip(),) if m_inline else ("",)
        start_idx = start.end()
        # Find next stop label efficiently with cached regex
        next_stop = len(text)
        if patterns['stop']:
            m = patterns['stop'].search(text[start_idx:])
            if m:
                next_stop = start_idx + m.start()
        block = text[start_idx:next_stop].strip()
        return (block,)

    def parse_zip_ode_response(self, content: str) -> dict:
        """
        Parses the structured response produced by processing_mode='zip_ode_explain'.
        """
        # Core single-line fields
        student_name = self._get_field(content, "STUDENT_NAME")
        school_name  = self._get_field(content, "SCHOOL_NAME")
        zip_code     = self._get_field(content, "ZIP_CODE")
        poem_title   = self._get_field(content, "POEM_TITLE", default="")
        poem_theme   = self._get_field(content, "POEM_THEME", default="")
        poem_lang    = self._get_field(content, "POEM_LANGUAGE", default="")

        # Blocks
        transcription = self._block_after_label(
            content, "TRANSCRIPTION",
            stop_labels=["STUDENT_NAME", "SCHOOL_NAME", "ZIP_CODE", "POEM", "POEM_TITLE", "POEM_THEME", "POEM_LANGUAGE", "Confidence"]
        )[0]

        poem_block = self._block_after_label(
            content, "POEM",
            stop_labels=["POEM_TITLE", "POEM_THEME", "POEM_LANGUAGE", "Confidence"]
        )[0]
        poem_lines = [ln.rstrip() for ln in poem_block.splitlines() if ln.strip() != ""]

        # Local validation (optional)
        validation_rows = []
        if zip_code and zip_code.isdigit():
            validation_result = validate_poem_lines(poem_lines, zip_code)
            validation_rows = validation_result["rows"]
            overall_ok = str(validation_result["overall_ok"])
        else:
            overall_ok = "Unknown"

        return {
            "student_name": student_name,
            "school_name": school_name,
            "zip_code": zip_code,
            "poem_title": poem_title,
            "poem_theme": poem_theme,
            "poem_language": poem_lang,
            "transcription": transcription,
            "poem_lines": poem_lines,
            "validation_rows": validation_rows,
            "overall_ok": overall_ok
        }

    # -----------------------------
    # Legacy extractor (kept for compatibility)
    # -----------------------------
    def extract_student_info_legacy(self, text):
        """Legacy: Extract student name, school, poem title, theme, and language from older outputs"""
        lines = text.split('\n')
        info = StudentInfo()
        
        # Single pass through lines for efficiency
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Look for student name and school in first few lines
            if i < 5:
                if 'School:' in line or 'school' in line.lower():
                    info.school_name = line.split(':')[-1].strip() if ':' in line else line
                    info.school_name = re.sub(r'(?i)\bschool\b', '', info.school_name).strip()
                elif line and not line.startswith('Grade'):
                    if 'Name:' in line:
                        info.student_name = line.split('Name:')[-1].strip()
                    elif not info.student_name and len(line.split()) <= 4:  # Likely a name
                        info.student_name = line
            
            # Extract poem metadata from any line
            if line.startswith('POEM_TITLE:'):
                info.poem_title = line.replace('POEM_TITLE:', '').strip()
            elif line.startswith('POEM_THEME:'):
                info.poem_theme = line.replace('POEM_THEME:', '').strip()
            elif line.startswith('POEM_LANGUAGE:'):
                info.poem_language = line.replace('POEM_LANGUAGE:', '').strip()
        
        return info

    def create_filename(self, student_name, school_name, poem_title, poem_theme, fallback_name, zip_code=None):
        """Create meaningful filename from student info"""
        parts = []
        if school_name:
            clean_school = self._filename_clean_pattern.sub('', school_name).strip().replace(' ', '_')
            parts.append(clean_school)
        if student_name:
            clean_student = self._filename_clean_pattern.sub('', student_name).strip().replace(' ', '_')
            parts.append(clean_student)
        if poem_title:
            clean_poem = self._filename_clean_pattern.sub('', poem_title).strip().replace(' ', '_')
            parts.append(clean_poem)
        if poem_theme:
            parts.append(poem_theme)
        if zip_code and zip_code.isdigit():
            parts.append(zip_code)
        
        return '_'.join(parts) if parts else fallback_name
    
    # -----------------------------
    # Core API call
    # -----------------------------
    def convert_image_to_text(self, image_path, model="meta-llama/llama-4-scout-17b-16e-instruct", processing_mode="zip_ode_explain"):
        """Convert single image to text using Groq API"""
        try:
            base64_image = self.image_to_base64(image_path)
            
            # Prompts
            if processing_mode == "poem":
                prompt_text = f"Transcribe everything in this image including student name, school name at the top, "\
                             f"and the complete poem below. Preserve exact formatting, line breaks, and punctuation. "\
                             f"Use [?] for unclear words. At the end, add exactly these 4 lines with no additional text:\n"\
                             f"POEM_TITLE: [actual title]\n"\
                             f"POEM_THEME: [one word: family, nature, friendship, school, emotions, seasons, miami, or sun]\n"\
                             f"POEM_LANGUAGE: [language name]\n"\
                             f"Confidence: X/10"
            elif processing_mode == "freeform":
                prompt_text = f"Transcribe all text in this image exactly as it appears. Preserve formatting, line breaks, and punctuation. "\
                             f"Use [?] for unclear words. At the end, add exactly these 4 lines with no additional text:\n"\
                             f"DOCUMENT_TITLE: [best guess at title or 'Unknown']\n"\
                             f"DOCUMENT_TYPE: [worksheet, form, letter, notes, or other]\n"\
                             f"LANGUAGE: [language name]\n"\
                             f"Confidence: X/10"
            elif processing_mode == "postcard_poem":
                prompt_text = (
                    "Transcribe this postcard poem including any student name, school name, and the complete poem. "
                    "Preserve exact formatting, line breaks, and punctuation. Use [?] for unclear words. "
                    "At the end, add exactly these lines:\n"
                    "POEM_TITLE: [actual title or 'Postcard Poem']\n"
                    "POEM_THEME: [one word: family, nature, friendship, school, emotions, seasons, miami, or sun]\n"
                    "POEM_LANGUAGE: [language name]\n"
                    "POSTCARD_TYPE: [greeting, travel, art, or other]\n"
                    "Confidence: X/10"
                )
            elif processing_mode == "worksheet_poem":
                prompt_text = (
                    "Transcribe this worksheet including student name, any instructions, and the poem content. "
                    "Preserve exact formatting, line breaks, and punctuation. Use [?] for unclear words. "
                    "At the end, add exactly these lines:\n"
                    "POEM_TITLE: [actual title or worksheet title]\n"
                    "POEM_THEME: [one word: family, nature, friendship, school, emotions, seasons, miami, or sun]\n"
                    "POEM_LANGUAGE: [language name]\n"
                    "WORKSHEET_TYPE: [creative writing, fill-in-blank, template, or other]\n"
                    "Confidence: X/10"
                )
            elif processing_mode == "survey_form":
                prompt_text = (
                    "Transcribe this survey form including all questions, answers, and participant information. "
                    "Look for checkboxes (☐ ☑ ✓ ✗ X) and circles around answers. "
                    "Mark checked boxes as [✓] and unchecked as [☐]. Mark circled answers as (CIRCLED). "
                    "Preserve exact formatting, line breaks, and punctuation. Use [?] for unclear words. "
                    "At the end, add exactly these lines:\n"
                    "FORM_TITLE: [survey title or 'Survey Form']\n"
                    "FORM_TYPE: [feedback, evaluation, questionnaire, or other]\n"
                    "LANGUAGE: [language name]\n"
                    "PARTICIPANT_NAME: [if visible or 'Unknown']\n"
                    "Confidence: X/10"
                )
            elif processing_mode == "custom_poem":
                # Load custom settings
                try:
                    with open(os.path.join(os.path.dirname(__file__), 'custom_poem_settings.json'), 'r') as f:
                        settings = json.load(f)['custom_poem']
                    document_list = ', '.join(settings['document_contains'])
                    prompt_text = settings['prompt_template'].format(
                        document_contains=document_list,
                        structure=settings['structure']
                    )
                except (FileNotFoundError, KeyError, json.JSONDecodeError):
                    prompt_text = (
                        "Transcribe everything in this image including student name, school name, and poem text. "
                        "Preserve exact formatting, line breaks, and punctuation. Use [?] for unclear words. "
                        "At the end, add: POEM_TITLE: [title]\nPOEM_THEME: [theme]\nPOEM_LANGUAGE: [language]\nConfidence: X/10"
                    )
            elif processing_mode == "zip_ode_explain":
                prompt_text = (
                    "You are helping with O, Miami's 'Zip Ode' poems.\n\n"
                    "Task:\n"
                    "1) Transcribe all visible text exactly (preserve line breaks, punctuation; use [?] for unclear).\n"
                    "2) Extract these fields when possible:\n"
                    "   - STUDENT_NAME: (if present at top)\n"
                    "   - SCHOOL_NAME: (if present at top)\n"
                    "   - ZIP_CODE: (5 digits; if multiple appear, choose the one associated with the poem)\n"
                    "3) Identify the poem body (exclude headings/names).\n"
                    "4) Output a compact report exactly in the schema below (no extra commentary).\n\n"
                    "Schema (print exactly these keys, one per line, then the poem):\n"
                    "TRANSCRIPTION:\n"
                    "<full raw transcription here>\n\n"
                    "STUDENT_NAME: <string or Unknown>\n"
                    "SCHOOL_NAME: <string or Unknown>\n"
                    "ZIP_CODE: <##### or Unknown>\n\n"
                    "POEM:\n"
                    "<only the poem lines here, one per line, in order>\n\n"
                    "POEM_TITLE: <best short title or Unknown>\n"
                    "POEM_THEME: <one word: family, nature, friendship, school, emotions, seasons, miami, or sun>\n"
                    "POEM_LANGUAGE: <language name>\n"
                    "Confidence: <X/10>"
                )
            else:
                raise ValueError(f"Unknown processing_mode: {processing_mode}")
            
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_text},
                            {"type": "image_url",
                             "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                        ]
                    }
                ],
                model=model,
                temperature=0.1,
                max_tokens=2000,
                timeout=30
            )
            
            return chat_completion.choices[0].message.content
            
        except Exception as e:
            return f"Error processing {image_path}: {str(e)}"

    # -----------------------------
    # Directory processing
    # -----------------------------
    def process_directory(self, directory_path, output_directory=None, output_file="batch_results.json", processing_mode="zip_ode_explain"):
        if output_directory is None:
            output_directory = directory_path
        """Process all images in a directory"""
        supported_formats = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.heic', '.heif')
        results = []
        
        image_files = [f for f in os.listdir(directory_path) 
                      if f.lower().endswith(supported_formats)]
        
        logging.info(f"Found {len(image_files)} image files to process...")
        
        for i, filename in enumerate(image_files, 1):
            image_path = os.path.join(directory_path, filename)
            logging.info(f"Processing {i}/{len(image_files)}: {filename}")
            
            converted_text = self.convert_image_to_text(
                image_path,
                "meta-llama/llama-4-scout-17b-16e-instruct",
                processing_mode=processing_mode
            )

            # Try new structured parser first
            parsed = self.parse_zip_ode_response(converted_text) if processing_mode == "zip_ode_explain" else None

            if parsed:
                student_name  = parsed["student_name"]
                school_name   = parsed["school_name"]
                poem_title    = parsed["poem_title"]
                poem_theme    = parsed["poem_theme"]
                poem_language = parsed["poem_language"]
                zip_code      = parsed["zip_code"]
                meaningful_name = self.create_filename(
                    student_name, school_name, poem_title, poem_theme,
                    fallback_name=os.path.splitext(filename)[0],
                    zip_code=zip_code if zip_code and zip_code.isdigit() else None
                )
            else:
                # Fallback to legacy extractor for other modes
                info = self.extract_student_info_legacy(converted_text)
                student_name, school_name, poem_title, poem_theme, poem_language = info.student_name, info.school_name, info.poem_title, info.poem_theme, info.poem_language
                zip_code = ""
                meaningful_name = self.create_filename(
                    student_name, school_name, poem_title, poem_theme,
                    fallback_name=os.path.splitext(filename)[0],
                    zip_code=None
                )

            # Prepare result object
            result = {
                "filename": filename,
                "image_path": image_path,
                "converted_text": converted_text,
                "student_name": student_name,
                "school_name": school_name,
                "zip_code": zip_code,
                "poem_title": poem_title,
                "poem_theme": poem_theme,
                "poem_language": poem_language,
                "parsed": parsed if parsed else {},
                "saved_as": f"{meaningful_name}.txt",
                "processed_at": datetime.now(timezone.utc).isoformat()
            }
            results.append(result)
            
            # Save individual text file with meaningful name
            text_filename = f"{meaningful_name}.txt"
            text_path = os.path.join(output_directory, text_filename)
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(converted_text)
            
            # Also save a JSON sidecar with parsed fields and validation (handy for QA)
            json_sidecar = f"{meaningful_name}.json"
            json_path = os.path.join(output_directory, json_sidecar)
            with open(json_path, 'w', encoding='utf-8') as jf:
                json.dump(result, jf, indent=2, ensure_ascii=False)
    
                logging.info(f"  Saved as: {text_filename} (+ {json_sidecar})")
            
        # Save batch results as JSON
        output_path = os.path.join(output_directory, output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
            
        logging.info(f"\nBatch processing completed. Results saved to {output_path}")
        logging.info(f"Created {len(results)} text files with meaningful names")
        return results

# -----------------------------
# Main
# -----------------------------
def main():
    upload_dir = os.environ.get('UPLOAD_DIRECTORY', os.getcwd())
    output_dir = os.environ.get('OUTPUT_DIRECTORY', os.getcwd())
    
    # Use parent directory as base for security validation
    base_dir = os.path.dirname(upload_dir) if upload_dir != os.getcwd() else os.getcwd()
    processor = BatchImageProcessor(base_dir)
    # Process all images in the directory with the new mode
    results = processor.process_directory(upload_dir, output_dir, processing_mode="zip_ode_explain")
    
    logging.info(f"Successfully processed {len(results)} images")


if __name__ == "__main__":
    main()