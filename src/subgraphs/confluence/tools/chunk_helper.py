import json
import re
import os
from typing import List, Dict, Any

def chunk_confluence_pages(file_path: str, max_words_heading: int = 5) -> List[Dict[str, Any]]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file path '{file_path}' does not exist.")

    with open(file_path, 'r', encoding='utf-8') as f:
        documents = json.load(f)
        
    if isinstance(documents, dict):
        documents = [documents]
        
    all_processed_chunks = []
    
    for doc in documents:
        doc_id = doc.get("id", "unknown_id")
        title = doc.get("title", "Untitled Document")
        url = doc.get("url", "")
        last_updated = doc.get("last_updated", "")
        content = doc.get("content", "")
        
        # Split and filter out empty lines to look ahead accurately
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        sections = {}
        current_header = "Overview"
        sections[current_header] = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            word_count = len(line.split())
            
            # Lookahead check: Is this line short, AND is the next line a long content block?
            is_probably_header = word_count < max_words_heading
            has_next_line = (i + 1) < len(lines)
            
            if is_probably_header and has_next_line:
                next_line_word_count = len(lines[i + 1].split())
                
                # If the next line is long content, this line is definitely a valid section header
                if next_line_word_count >= max_words_heading:
                    current_header = line
                    if current_header not in sections:
                        sections[current_header] = []
                    i += 1  # Move past the header line
                    continue

            # If it's noise data (like 'wide' or '760') or regular body text, accumulate it
            sections[current_header].append(lines[i])
            i += 1
                
        # Build the final chunks
        for section_name, content_lines in sections.items():
            section_body = "\n".join(content_lines).strip()
            
            if not section_body:
                continue
                
            # --- FIXED FOR PINECONE ASCII COMPLIANCE ---
            # 1. Normalize smart quotes/apostrophes to straight equivalents or remove them
            safe_section = section_name.lower().replace("’", "").replace("'", "")
            # 2. Replace spaces and hyphens with underscores
            safe_section = safe_section.replace(" ", "_").replace("-", "_")
            # 3. Strip out any remaining non-ASCII/non-alphanumeric characters using regex
            safe_section = re.sub(r'[^a-z0-9_]', '', safe_section)
            # 4. Clean up any trailing/double underscores for cosmetic neatness
            safe_section = re.sub(r'_+', '_', safe_section).strip('_')
            
            # Fallback if the header was purely emojis or special characters
            if not safe_section:
                safe_section = "section"
                
            chunk_id = f"{doc_id}_{safe_section}"
            # -------------------------------------------
                
            indexable_text = (
                f"Document Title: {title}\n"
                f"Section: {section_name}\n\n"
                f"{section_body}"
            )
            
            chunk = {
                "chunk_id": chunk_id, # Safely scrubbed for Pinecone's ID validation
                "metadata": {
                    "doc_id": doc_id,
                    "title": title,
                    "url": url,
                    "last_updated": last_updated,
                    "section": section_name # Keep the raw human-readable header here!
                },
                "indexable_text": indexable_text
            }
            all_processed_chunks.append(chunk)           
    return all_processed_chunks


# --- Run Execution and Print Verification Results ---
if __name__ == "__main__":
    # Setup mock file directory structure for test demonstration if file doesn't exist
    os.makedirs("data", exist_ok=True)
    mock_path = "data/confluence_pages.json"
    
    if not os.path.exists(mock_path):
        # Fallback to write the target structured file sample for testing execution flow
        sample_data = [{
            "id": "196743",
            "title": "How to Deploy GlobalProtect on Linux",
            "url": "https://cbnits-team-eh0i70zr.atlassian.net/wiki/spaces/CKB/pages/196743/How+to+Deploy+GlobalProtect+on+Linux",
            "last_updated": "2026-02-17T10:52:07.392Z",
            "content": "Summary\nDeploying GlobalProtect on Linux enables secure remote access for Linux endpoints using the CLI-based GlobalProtect agent.\nDeployment Steps\nDownload the appropriate GlobalProtect Linux package from the firewall or support portal. Install the package using the distribution’s package manager.\nValidation Tips\nConfirm DNS resolution, certificate trust, and network reachability before testing."
        }]
        with open(mock_path, 'w', encoding='utf-8') as f:
            json.dump(sample_data, f, indent=2)

    # Execute chunking function on the data directory
    resulting_chunks = chunk_confluence_pages(mock_path)
    with open("data/confluence_chunks.json", "w", encoding="utf-8") as f:
        json.dump(resulting_chunks, f, indent=2, ensure_ascii=False)
    
    print(f"Saved {len(resulting_chunks)} successfully")
    
    # Clean Print Output
    print(f"=== Chunking Complete: Generated {len(resulting_chunks)} chunks from source ===")
    print(json.dumps(resulting_chunks, indent=2))