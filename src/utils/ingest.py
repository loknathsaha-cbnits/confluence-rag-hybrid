import json
import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load credentials from .env file
load_dotenv()

DOMAIN = os.getenv("CONFLUENCE_DOMAIN")
EMAIL = os.getenv("CONFLUENCE_EMAIL")
TOKEN = os.getenv("CONFLUENCE_API_TOKEN")
SPACE_KEY = "CKB"

BASE_URL = f"https://{DOMAIN}/wiki/rest/api"
AUTH = (EMAIL, TOKEN)
HEADERS = {"Accept": "application/json"}

def clean_confluence_html(html_content: str) -> str:
    """
    Parses raw Confluence XHTML, strips out noisy macro containers,
    and returns a clean, text-heavy version suitable for an LLM.
    """
    if not html_content:
        return ""
    
    soup = BeautifulSoup(html_content, "html.parser")
    
    # 1. Handle Tables: Convert HTML tables into basic text rows 
    # so the structural layout isn't completely broken during chunking
    for table in soup.find_all("table"):
        table_text = []
        for row in table.find_all("tr"):
            cells = [cell.get_text(strip=True) for cell in row.find_all(["td", "th"])]
            table_text.append(" | ".join(cells))
        # Replace the HTML table element with a plain-text markdown-ish block
        table.replace_with("\n" + "\n".join(table_text) + "\n")

    # 2. Extract text from the cleaned soup
    # This automatically discards remaining structural tags like <ac:...> macros
    clean_text = soup.get_text(separator="\n")
    
    # 3. Clean up excessive whitespace and blank lines
    lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
    return "\n".join(lines)

def fetch_all_pages():
    pages_extracted = []
    limit = 50
    start = 0
    has_more = True

    print("🚀 Starting Confluence Data Extraction...")

    while has_more:
        endpoint = f"{BASE_URL}/content"          # ✅ v1 endpoint
        params = {
            "spaceKey": SPACE_KEY,
            "type": "page",
            "limit": limit,
            "start": start,
            "expand": "body.storage,version",     # ✅ v1 expand
        }

        response = requests.get(endpoint, auth=AUTH, headers=HEADERS, params=params)

        if response.status_code != 200:
            print(f"❌ Failed. Status: {response.status_code}")
            print(response.text[:300])
            break

        data = response.json()
        results = data.get("results", [])

        for page in results:
            page_id = page.get("id")
            title = page.get("title")
            web_ui_link = page.get("_links", {}).get("webui", "")
            full_url = f"https://{DOMAIN}/wiki" + web_ui_link
            last_updated = page.get("version", {}).get("when", "Unknown")
            raw_body = page.get("body", {}).get("storage", {}).get("value", "")
            cleaned_text = clean_confluence_html(raw_body)

            pages_extracted.append({
                "id": page_id,
                "title": title,
                "url": full_url,
                "last_updated": last_updated,
                "content": cleaned_text,
            })
            print(f"  ✅ '{title}' (ID: {page_id})")

        total = data.get("totalSize", 0)
        start += limit
        if start >= total:
            has_more = False

    print(f"\n✅ Done! Extracted {len(pages_extracted)} pages.")
    return pages_extracted

if __name__ == "__main__":
    extracted_docs = fetch_all_pages()

    with open("confluence_pages.json", "w", encoding="utf-8") as f:
        json.dump(extracted_docs, f, indent=2, ensure_ascii=False)
    
    print(f"Saved {len(extracted_docs)} successfully")
    
    # Look at the first page output to verify the cleaning quality
    if extracted_docs:
        print("\n--- SAMPLE OUTPUT (First Extracted Page) ---")
        print(f"Title: {extracted_docs[0]['title']}")
        print(f"URL: {extracted_docs[0]['url']}")
        print(f"Content Snippet:\n{extracted_docs[0]['content'][:400]}...")