import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load credentials from .env file
load_dotenv()

DOMAIN = os.getenv("CONFLUENCE_DOMAIN")
EMAIL = os.getenv("CONFLUENCE_EMAIL")
TOKEN = os.getenv("CONFLUENCE_API_TOKEN")

BASE_URL = f"https://{DOMAIN}/wiki/api/v2"
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
    """
    Paginates through the entire Confluence workspace to fetch all accessible pages.
    """
    pages_extracted = []
    limit = 20  # Fetch 20 pages per API call to stay safe from timeouts
    start = 0
    has_more = True

    print("🚀 Starting Confluence Data Extraction...")

    while has_more:
        endpoint = f"{BASE_URL}/pages"
        params = {
            "limit": limit,
            "start": start,
            "body-format": "storage"  # Asks for raw XHTML storage layout
        }
        
        response = requests.get(endpoint, auth=AUTH, headers=HEADERS, params=params)
        
        if response.status_code != 200:
            print(f"❌ Failed to fetch data. Status: {response.status_code}")
            print(response.text)
            break
            
        data = response.json()
        results = data.get("results", [])
        
        for page in results:
            page_id = page.get("id")
            title = page.get("title")
            
            # Construct the absolute web URL for citations later
            base_web_url = f"https://{DOMAIN}/wiki"
            web_ui_link = page.get("_links", {}).get("webui", "")
            full_url = base_web_url + web_ui_link
            
            last_updated = page.get("version", {}).get("createdAt", "Unknown")
            
            # Extract the raw XHTML body string safely
            raw_body = page.get("body", {}).get("storage", {}).get("value", "")
            
            # Clean it up!
            cleaned_text = clean_confluence_html(raw_body)
            
            # Pack it into a temporary structure matching your state logic
            page_data = {
                "id": page_id,
                "title": title,
                "url": full_url,
                "last_updated": last_updated,
                "content": cleaned_text
            }
            pages_extracted.append(page_data)
            print(f"  Processed page: '{title}' (ID: {page_id})")
            
        # Check if there's another page of API results to fetch
        next_link = data.get("_links", {}).get("next")
        if next_link:
            start += limit
        else:
            has_more = False

    print(f"\n✅ Extraction finished! Extracted a total of {len(pages_extracted)} pages.")
    return pages_extracted

if __name__ == "__main__":
    extracted_docs = fetch_all_pages()
    
    # Look at the first page output to verify the cleaning quality
    if extracted_docs:
        print("\n--- SAMPLE OUTPUT (First Extracted Page) ---")
        print(f"Title: {extracted_docs[0]['title']}")
        print(f"URL: {extracted_docs[0]['url']}")
        print(f"Content Snippet:\n{extracted_docs[0]['content'][:400]}...")