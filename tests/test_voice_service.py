"""
Unit tests for the Voice Service
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import sys
import os

# Add the services directory to the path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'voice-service', 'src'))

from handlers.stt_handler import STTHandler, TranscriptionResult
from handlers.tts_handler import TTSHandler, SynthesisResult
from processors.language_detector import LanguageDetector


class TestSTTHandler(unittest.TestCase):
    """Test cases for STT Handler."""

    def setUp(self):
        """Set up test fixtures."""
        self.stt_handler = STTHandler()

    @patch('boto3.client')
    def test_transcribe_audio_success(self, mock_boto_client):
        """Test successful audio transcription."""
        # Mock the transcribe client
        mock_transcribe = Mock()
        mock_boto_client.return_value = mock_transcribe
        
        mock_transcribe.start_transcription_job.return_value = None
        mock_transcribe.get_transcription_job.return_value = {
            'TranscriptionJob': {
                'TranscriptionJobStatus': 'COMPLETED',
                'LanguageCode': 'hi-IN',
                'IdentifiedLanguageScore': 0.95
            }
        }
        
        # Mock the S3 client to return a transcript
        mock_s3 = Mock()
        mock_boto_client.side_effect = lambda service, **kwargs: mock_s3 if service == 's3' else mock_transcribe
        
        mock_s3.get_object.return_value = {
            'Body': Mock(read=Mock(return_value=json.dumps({
                'results': {
                    'transcripts': [{'transcript': 'नमस्ते, यह एक परीक्षण है'}]
                }
            }).encode()))
        }
        
        # Test the transcribe_audio method
        result = self.stt_handler.transcribe_audio(
            s3_key='test/audio.webm',
            language_hint='auto',
            media_format='webm',
            channel='web'
        )
        
        self.assertIsInstance(result, TranscriptionResult)
        self.assertEqual(result.language_code, 'hi-IN')
        self.assertEqual(result.transcript, 'नमस्ते, यह एक परीक्षण है')

    def test_detect_language_heuristic_hindi(self):
        """Test language detection heuristic for Hindi."""
        text_with_devanagari = "नमस्ते, यह एक परीक्षण है"
        result = self.stt_handler.detect_language_heuristic(text_with_devanagari)
        self.assertEqual(result, 'hi')

    def test_detect_language_heuristic_english(self):
        """Test language detection heuristic for English."""
        text_without_devanagari = "Hello, this is a test"
        result = self.stt_handler.detect_language_heuristic(text_without_devanagari)
        self.assertEqual(result, 'en')


class TestTTSHandler(unittest.TestCase):
    """Test cases for TTS Handler."""

    def setUp(self):
        """Set up test fixtures."""
        self.tts_handler = TTSHandler()

    @patch('boto3.client')
    def test_synthesize_success(self, mock_boto_client):
        """Test successful text synthesis."""
        # Mock the polly client
        mock_polly = Mock()
        mock_boto_client.return_value = mock_polly
        
        mock_polly.start_speech_synthesis_task.return_value = {
            'SynthesisTask': {
                'TaskId': 'test-task-id'
            }
        }
        
        # Mock the S3 client
        mock_s3 = Mock()
        mock_boto_client.side_effect = lambda service, **kwargs: mock_s3 if service == 's3' else mock_polly
        
        mock_s3.generate_presigned_url.return_value = 'https://example.com/test.mp3'
        
        # Test the synthesize method
        result = self.tts_handler.synthesize(
            text='नमस्ते, यह एक परीक्षण है',
            language='hi',
            session_id='test-session'
        )
        
        self.assertIsInstance(result, SynthesisResult)
        self.assertIn('.mp3', result.presigned_url)

    def test_chunk_text_short(self):
        """Test text chunking for short text."""
        short_text = "This is a short text."
        chunks = self.tts_handler._chunk_text(short_text)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], short_text)

    def test_chunk_text_long(self):
        """Test text chunking for long text."""
        long_text = "This is a very long text. " * 100  # Exceeds MAX_POLLY_CHARS
        chunks = self.tts_handler._chunk_text(long_text)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLess(len(chunk), self.tts_handler.MAX_POLLY_CHARS)


class TestLanguageDetector(unittest.TestCase):
    """Test cases for Language Detector."""

    def setUp(self):
        """Set up test fixtures."""
        self.detector = LanguageDetector()

    def test_detect_language_hindi(self):
        """Test language detection for Hindi text."""
        text = "नमस्ते, यह एक परीक्षण है"
        result = self.detector.detect_language(text)
        self.assertEqual(result, 'hi')

    def test_detect_language_english(self):
        """Test language detection for English text."""
        text = "Hello, this is a test"
        result = self.detector.detect_language(text)
        self.assertEqual(result, 'en')

    def test_detect_language_mixed(self):
        """Test language detection for mixed language text."""
        text = "Hello नमस्ते world"
        result = self.detector.detect_language(text)
        # Should detect based on majority script or first significant script
        self.assertIn(result, ['hi', 'en'])


if __name__ == '__main__':
    unittest.main()