"""
Hybrid Retriever — Semantic + Keyword search with Reciprocal Rank Fusion.
OpenSearch KNN (vector) + BM25 (keyword) → RRF fusion → top-k results.
Target: < 200ms retrieval latency at P95.
"""
import boto3
import json
import hashlib
import logging
import os
from dataclasses import dataclass
from typing import List, Optional, Dict
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    chunk_id: str
    scheme_id: str
    scheme_name: str
    text: str
    score: float
    source_url: str
    retrieval_method: str = "hybrid"


class HybridRetriever:
    """
    Production RAG retriever. Combines dense (semantic) and sparse (BM25)
    retrieval via Reciprocal Rank Fusion for best recall.
    """

    INDEX_NAME = "sahayak-schemes-v2"
    EMBEDDING_MODEL = "amazon.titan-embed-text-v2:0"

    def __init__(self):
        self.bedrock = boto3.client("bedrock-runtime", region_name="ap-south-1")
        self.opensearch = self._init_opensearch()
        self._embedding_cache: Dict[str, List[float]] = {}

    def _init_opensearch(self) -> OpenSearch:
        credentials = boto3.Session().get_credentials().get_frozen_credentials()
        awsauth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            "ap-south-1",
            "es",
            session_token=credentials.token,
        )
        return OpenSearch(
            hosts=[{"host": os.environ.get("OPENSEARCH_ENDPOINT", "localhost"), "port": 443}],
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=10,
            max_retries=2,
        )

    def get_embeddings(self, text: str) -> List[float]:
        """Generate Titan Embeddings V2 (1536-dim, multilingual)."""
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]

        response = self.bedrock.invoke_model(
            modelId=self.EMBEDDING_MODEL,
            body=json.dumps({
                "inputText": text[:8000],  # Titan V2 limit
                "dimensions": 1536,
                "normalize": True,
            }),
        )
        embedding = json.loads(response["body"].read())["embedding"]
        self._embedding_cache[cache_key] = embedding
        return embedding

    def semantic_search(
        self, query_embedding: List[float], top_k: int = 20, filters: Optional[Dict] = None
    ) -> List[Dict]:
        """KNN vector search."""
        knn_query = {"knn": {"embedding_vector": {"vector": query_embedding, "k": top_k}}}

        if filters:
            query_body = {
                "query": {
                    "bool": {
                        "must": [knn_query],
                        "filter": [{"terms": {k: v}} for k, v in filters.items()],
                    }
                }
            }
        else:
            query_body = {"query": knn_query}

        response = self.opensearch.search(
            index=self.INDEX_NAME, body={**query_body, "size": top_k}
        )
        return response["hits"]["hits"]

    def keyword_search(self, query: str, top_k: int = 20, filters: Optional[Dict] = None) -> List[Dict]:
        """BM25 multi-field full-text search."""
        must_clauses = [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["text_en^1.5", "text_hi^2.0", "scheme_name^3.0"],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                    "prefix_length": 2,
                }
            }
        ]
        if filters:
            query_body = {
                "query": {"bool": {"must": must_clauses, "filter": [{"terms": {k: v}} for k, v in filters.items()]}}
            }
        else:
            query_body = {"query": {"bool": {"must": must_clauses}}}

        response = self.opensearch.search(index=self.INDEX_NAME, body={**query_body, "size": top_k})
        return response["hits"]["hits"]

    def hybrid_retrieve(
        self,
        query: str,
        language: str = "hi",
        user_context: Optional[Dict] = None,
        top_k: int = 5,
    ) -> List[RetrievalResult]:
        """
        Full hybrid retrieval pipeline:
        1. Parallel semantic + keyword search
        2. Reciprocal Rank Fusion
        3. Return top-k results
        """
        filters = self._build_filters(user_context)

        # Get embeddings and run both searches
        query_embedding = self.get_embeddings(query)
        semantic_hits = self.semantic_search(query_embedding, top_k=20, filters=filters)
        keyword_hits = self.keyword_search(query, top_k=20, filters=filters)

        # Reciprocal Rank Fusion
        k = 60  # Standard RRF constant
        fused_scores: Dict[str, float] = {}

        for rank, hit in enumerate(semantic_hits):
            doc_id = hit["_id"]
            fused_scores[doc_id] = fused_scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)

        for rank, hit in enumerate(keyword_hits):
            doc_id = hit["_id"]
            fused_scores[doc_id] = fused_scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)

        # Collect all unique hits
        all_hits = {hit["_id"]: hit for hit in semantic_hits + keyword_hits}

        # Sort by fused score
        sorted_ids = sorted(fused_scores, key=lambda x: fused_scores[x], reverse=True)

        results = []
        for doc_id in sorted_ids[:top_k]:
            if doc_id in all_hits:
                source = all_hits[doc_id]["_source"]
                text_field = "text_hi" if language == "hi" and source.get("text_hi") else "text_en"
                results.append(
                    RetrievalResult(
                        chunk_id=source.get("chunk_id", doc_id),
                        scheme_id=source.get("scheme_id", ""),
                        scheme_name=source.get("scheme_name", ""),
                        text=source.get(text_field, source.get("text_en", "")),
                        score=round(fused_scores[doc_id], 6),
                        source_url=source.get("source_url", ""),
                    )
                )

        logger.info(f"Retrieved {len(results)} chunks: semantic={len(semantic_hits)}, keyword={len(keyword_hits)}")
        return results

    def _build_filters(self, user_context: Optional[Dict]) -> Optional[Dict]:
        if not user_context:
            return None
        filters = {}
        if user_context.get("state"):
            filters["eligible_states"] = [user_context["state"], "ALL"]
        if user_context.get("occupation"):
            filters["eligible_occupations"] = [user_context["occupation"], "ALL"]
        return filters if filters else None
