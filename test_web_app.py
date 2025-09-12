import unittest
from unittest.mock import patch, MagicMock
import os
import json
from web_app import app, SessionManager
from student_info import StudentInfo
import io

class TestWebApp(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        
    @patch('web_app.secure_filename')
    def test_upload_image_invalid_filename(self, mock_secure_filename):
        mock_secure_filename.return_value = ''
        
        data = {'file': (io.BytesIO(b'test data'), 'test#image.jpg')}
        response = self.client.post('/upload_image', data=data)
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertIn('error', response_data)
        self.assertIn('filename', response_data['error'].lower())

    @patch.object(SessionManager, 'get_current_images')
    @patch.object(SessionManager, 'get_current_index')
    @patch('batch_processor.BatchImageProcessor')
    def test_convert_text(self, mock_processor_class, mock_get_index, mock_get_images):
        mock_get_images.return_value = ['/test/image.jpg']
        mock_get_index.return_value = 0
        
        mock_processor = MagicMock()
        mock_processor.convert_image_to_text.return_value = 'Test converted text\nConfidence: 8/10'
        mock_processor.extract_student_info_legacy.return_value = StudentInfo('John', 'School', 'Title', 'Theme', 'English')
        mock_processor_class.return_value = mock_processor
        
        response = self.client.post('/convert_text', json={
            'api_key': 'test_key', 
            'model': 'test_model', 
            'processing_mode': 'poem'
        })
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertIn('text', response_data)
        self.assertEqual(response_data['text'], 'Test converted text')
        
if __name__ == '__main__':
    unittest.main()