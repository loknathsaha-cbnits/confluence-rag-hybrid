import json
import os
from typing import List, Dict, Any
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer
import os
from dotenv import load_dotenv

load_dotenv()

PINECONE_API_KEY=os.getenv("PINECONE_API_KEY")
INDEX_NAME=os.getenv("PINECONE_INDEX_NAME")

class VectorEmbedder:
    def __init__(self, model_name: str = 'sentence-transformers/all-MiniLM-L6-v2'):
        """
        Initializes the embedding model. This model converts our contextualized 
        indexable_text into a 384-dimensional dense vector.
        """
        print(f"Loading embedding model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        print("Model loaded successfully.\n")

    def embed_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Takes the dynamically generated chunks, passes the indexable_text through 
        the embedding model, and formats the output for a Vector Database.
        """
        vector_db_payloads = []

        for chunk in chunks:
            # 1. Extract the text we want to convert to math
            text_to_embed = chunk["indexable_text"]

            # 2. Generate the embedding vector
            # We convert the numpy array to a standard Python list for JSON serialization
            embedding_vector = self.model.encode(text_to_embed).tolist()

            # 3. Restructure for standard Vector DB insertion (Qdrant, Milvus, Pinecone, etc.)
            db_record = {
                "id": chunk["chunk_id"],
                "vector": embedding_vector,
                "payload": {
                    "metadata": chunk["metadata"],
                    "text": chunk["indexable_text"]
                }
            }
            
            vector_db_payloads.append(db_record)

        return vector_db_payloads

    def setup_pinecone(self, api_key: str, index_name: str, dimension: int = 384):
        """
        Initializes the Pinecone client and creates the index if it doesn't exist.
        """
        print("Connecting to Pinecone...")
        self.pc = Pinecone(api_key=api_key)
        self.index_name = index_name

        # Check if the index exists, create if not
        if not self.pc.has_index(index_name):
            print(f"Index '{index_name}' not found. Creating a new serverless index...")
            self.pc.create_index(
                name=index_name,
                dimension=dimension,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region="us-east-1" # Update this to your preferred region if needed
                )
            )
            print("Index created successfully.")
        else:
            print(f"Index '{index_name}' found.")
            
        self.index = self.pc.Index(index_name)
        print("Pinecone setup complete.\n")

    def upsert_to_pinecone(self, embedded_records: list, batch_size: int = 100):
        """
        Formats the embedded records for Pinecone's schema and upserts them in batches.
        """
        pinecone_payloads = []

        for record in embedded_records:
            # Flatten the payload into a single metadata dictionary
            metadata = record["payload"]["metadata"]
            metadata["text"] = record["payload"]["text"]

            pinecone_vector = {
                "id": record["id"],
                "values": record["vector"],
                "metadata": metadata
            }
            pinecone_payloads.append(pinecone_vector)

        print(f"Upserting {len(pinecone_payloads)} vectors to Pinecone in batches of {batch_size}...")
        self.index.upsert(vectors=pinecone_payloads, batch_size=batch_size)
        print("Upsert complete! Your data is live.")


# --- Execution and Verification ---
if __name__ == "__main__":
    print("Started Embeddings...")

    CHUNKS_FILE_PATH = "data/confluence_chunks.json"
    
    if not os.path.exists(CHUNKS_FILE_PATH):
        print(f"Error: Could not find {CHUNKS_FILE_PATH}. Please ensure your chunker script ran successfully.")
    else:
        print(f"Started Embeddings for file: {CHUNKS_FILE_PATH}...")

        # 1. Load the actual chunks from your JSON file
        with open(CHUNKS_FILE_PATH, 'r', encoding='utf-8') as f:
            all_chunks = json.load(f)

    # 3. The streamlined Pipeline
    embedder = VectorEmbedder()
    
    # Step A: Embed the chunks
    embedded_data = embedder.embed_chunks(all_chunks)
    
    # Step B: Connect to Pinecone
    embedder.setup_pinecone(api_key=PINECONE_API_KEY, index_name=INDEX_NAME)
    
    # Step C: Send the data straight to the database
    embedder.upsert_to_pinecone(embedded_data)

    for record in embedded_data:
        # Create a display copy to truncate the 384 floats so it doesn't flood your console
        display_record = record.copy()
        vec_length = len(display_record["vector"])
        first_few = [round(v, 4) for v in display_record["vector"][:3]]
        
        display_record["vector"] = f"[{first_few[0]}, {first_few[1]}, {first_few[2]}, ... ({vec_length} dimensions total)]"
        
        print(json.dumps(display_record, indent=2))
        print("-" * 60)