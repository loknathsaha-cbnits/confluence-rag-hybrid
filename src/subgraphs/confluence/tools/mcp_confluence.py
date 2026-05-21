import os
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv()

async def get_atlassian_tools():
    DOMAIN = os.getenv("CONFLUENCE_DOMAIN")
    EMAIL = os.getenv("CONFLUENCE_EMAIL")
    TOKEN = os.getenv("CONFLUENCE_API_TOKEN")

    client = MultiServerMCPClient({
        "mcp-atlassian": {
            "command": "uvx",
            "args": ["mcp-atlassian"],
            "env": {
                "CONFLUENCE_URL": f"https://{DOMAIN}/wiki/",
                "CONFLUENCE_USERNAME": EMAIL,
                "CONFLUENCE_API_TOKEN": TOKEN
            }
        }
    })
    
    # Pre-fetch and convert MCP tools to LangChain tools
    langchain_tools = await client.get_tools()
    return langchain_tools, client