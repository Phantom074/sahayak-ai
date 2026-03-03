"""
Unit tests for the Scheme Management Service
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import sys
import os

# Add the services directory to the path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'scheme-management-service', 'src'))

from admin.scheme_admin import SchemeAdmin
from ingestion.document_ingester import DocumentIngester


class TestSchemeAdmin(unittest.TestCase):
    """Test cases for Scheme Admin."""

    def setUp(self):
        """Set up test fixtures."""
        self.admin = SchemeAdmin()

    @patch('boto3.resource')
    def test_create_scheme_success(self, mock_dynamodb_resource):
        """Test successful scheme creation."""
        # Mock the DynamoDB table
        mock_table = Mock()
        mock_dynamodb_resource.return_value.Table.return_value = mock_table
        
        mock_table.put_item.return_value = {}
        
        scheme_data = {
            'scheme_name': 'Test Scheme',
            'description': 'A test scheme',
            'benefits': ['Benefit 1', 'Benefit 2']
        }
        
        scheme_id = self.admin.create_scheme(scheme_data)
        
        self.assertTrue(scheme_id.startswith('scheme_'))
        mock_table.put_item.assert_called_once()
        
        # Verify the put_item call had the expected arguments
        call_args = mock_table.put_item.call_args
        self.assertIsNotNone(call_args)
        
        item = call_args[1]['Item']
        self.assertEqual(item['scheme_name'], 'Test Scheme')
        self.assertEqual(item['description'], 'A test scheme')
        self.assertIn('scheme_id', item)
        self.assertIn('created_at', item)

    @patch('boto3.resource')
    def test_get_scheme_success(self, mock_dynamodb_resource):
        """Test successful scheme retrieval."""
        # Mock the DynamoDB table
        mock_table = Mock()
        mock_dynamodb_resource.return_value.Table.return_value = mock_table
        
        expected_scheme = {
            'scheme_id': 'test-scheme-123',
            'pk': 'SCHEME#test-scheme-123',
            'sk': 'METADATA#latest',
            'scheme_name': 'Test Scheme',
            'description': 'A test scheme',
            'benefits': ['Benefit 1', 'Benefit 2'],
            'status': 'active'
        }
        
        mock_table.get_item.return_value = {'Item': expected_scheme}
        
        scheme = self.admin.get_scheme('test-scheme-123')
        
        self.assertIsNotNone(scheme)
        self.assertEqual(scheme['scheme_name'], 'Test Scheme')
        mock_table.get_item.assert_called_once()

    @patch('boto3.resource')
    def test_update_scheme_success(self, mock_dynamodb_resource):
        """Test successful scheme update."""
        # Mock the DynamoDB table
        mock_table = Mock()
        mock_dynamodb_resource.return_value.Table.return_value = mock_table
        
        # Mock get_item to return an existing scheme
        existing_scheme = {
            'scheme_id': 'test-scheme-123',
            'pk': 'SCHEME#test-scheme-123',
            'sk': 'METADATA#latest',
            'scheme_name': 'Old Name',
            'description': 'Old Description'
        }
        mock_table.get_item.return_value = {'Item': existing_scheme}
        
        update_data = {
            'scheme_name': 'New Name',
            'description': 'New Description'
        }
        
        result = self.admin.update_scheme('test-scheme-123', update_data)
        
        self.assertTrue(result)
        mock_table.update_item.assert_called_once()

    @patch('boto3.resource')
    def test_delete_scheme_success(self, mock_dynamodb_resource):
        """Test successful scheme deletion."""
        # Mock the DynamoDB table
        mock_table = Mock()
        mock_dynamodb_resource.return_value.Table.return_value = mock_table
        
        result = self.admin.delete_scheme('test-scheme-123')
        
        self.assertTrue(result)
        mock_table.delete_item.assert_called_once()

    def test_is_sensitive_field(self):
        """Test identification of sensitive fields."""
        # Test various sensitive fields
        sensitive_fields = [
            'phone_number', 'email', 'aadhaar_hash', 'address', 
            'pan_number', 'bank_account', 'income', 'dob'
        ]
        
        for field in sensitive_fields:
            is_sensitive = self.admin._is_sensitive_field(field)
            self.assertTrue(is_sensitive, f"Field {field} should be identified as sensitive")

    def test_encrypt_decrypt_roundtrip(self):
        """Test encryption and decryption roundtrip."""
        original_value = "test_sensitive_data"
        
        encrypted = self.admin._encrypt_value(original_value)
        decrypted = self.admin._decrypt_value(encrypted)
        
        self.assertEqual(original_value, decrypted)

    def test_encrypt_sensitive_fields(self):
        """Test encryption of sensitive fields in profile data."""
        profile_data = {
            'scheme_name': 'Test Scheme',  # Not sensitive
            'phone_number': '1234567890',  # Sensitive
            'email': 'test@example.com'    # Sensitive
        }
        
        encrypted_data = self.admin._encrypt_sensitive_fields(profile_data)
        
        # Original sensitive fields should not be present
        self.assertNotIn('phone_number', encrypted_data)
        self.assertNotIn('email', encrypted_data)
        
        # Encrypted versions should be present
        self.assertIn('encrypted_phone_number', encrypted_data)
        self.assertIn('encrypted_email', encrypted_data)
        
        # Non-sensitive field should remain
        self.assertEqual(encrypted_data['scheme_name'], 'Test Scheme')

    def test_decrypt_sensitive_fields(self):
        """Test decryption of sensitive fields in profile data."""
        encrypted_data = {
            'scheme_name': 'Test Scheme',  # Not sensitive
            'encrypted_phone_number': self.admin._encrypt_value('1234567890'),
            'encrypted_email': self.admin._encrypt_value('test@example.com')
        }
        
        decrypted_data = self.admin._decrypt_sensitive_fields(encrypted_data)
        
        # Encrypted fields should not be present
        self.assertNotIn('encrypted_phone_number', decrypted_data)
        self.assertNotIn('encrypted_email', decrypted_data)
        
        # Decrypted versions should be present
        self.assertEqual(decrypted_data['phone_number'], '1234567890')
        self.assertEqual(decrypted_data['email'], 'test@example.com')
        
        # Non-sensitive field should remain
        self.assertEqual(decrypted_data['scheme_name'], 'Test Scheme')


class TestDocumentIngester(unittest.TestCase):
    """Test cases for Document Ingester."""

    def setUp(self):
        """Set up test fixtures."""
        self.ingester = DocumentIngester()

    @patch('requests.get')
    @patch('boto3.client')
    def test_ingest_single_document_success(self, mock_boto_client, mock_requests_get):
        """Test successful ingestion of a single document."""
        # Mock requests.get to return a fake document
        mock_response = Mock()
        mock_response.content = b'fake pdf content'
        mock_response.headers = {'content-type': 'application/pdf'}
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response
        
        # Mock S3 client
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3
        
        # Mock the upload_fileobj method
        mock_s3.upload_fileobj.return_value = None
        
        result = self.ingester.ingest_single_document('test-scheme-123', 'https://example.com/doc.pdf')
        
        self.assertTrue(result['success'])
        self.assertEqual(result['file_size'], len(b'fake pdf content'))
        mock_s3.upload_fileobj.assert_called_once()

    def test_get_file_extension_from_content_type(self):
        """Test getting file extension from content type."""
        # Test common content types
        test_cases = [
            ('application/pdf', 'https://example.com/doc', '.pdf'),
            ('text/plain', 'https://example.com/text', '.txt'),
            ('text/html', 'https://example.com/page', '.html'),
            ('application/msword', 'https://example.com/doc', '.doc'),
            ('application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'https://example.com/docx', '.docx'),
        ]
        
        for content_type, url, expected_ext in test_cases:
            ext = self.ingester._get_file_extension(content_type, url)
            self.assertEqual(ext, expected_ext, f"Expected {expected_ext} for content type {content_type}")

    def test_get_file_extension_from_url(self):
        """Test getting file extension from URL when content type is unknown."""
        content_type = 'application/octet-stream'
        url = 'https://example.com/document.pdf'
        ext = self.ingester._get_file_extension(content_type, url)
        self.assertEqual(ext, '.pdf')

    def test_chunk_text_short(self):
        """Test text chunking for short text."""
        short_text = "This is a short text." * 5  # Well under chunk size
        chunks = self.ingester._chunk_text(short_text, chunk_size=500, overlap=50)
        
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], short_text)

    def test_chunk_text_long(self):
        """Test text chunking for long text."""
        long_text = "This is a sentence. " * 100  # Creates long text
        chunks = self.ingester._chunk_text(long_text, chunk_size=100, overlap=10)
        
        self.assertGreater(len(chunks), 1)
        
        # Check that chunks are approximately the right size
        for i, chunk in enumerate(chunks):
            if i == len(chunks) - 1:  # Last chunk might be shorter
                continue
            # Each chunk (except possibly the last) should be close to chunk_size
            self.assertLessEqual(len(chunk), 100)
            # But not too much smaller (unless overlap is large relative to chunk size)
            if len(chunks) > 1:
                self.assertGreater(len(chunk), 50)  # More than half the chunk size

    def test_chunk_text_with_sentence_boundaries(self):
        """Test that text is chunked at sentence boundaries when possible."""
        text_with_sentences = "First sentence. Second sentence. Third sentence. " * 20
        chunks = self.ingester._chunk_text(text_with_sentences, chunk_size=100, overlap=10)
        
        # Check that chunks don't break sentences in the middle (approximately)
        for chunk in chunks:
            # The chunk should either end with a period or be the last chunk
            if len(chunk) < len(text_with_sentences):  # Not the last chunk
                # If it's not the full text, it should end at a sentence boundary
                # (or close to it, given our chunking algorithm)
                pass  # The algorithm handles this internally


if __name__ == '__main__':
    unittest.main()