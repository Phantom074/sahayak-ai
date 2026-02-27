"""
Document Processor — Ingests government scheme documents into OpenSearch.
Supports PDF, HTML, and structured JSON scheme data.
Chunks documents with overlap for better retrieval context.
"""
import boto3
import json
import hashlib
import logging
import os
import uuid
from dataclasses import dataclass
from typing import List, Dict, Optional
import re

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    chunk_id: str
    scheme_id: str
    scheme_name: str
    text_en: str
    text_hi: Optional[str]
    chunk_index: int
    total_chunks: int
    source_url: str
    eligible_states: List[str]
    eligible_occupations: List[str]
    categories: List[str]
    last_updated: str


class DocumentProcessor:
    """
    Processes and chunks scheme documents for OpenSearch indexing.
    
    Chunking strategy: 
    - Chunk size: 512 tokens (~400 words)
    - Overlap: 64 tokens (~50 words) for context continuity
    - Boundary: sentence-aware splitting
    """

    CHUNK_SIZE = 400  # words
    CHUNK_OVERLAP = 50  # words
    S3_BUCKET = os.environ.get("SCHEMES_BUCKET", "sahayak-scheme-documents")

    def __init__(self):
        self.s3 = boto3.client("s3", region_name="ap-south-1")
        self.bedrock = boto3.client("bedrock-runtime", region_name="ap-south-1")
        self.translate = boto3.client("translate", region_name="ap-south-1")

    def process_scheme_document(self, scheme_metadata: Dict, document_text: str) -> List[DocumentChunk]:
        """
        Process a scheme document into indexed chunks.
        
        Args:
            scheme_metadata: Scheme metadata dict (name, id, ministry, etc.)
            document_text: Raw text content of the scheme document
            
        Returns:
            List of DocumentChunks ready for OpenSearch indexing
        """
        # Clean and normalize text
        cleaned_text = self._clean_text(document_text)

        # Split into semantic chunks
        raw_chunks = self._semantic_chunk(cleaned_text)

        chunks = []
        for i, chunk_text in enumerate(raw_chunks):
            # Translate to Hindi if not already bilingual
            text_hi = self._translate_to_hindi(chunk_text) if scheme_metadata.get("translate_hi") else None

            chunk = DocumentChunk(
                chunk_id=f"{scheme_metadata['scheme_id']}-chunk-{i:04d}",
                scheme_id=scheme_metadata["scheme_id"],
                scheme_name=scheme_metadata["name_en"],
                text_en=chunk_text,
                text_hi=text_hi,
                chunk_index=i,
                total_chunks=len(raw_chunks),
                source_url=scheme_metadata.get("source_url", ""),
                eligible_states=scheme_metadata.get("eligible_states", ["ALL"]),
                eligible_occupations=scheme_metadata.get("eligible_occupations", ["ALL"]),
                categories=scheme_metadata.get("categories", []),
                last_updated=scheme_metadata.get("last_verified", ""),
            )
            chunks.append(chunk)

        logger.info(f"Processed {len(chunks)} chunks for scheme: {scheme_metadata['scheme_id']}")
        return chunks

    def _clean_text(self, text: str) -> str:
        """Remove noise, normalize whitespace, fix encoding issues."""
        # Remove excessive whitespace
        text = re.sub(r"\s+", " ", text)
        # Remove page numbers, headers common in PDFs
        text = re.sub(r"\bPage \d+ of \d+\b", "", text, flags=re.IGNORECASE)
        # Normalize Hindi punctuation
        text = text.replace("।।", "।").strip()
        return text

    def _semantic_chunk(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks at sentence boundaries.
        Preserves semantic context across chunk boundaries.
        """
        # Split on sentence endings (English and Hindi)
        sentences = re.split(r"(?<=[.!?।])\s+", text)
        
        chunks = []
        current_words = []
        current_word_count = 0

        for sentence in sentences:
            sentence_words = sentence.split()
            sentence_word_count = len(sentence_words)

            if current_word_count + sentence_word_count > self.CHUNK_SIZE and current_words:
                chunks.append(" ".join(current_words))
                # Keep overlap for context continuity
                overlap_words = current_words[-self.CHUNK_OVERLAP:]
                current_words = overlap_words + sentence_words
                current_word_count = len(current_words)
            else:
                current_words.extend(sentence_words)
                current_word_count += sentence_word_count

        if current_words:
            chunks.append(" ".join(current_words))

        return chunks if chunks else [text]

    def _translate_to_hindi(self, text: str) -> Optional[str]:
        """Translate English text to Hindi using Amazon Translate."""
        try:
            # Only translate reasonably-sized chunks
            if len(text) > 5000:
                text = text[:5000]
                
            response = self.translate.translate_text(
                Text=text,
                SourceLanguageCode="en",
                TargetLanguageCode="hi",
            )
            return response["TranslatedText"]
        except Exception as e:
            logger.warning(f"Translation failed: {e}")
            return None

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for multiple texts (serial, as Bedrock has no batch API)."""
        embeddings = []
        for text in texts:
            response = self.bedrock.invoke_model(
                modelId="amazon.titan-embed-text-v2:0",
                body=json.dumps({
                    "inputText": text[:8000],
                    "dimensions": 1536,
                    "normalize": True,
                }),
            )
            embedding = json.loads(response["body"].read())["embedding"]
            embeddings.append(embedding)
        return embeddings
