import requests
from requests.auth import HTTPBasicAuth
import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# ── Configuration ────────────────────────────────────────────────
load_dotenv()

DOMAIN = os.getenv("CONFLUENCE_DOMAIN")
EMAIL = os.getenv("CONFLUENCE_EMAIL")
TOKEN = os.getenv("CONFLUENCE_API_TOKEN")
SPACE_KEY = "CKB"   # from your URL: .../spaces/CKB/...

BASE_URL = f"https://{DOMAIN}/wiki/rest/api"
auth     = HTTPBasicAuth(EMAIL, TOKEN)
headers  = {"Accept": "application/json"}

# Test: fetch your own profile
response = requests.get(
    f"https://{DOMAIN}/wiki/rest/api/user/current",
    headers=headers,
    auth=auth
)


print("Status:", response.status_code)
print("Body:",   response.json())

# ── Fetch all pages (handles pagination) ─────────────────────────
# def get_all_pages_in_space(space_key: str) -> list[dict]:
#     url   = f"{BASE_URL}/content"
#     pages = []
#     start = 0
#     limit = 50

#     while True:
#         params = {
#             "spaceKey": space_key,
#             "type":     "page",
#             "start":    start,
#             "limit":    limit,
#             "expand":   "body.storage,version,ancestors",
#         }

#         response = requests.get(url, headers=headers, auth=auth, params=params)
#         response.raise_for_status()
#         data = response.json()

#         results = data["results"]
#         pages.extend(results)
#         print(f"  Fetched {start + len(results)} / {data['totalSize']} pages...")

#         # Stop when we've collected everything
#         if start + limit >= data["totalSize"]:
#             break
#         start += limit

#     return pages


# # ── Run ───────────────────────────────────────────────────────────
# if __name__ == "__main__":
    # print(f"Fetching all pages from space: {SPACE_KEY}\n")
    # pages = get_all_pages_in_space(SPACE_KEY)

    # print(f"\nTotal pages fetched: {len(pages)}\n")
    # print(f"{'ID':<12} {'VERSION':<10} {'TITLE'}")
    # print("-" * 60)

    # for page in pages:
    #     pid     = page["id"]
    #     version = page["version"]["number"]
    #     title   = page["title"]
    #     print(f"{pid:<12} {version:<10} {title}")