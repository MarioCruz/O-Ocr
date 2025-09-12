import unittest
from unittest.mock import patch
import os
import json
from batch_processor import BatchImageProcessor
from student_info import StudentInfo

class TestBatchImageProcessor(unittest.TestCase):

    def setUp(self):
        os.environ['GROQ_API_KEY'] = "test"
        self.processor = BatchImageProcessor()
        self.test_dir = "test_images"
        os.makedirs(self.test_dir, exist_ok=True)
        self.test_image = os.path.join(self.test_dir, "test_image.jpg")
        with open(self.test_image, "w") as f:
            f.write("test")

    def tearDown(self):
        os.remove(self.test_image)
        os.rmdir(self.test_dir)

    def test_create_filename(self):
        student_name = "John Doe"
        school_name = "Test School"
        poem_title = "My Poem"
        poem_theme = "Nature"
        fallback_name = "fallback"
        zip_code = "12345"

        expected_filename = "Test_School_John_Doe_My_Poem_Nature_12345"
        actual_filename = self.processor.create_filename(student_name, school_name, poem_title, poem_theme, fallback_name, zip_code)
        self.assertEqual(actual_filename, expected_filename)

    @patch('batch_processor.BatchImageProcessor.convert_image_to_text')
    def test_convert_image_to_text(self, mock_convert_image_to_text):
        mock_convert_image_to_text.return_value = "test"
        text = self.processor.convert_image_to_text(self.test_image)
        self.assertEqual(text, "test")

    def test_parse_zip_ode_response(self):
        content = """STUDENT_NAME: John Doe
SCHOOL_NAME: Test School
ZIP_CODE: 12345
POEM_TITLE: My Poem
POEM_THEME: Nature
POEM_LANGUAGE: English
OVERALL_OK: True
TRANSCRIPTION:
This is a test poem.
ZIP_ODE_EXPLANATION: This is a test explanation.
POEM:
This is a test poem.
VALIDATION_TABLE:
Line | ExpectedWords | ActualWords | OK(true/false) | LineText
1 | 4 | 4 | true | This is a test poem.
OVERALL_OK: True
POEM_TITLE: My Poem
POEM_THEME: Nature
POEM_LANGUAGE: English
Confidence: 10/10
"""
        parsed = self.processor.parse_zip_ode_response(content)
        self.assertEqual(parsed["student_name"], "John Doe")
        self.assertEqual(parsed["school_name"], "Test School")
        self.assertEqual(parsed["zip_code"], "12345")
        self.assertEqual(parsed["poem_title"], "My Poem")
        self.assertEqual(parsed["poem_theme"], "Nature")
        self.assertEqual(parsed["poem_language"], "English")
        self.assertEqual(parsed["overall_ok"], "True")
        self.assertEqual(parsed["transcription"], "This is a test poem.")
        self.assertEqual(parsed["zip_ode_explanation"], "This is a test explanation.")
        self.assertEqual(parsed["poem_lines"], ["This is a test poem."])
        self.assertEqual(len(parsed["validation_rows"]), 1)