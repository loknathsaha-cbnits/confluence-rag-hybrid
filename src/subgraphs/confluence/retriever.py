import os
import json
import pickle
from typing import List, Dict, Any
from dotenv import load_dotenv
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer
from flashrank import Ranker, RerankRequest

# Load environment configuration
load_dotenv()

HF_WRITE_TOKEN = os.getenv("HF_WRITE_TOKEN")
DATASET_NAME = os.getenv("DATASET_NAME")
HF_USERNAME = os.getenv("HF_USERNAME")
PINECONE_API_KEY=os.getenv("PINECONE_API_KEY")
INDEX_NAME=os.getenv("PINECONE_INDEX_NAME")

class HybridRetrieverEngine:
    def __init__(self, hf_corpus_path: str = "data/upload/bm25_corpus.json", bm25_index_path: str = "data/upload/bm25_index.pkl"):
        # 1. Initialize Embedding Model for Dense Vector Path
        self.encoder = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        
        # 2. Connect to Pinecone Control Plane
        self.pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        self.index = self.pc.Index(os.getenv("PINECONE_INDEX_NAME"))
        
        # 3. Load Local/Downloaded BM25 Index Components
        with open(bm25_index_path, 'rb') as f:
            self.bm25 = pickle.load(f)
        with open(hf_corpus_path, 'r', encoding='utf-8') as f:
            self.corpus = json.load(f)
            
        # 4. Initialize Lightweight Local Cross-Encoder Reranker
        # Defaults to the high-performance ~4MB 'ms-marco-MiniLM-L-4-v2' model
        self.reranker = Ranker()

    def _tokenize_query(self, query: str) -> List[str]:
        """Ensures query text features are evaluated cleanly by BM25 lexers."""
        import re
        return re.sub(r'[^\w\s]', ' ', query.lower()).split()

    def reciprocal_rank_fusion(self, dense_results: List[Dict], sparse_results: List[Dict], k: int = 60) -> List[Dict]:
        """
        Applies Reciprocal Rank Fusion math to combine independent rank metrics
        into a unified, balanced list.
        """
        rrf_scores = {}
        document_lookup = {}

        # Process Vector DB rankings
        for rank, hit in enumerate(dense_results, start=1):
            chunk_id = hit["id"]
            document_lookup[chunk_id] = {
                "id": chunk_id,
                "title": hit["metadata"].get("title"),
                "section": hit["metadata"].get("section"),
                "text": hit["metadata"].get("text"),
                "url": hit["metadata"].get("url")
            }
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + (1.0 / (k + rank))

        # Process Lexical BM25 rankings
        for rank, hit in enumerate(sparse_results, start=1):
            chunk_id = hit["chunk_id"]
            if chunk_id not in document_lookup:
                document_lookup[chunk_id] = {
                    "id": chunk_id,
                    "title": hit["metadata"].get("title"),
                    "section": hit["metadata"].get("section"),
                    "text": hit["indexable_text"],
                    "url": hit["metadata"].get("url")
                }
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + (1.0 / (k + rank))

        # Sort document pointers by final accumulated RRF values descending
        sorted_docs = sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)
        
        return [document_lookup[doc_id] for doc_id, _ in sorted_docs]

    def search(self, query: str, top_n: int = 20, final_k: int = 4) -> List[Dict[str, Any]]:
        """
        Executes the entire hybrid retrieval and cross-encoder reranking pipeline.
        """
        # --- PHASE 1: PARALLEL BROAD RETRIEVAL ---
        # Dense Query
        query_vector = self.encoder.encode(query).tolist()
        pinecone_res = self.index.query(vector=query_vector, top_k=top_n, include_metadata=True)
        dense_hits = pinecone_res.get("matches", [])
        
        # Sparse Query
        tokenized_query = self._tokenize_query(query)
        # Fetch matching objects directly using rank_bm25 API metrics
        sparse_hits = self.bm25.get_top_documents(tokenized_query, self.corpus, n=top_n)

        # --- PHASE 2: RANK FUSION ---
        fused_candidates = self.reciprocal_rank_fusion(dense_hits, sparse_hits, k=60)
        
        # Trim list slightly to optimize reranker processing speeds
        rerank_candidates = fused_candidates[:top_n]

        # --- PHASE 3: CROSS-ENCODER RERANKING ---
        # Format payloads for FlashRank expectations
        passages = [
            {"id": doc["id"], "text": doc["text"], "meta": {"title": doc["title"], "section": doc["section"], "url": doc["url"]}}
            for doc in rerank_candidates
        ]
        
        rerank_request = RerankRequest(query=query, passages=passages)
        reranked_results = self.reranker.rerank(rerank_request)

        # --- PHASE 4: EXTRACT TOP K FINALS ---
        final_context_chunks = []
        for item in reranked_results[:final_k]:
            final_context_chunks.append({
                "chunk_id": item["id"],
                "score": round(item["score"], 4),
                "title": item["meta"]["title"],
                "section": item["meta"]["section"],
                "url": item["meta"]["url"],
                "text": item["text"]
            })

        return final_context_chunks

# --- Local Verification Check ---
if __name__ == "__main__":
    # Ensure you pass correct directory paths where files reside
    try:
        retriever = HybridRetrieverEngine()
        user_query = "How can I check connection status for GlobalProtect client on Linux distributed endpoints?"
        
        results = retriever.search(query=user_query, top_n=15, final_k=3)
        
        print(f"\n=== TOP {len(results)} GROUNDED CHUNKS RETURNED ===")
        print(json.dumps(results, indent=2))
    except Exception as e:
        print(f"Initialization skipped or missing files: {e}")