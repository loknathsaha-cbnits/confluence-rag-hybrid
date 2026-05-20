import os
import json
import pickle
from typing import List, Dict, Any
from typing_extensions import TypedDict
from dotenv import load_dotenv

from pinecone import Pinecone
from sentence_transformers import SentenceTransformer
from flashrank import Ranker, RerankRequest
from langgraph.graph import StateGraph, START, END

from src.graph.state import DataSource, SourceState, State

# Load environment configuration
load_dotenv()


class HybridRetrieverEngine:
    def __init__(self, hf_corpus_path: str = "data/upload/bm25_corpus.json", bm25_index_path: str = "data/upload/bm25_index.pkl"):
        self.encoder = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        self.pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        self.index = self.pc.Index(os.getenv("PINECONE_INDEX_NAME"))
        
        with open(bm25_index_path, 'rb') as f:
            self.bm25 = pickle.load(f)
        with open(hf_corpus_path, 'r', encoding='utf-8') as f:
            self.corpus = json.load(f)
            
        self.reranker = Ranker()

    def _tokenize_query(self, query: str) -> List[str]:
        import re
        return re.sub(r'[^\w\s]', ' ', query.lower()).split()

    def reciprocal_rank_fusion(self, dense_results: List[Dict], sparse_results: List[Dict], k: int = 60) -> List[Dict]:
        rrf_scores = {}
        document_lookup = {}

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

        sorted_docs = sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)
        return [document_lookup[doc_id] for doc_id, _ in sorted_docs]

    def search(self, query: str, top_n: int = 20, final_k: int = 4) -> List[Dict[str, Any]]:
        query_vector = self.encoder.encode(query).tolist()
        pinecone_res = self.index.query(vector=query_vector, top_k=top_n, include_metadata=True)
        dense_hits = pinecone_res.get("matches", [])
        
        tokenized_query = self._tokenize_query(query)
        sparse_hits = self.bm25.get_top_n(tokenized_query, self.corpus, n=top_n)

        fused_candidates = self.reciprocal_rank_fusion(dense_hits, sparse_hits, k=60)
        rerank_candidates = fused_candidates[:top_n]

        passages = [
            {"id": doc["id"], "text": doc["text"], "meta": {"title": doc["title"], "section": doc["section"], "url": doc["url"]}}
            for doc in rerank_candidates
        ]
        
        rerank_request = RerankRequest(query=query, passages=passages)
        reranked_results = self.reranker.rerank(rerank_request)

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


# This instantiates heavy models once at startup, rather than inside the node function.
try:
    retriever_engine = HybridRetrieverEngine()
except Exception as e:
    print(f"Engine initialization skipped (likely local files missing): {e}")
    retriever_engine = None


# ==========================================
# 4. THE LANGGRAPH FUNCTIONAL NODE
# ==========================================
def retriever_node(state: State) -> Dict[str, Any]:
    """
    LangGraph functional node. It extracts the query from the state,
    invokes the hybrid retriever engine, and updates the state's retrieved_results and sources.
    """
    user_query = state.get("query", "")
    print(f"[Node: Retriever] Running hybrid retrieval + FlashRank for: '{user_query}'")
    
    formatted_results: List[DataSource] = []
    formatted_sources: List[SourceState] = []

    # Fallback placeholder if files are missing locally during dev
    if retriever_engine is None:
        dummy_source = SourceState(
            title="Fallback Context",
            url="http://example.com",
            last_updated="Unknown"
        )
        dummy_data = DataSource(
            chunk_id="fallback_1",
            text_content="Fallback engine context. Please check your local index files.",
            score=1.0,
            source=dummy_source
        )
        formatted_results.append(dummy_data)
        formatted_sources.append(dummy_source)
    else:
        # Run pipeline
        raw_chunks = retriever_engine.search(query=user_query, top_n=15, final_k=3)

        print(raw_chunks)
        
        # Transform raw output into the Global State Schema
        for chunk in raw_chunks:
            source_info = SourceState(
                title=chunk.get("title", "Unknown"),
                url=chunk.get("url", "Unknown"),
                last_updated="Unknown"  # Add logic if you fetch dates from Confluence metadata
            )
            
            data_source = DataSource(
                chunk_id=chunk.get("chunk_id", ""),
                text_content=chunk.get("text", ""),
                score=float(chunk.get("score", 0.0)),
                source=source_info
            )
            
            formatted_results.append(data_source)
            formatted_sources.append(source_info)
        
    # Update the graph state with the typed lists
    return {
        "retrieved_results": formatted_results,
        "sources": formatted_sources
    }