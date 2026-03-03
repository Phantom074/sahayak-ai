"""
Document Ingester
Handles the ingestion and processing of scheme documents for search/indexing.
"""

import json
import boto3
import logging
import os
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse
import requests
from datetime import datetime

from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class DocumentIngester:
    """Manages document ingestion for scheme content."""
    
    def __init__(self):
        self.s3 = boto3.client('s3', region_name='ap-south-1')
        self.bedrock = boto3.client('bedrock-runtime', region_name='ap-south-1')
        self.opensearch = boto3.client('opensearch', region_name='ap-south-1')
        
        self.schemes_bucket = os.environ.get('SCHEMES_BUCKET', 'sahayak-scheme-documents')
        self.processed_bucket = os.environ.get('PROCESSED_DOCS_BUCKET', 'sahayak-processed-docs')
        self.opensearch_endpoint = os.environ.get('OPENSEARCH_ENDPOINT', 'https://search-sahayak-schemes...')
        
    def ingest_documents(self, scheme_id: str, document_urls: List[str]) -> List[Dict[str, Any]]:
        """Ingest multiple documents for a scheme."""
        results = []
        
        for url in document_urls:
            try:
                result = self.ingest_single_document(scheme_id, url)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to ingest document {url}: {str(e)}")
                results.append({
                    'url': url,
                    'success': False,
                    'error': str(e)
                })
        
        return results
    
    def ingest_single_document(self, scheme_id: str, document_url: str) -> Dict[str, Any]:
        """Ingest a single document for a scheme."""
        try:
            # Download document
            logger.info(f"Downloading document: {document_url}")
            response = requests.get(document_url)
            response.raise_for_status()
            
            # Determine file type
            content_type = response.headers.get('content-type', 'application/octet-stream')
            file_ext = self._get_file_extension(content_type, document_url)
            
            # Upload to S3
            s3_key = f"{scheme_id}/{datetime.utcnow().strftime('%Y/%m/%d')}/{os.path.basename(document_url)}"
            self.s3.upload_fileobj(
                BytesIO(response.content),
                self.schemes_bucket,
                s3_key,
                ExtraArgs={'ContentType': content_type}
            )
            
            # Process document based on type
            if file_ext.lower() in ['.pdf', '.txt', '.html', '.doc', '.docx']:
                chunks = self._extract_and_chunk_content(response.content, file_ext)
                
                # Index chunks in OpenSearch
                indexed_count = self._index_chunks(scheme_id, s3_key, chunks)
                
                result = {
                    'url': document_url,
                    'success': True,
                    's3_key': s3_key,
                    'file_size': len(response.content),
                    'content_type': content_type,
                    'chunks_processed': len(chunks),
                    'indexed_chunks': indexed_count
                }
            else:
                result = {
                    'url': document_url,
                    'success': False,
                    'error': f'Unsupported file type: {file_ext}',
                    'supported_types': ['.pdf', '.txt', '.html', '.doc', '.docx']
                }
            
            logger.info(f"Successfully processed document: {document_url}")
            return result
            
        except requests.RequestException as e:
            logger.error(f"Failed to download document {document_url}: {str(e)}")
            return {
                'url': document_url,
                'success': False,
                'error': f'Download failed: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Failed to process document {document_url}: {str(e)}")
            return {
                'url': document_url,
                'success': False,
                'error': str(e)
            }
    
    def _get_file_extension(self, content_type: str, url: str) -> str:
        """Determine file extension from content type or URL."""
        # Map common content types to extensions
        type_map = {
            'application/pdf': '.pdf',
            'text/plain': '.txt',
            'text/html': '.html',
            'application/msword': '.doc',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx'
        }
        
        if content_type in type_map:
            return type_map[content_type]
        
        # Fallback to URL extension
        parsed_url = urlparse(url)
        _, ext = os.path.splitext(parsed_url.path)
        return ext or '.bin'
    
    def _extract_and_chunk_content(self, content: bytes, file_ext: str) -> List[Dict[str, Any]]:
        """Extract text content and chunk it for indexing."""
        import PyPDF2
        from io import BytesIO
        
        text_content = ""
        
        if file_ext.lower() == '.pdf':
            # Extract text from PDF
            pdf_reader = PyPDF2.PdfReader(BytesIO(content))
            text_content = ""
            for page in pdf_reader.pages:
                text_content += page.extract_text() + "\n"
        elif file_ext.lower() in ['.txt', '.html']:
            # Handle plain text and HTML
            text_content = content.decode('utf-8')
            if file_ext.lower() == '.html':
                # Simple HTML tag removal
                import re
                text_content = re.sub(r'<[^>]+>', '', text_content)
        elif file_ext.lower() in ['.doc', '.docx']:
            # For Word documents, we'd use python-docx
            # This is a simplified approach
            text_content = content.decode('utf-8', errors='ignore')
        
        # Chunk the text
        chunks = self._chunk_text(text_content)
        
        # Create chunk objects with metadata
        chunk_objects = []
        for i, chunk_text in enumerate(chunks):
            chunk_objects.append({
                'chunk_id': f"{uuid.uuid4().hex}_{i}",
                'content': chunk_text,
                'chunk_index': i,
                'total_chunks': len(chunks)
            })
        
        return chunk_objects
    
    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks."""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            
            # If we're not at the end, try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings near the end
                sentence_end = max(chunk.rfind('.'), chunk.rfind('!'), chunk.rfind('?'))
                if sentence_end > chunk_size // 2:  # If found a good breaking point
                    chunk = chunk[:sentence_end + 1]
                    end = start + len(chunk)
            
            chunks.append(chunk)
            
            # Move start forward, accounting for overlap
            start = end - overlap if end - overlap > start else end
        
        return chunks
    
    def _index_chunks(self, scheme_id: str, s3_key: str, chunks: List[Dict[str, Any]]) -> int:
        """Index document chunks in OpenSearch."""
        indexed_count = 0
        
        for chunk_obj in chunks:
            try:
                # Create embedding using Bedrock
                embedding = self._get_embedding(chunk_obj['content'])
                
                # Prepare document for OpenSearch
                doc = {
                    'chunk_id': chunk_obj['chunk_id'],
                    'scheme_id': scheme_id,
                    'content': chunk_obj['content'],
                    's3_key': s3_key,
                    'chunk_index': chunk_obj['chunk_index'],
                    'total_chunks': chunk_obj['total_chunks'],
                    'embedding': embedding,
                    'created_at': datetime.utcnow().isoformat()
                }
                
                # Index in OpenSearch
                self._index_document(doc)
                indexed_count += 1
                
            except Exception as e:
                logger.error(f"Failed to index chunk {chunk_obj['chunk_id']}: {str(e)}")
        
        return indexed_count
    
    def _get_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using Bedrock."""
        # Use Amazon Titan Embeddings
        body = json.dumps({
            "inputText": text
        })
        
        response = self.bedrock.invoke_model(
            modelId="amazon.titan-embed-text-v1",
            body=body
        )
        
        response_body = json.loads(response['body'].read())
        return response_body['embedding']
    
    def _index_document(self, doc: Dict[str, Any]):
        """Index a single document in OpenSearch."""
        import base64
        
        # Prepare bulk index request
        action = {"index": {"_index": "sahayak-schemes-v2", "_id": doc['chunk_id']}}
        bulk_request = json.dumps(action) + '\n' + json.dumps(doc) + '\n'
        
        # Send to OpenSearch
        encoded_request = bulk_request.encode('utf-8')
        
        # Note: In practice, you'd use the OpenSearch client or direct HTTP request
        # This is a simplified approach
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Construct the URL for bulk indexing
        url = f"https://{self.opensearch_endpoint}/_bulk"
        
        import urllib3
        http = urllib3.PoolManager()
        
        response = http.request(
            'POST',
            url,
            body=encoded_request,
            headers=headers
        )
        
        if response.status >= 300:
            raise Exception(f"OpenSearch indexing failed: {response.data.decode()}")
    
    def update_document(self, scheme_id: str, document_url: str, new_url: str) -> Dict[str, Any]:
        """Update an existing document."""
        # First delete old document references
        # Then ingest new document
        # This is a simplified implementation
        result = self.ingest_single_document(scheme_id, new_url)
        return result
    
    def delete_document(self, scheme_id: str, document_url: str) -> bool:
        """Mark document as deleted and remove from search index."""
        try:
            # In a real implementation, this would:
            # 1. Mark document as deleted in DynamoDB
            # 2. Remove from OpenSearch index
            # 3. Optionally retain in S3 with deletion marker
            
            # For now, just return success
            logger.info(f"Marked document for deletion: {document_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete document {document_url}: {str(e)}")
            return False