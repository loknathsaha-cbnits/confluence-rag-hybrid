import json
import os
import pickle
import re
from typing import List, Dict, Any
from rank_bm25 import BM25Okapi

class BM25Indexer:
    def __init__(self):
        pass

    def _tokenize(self, text: str) -> List[str]:
        """
        Preprocesses and tokenizes raw text. 
        Converts to lowercase and splits by words, ignoring special characters.
        """
        # Lowercase and strip punctuation/newlines
        cleaned_text = re.sub(r'[^\w\s]', ' ', text.lower())
        # Split into a clean list of individual word tokens
        return cleaned_text.split()

    def build_and_store_index(self, chunks_path: str, output_dir: str = "data"):
        """
        Loads chunks, tokenizes the text, constructs the BM25 state, 
        and stores the resulting index and metadata to disk.
        """
        if not os.path.exists(chunks_path):
            raise FileNotFoundError(f"Could not find chunks file at: {chunks_path}")

        # 1. Load your chunks from the JSON file
        print(f"Loading chunks from {chunks_path}...")
        with open(chunks_path, 'r', encoding='utf-8') as f:
            chunks = json.load(f)

        tokenized_corpus = []
        chunk_storage = []

        # 2. Tokenize the 'indexable_text' field for every chunk
        print("Tokenizing corpus and building inverted index structures...")
        for chunk in chunks:
            text_to_index = chunk["indexable_text"]
            tokens = self._tokenize(text_to_index)
            
            tokenized_corpus.append(tokens)
            # Store the full chunk object in a list that mirrors the tokenized index layout
            chunk_storage.append(chunk)

        # 3. Compile the Inverted Index & TF-IDF Weights
        print("Calculating BM25 term frequencies and global document weights...")
        bm25_instance = BM25Okapi(tokenized_corpus)

        # 4. Save/Store the artifacts into files
        os.makedirs(output_dir, exist_ok=True)
        index_file_path = os.path.join(output_dir, "bm25_index.pkl")
        corpus_file_path = os.path.join(output_dir, "bm25_corpus.json")

        print(f"Persisting BM25 binary index state to: {index_file_path}")
        with open(index_file_path, 'wb') as f:
            pickle.dump(bm25_instance, f)

        print(f"Persisting matching chunk text registry to: {corpus_file_path}")
        with open(corpus_file_path, 'w', encoding='utf-8') as f:
            json.dump(chunk_storage, f, indent=2)

        print("BM25 Indexing Pipeline Complete. Your sparse index is ready for retrieval.\n")


# --- Execution Pipeline ---
if __name__ == "__main__":
    # Path to the JSON chunks you saved earlier
    INPUT_CHUNKS = "data/confluence_chunks.json"
    
    # Quick mock file generation for demonstration if it doesn't exist
    if not os.path.exists(INPUT_CHUNKS):
        mock_data = [
            {
                "chunk_id": "819201_summary",
                "metadata": {"doc_id": "819201", "title": "API documentation", "section": "Summary"},
                "indexable_text": "Document Title: API documentation\nSection: Summary\n\nThe API Documentation section provides comprehensive technical resources for developers."
            }
        ]
        with open(INPUT_CHUNKS, 'w', encoding='utf-8') as f:
            json.dump(mock_data, f, indent=2)

    # Initialize and execute
    indexer = BM25Indexer()
    indexer.build_and_store_index(chunks_path=INPUT_CHUNKS)