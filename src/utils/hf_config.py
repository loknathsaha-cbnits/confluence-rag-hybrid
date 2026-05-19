import os
from dotenv import load_dotenv
from huggingface_hub import HfApi, login, CommitOperationAdd

load_dotenv()

HF_WRITE_TOKEN = os.getenv("HF_WRITE_TOKEN")
DATASET_NAME = os.getenv("DATASET_NAME")
HF_USERNAME = os.getenv("HF_USERNAME")

def upload_bm25_to_hub(token: str, username: str, repo_name: str, local_folder: str = "data/upload"):
    """
    Creates a dataset repository on Hugging Face and uses an atomic commit operation
    to force-upload BM25 artifacts, bypassing local tracking caches.
    """
    if not os.path.exists(local_folder):
        raise FileNotFoundError(f"Could not find local folder: {local_folder}")

    # Verify that the essential files exist locally before attempting commit
    pkl_path = os.path.join(local_folder, "bm25_index.pkl")
    json_path = os.path.join(local_folder, "bm25_corpus.json")
    
    if not os.path.exists(pkl_path) or not os.path.exists(json_path):
        raise FileNotFoundError(
            f"Missing required BM25 files in '{local_folder}'. "
            f"Please ensure both 'bm25_index.pkl' and 'bm25_corpus.json' exist."
        )

    # 1. Authenticate with the Hugging Face Hub
    print("Authenticating with Hugging Face...")
    login(token)
    
    api = HfApi()
    repo_id = f"{username}/{repo_name}"

    # 2. Create the dataset repository (ignores if it already exists)
    print(f"Ensuring repository '{repo_id}' exists...")
    api.create_repo(
        repo_id=repo_id, 
        repo_type="dataset", 
        exist_ok=True,
        private=True 
    )

    # 3. Build an explicit commit operation to bypass caching checks completely
    print(f"Preparing direct asset sync operations for files inside '{local_folder}'...")
    operations = [
        CommitOperationAdd(
            path_in_repo="bm25_artifacts/bm25_index.pkl",
            path_or_fileobj=pkl_path
        ),
        CommitOperationAdd(
            path_in_repo="bm25_artifacts/bm25_corpus.json",
            path_or_fileobj=json_path
        )
    ]

    # 4. Push the forced commit operation to the remote repository
    print("Publishing atomic commit to the Hugging Face Hub...")
    api.create_commit(
        repo_id=repo_id,
        repo_type="dataset",
        operations=operations,
        commit_message="Forced re-indexing sync: Pushing fresh clean BM25 artifacts to cloud"
    )

    print(f"\nUpload complete! Your index has been force-overwritten and is live at:")
    print(f"https://huggingface.co/datasets/{repo_id}/tree/main/bm25_artifacts")

# --- Execution ---
if __name__ == "__main__":
    upload_bm25_to_hub(
        token=HF_WRITE_TOKEN,
        username=HF_USERNAME,
        repo_name=DATASET_NAME
    )