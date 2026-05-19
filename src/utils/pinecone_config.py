import json
import os
from pinecone import Pinecone, ServerlessSpec

class PineconeIngestor:
    def __init__(self, api_key: str, index_name: str, dimension: int = 384):
        """
        Initializes the Pinecone client and creates the index if it doesn't exist.
        (384 is the dimension size for 'all-MiniLM-L6-v2').
        """
        print("Connecting to Pinecone...")
        # Initialize the modern Pinecone client
        self.pc = Pinecone(api_key=api_key)
        self.index_name = index_name

        # Check if the index exists, if not, create a serverless index
        if not self.pc.has_index(index_name):
            print(f"Index '{index_name}' not found. Creating it now...")
            self.pc.create_index(
                name=index_name,
                dimension=dimension,
                metric="cosine", # Cosine similarity is standard for text embeddings
                spec=ServerlessSpec(
                    cloud="aws",
                    region="us-east-1" # Update this to your preferred free-tier region
                )
            )
            print("Index created successfully.")
        
        # Connect to the target index
        self.index = self.pc.Index(index_name)
        print(f"Successfully connected to index: {index_name}\n")

    def upsert_vectors(self, embedded_records: list, batch_size: int = 100):
        """
        Maps our custom data structure to Pinecone's required schema and upserts it.
        """
        pinecone_payloads = []

        for record in embedded_records:
            # Flatten our 'payload' into a single 'metadata' dictionary for Pinecone
            metadata = record["payload"]["metadata"]
            metadata["text"] = record["payload"]["text"] # Crucial: Storing text so the LLM can read it

            # Build the exact dictionary Pinecone expects
            pinecone_vector = {
                "id": record["id"],
                "values": record["vector"],
                "metadata": metadata
            }
            pinecone_payloads.append(pinecone_vector)

        # Upsert in batches to avoid network timeouts on large datasets
        print(f"Upserting {len(pinecone_payloads)} vectors in batches of {batch_size}...")
        
        # Pinecone's upsert method handles the batching internally via the batch_size arg
        self.index.upsert(vectors=pinecone_payloads, batch_size=batch_size)
        
        print("Upsert complete! Your data is now live in Pinecone.")


# --- Execution ---
if __name__ == "__main__":
    # 1. Provide your credentials (best practice: load from .env)
    PINECONE_API_KEY = "your-pinecone-api-key-here"
    INDEX_NAME = "confluence-rag-index"
    
    # 2. Load the embedded chunks we created in the last step
    file_path = 'embedded_chunks.json' # Adjust to wherever you saved the embedder output
    
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            embedded_data = json.load(f)
            
        # 3. Initialize and run ingestion
        ingestor = PineconeIngestor(api_key=PINECONE_API_KEY, index_name=INDEX_NAME)
        ingestor.upsert_vectors(embedded_data)
    else:
        print(f"Error: Could not find '{file_path}'. Run the embedding script first.")