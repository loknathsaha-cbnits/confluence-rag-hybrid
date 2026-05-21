import os
from typing import Any, Dict
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import BaseTool
from src.graph.state import State

async def mcp_agent_node(state: State) -> Dict[str, Any]:
    user_query = state.get("query", "")
    print(f"[Node: MCP Agent] Activating open-source Atlassian writing loop...")
    
    # 1. Boot up our open-source MCP client
    client = MultiServerMCPClient({
        "mcp-atlassian": {
            "transport": "stdio",
            "command": "uvx",
            "args": ["mcp-atlassian"],
            "env": {
                "CONFLUENCE_URL": f"https://{os.getenv('CONFLUENCE_DOMAIN')}/wiki/",
                "CONFLUENCE_USERNAME": os.getenv("CONFLUENCE_EMAIL"),
                "CONFLUENCE_API_TOKEN": os.getenv("CONFLUENCE_API_TOKEN")
            }
        }
    })
    
    # 2. Get the tools and pass through our validation filter
    raw_mcp_tools = await client.get_tools()

    class SafeMCPToolWrapper(BaseTool):
        original_tool: Any = None

        def __init__(self, tool: Any):
            super().__init__(
                name=tool.name,
                description=tool.description,
                args_schema=tool.args_schema
            )
            self.original_tool = tool

        def _clean_args(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
            forbidden_keys = ["default_context", "run_manager", "config", "callbacks"]
            cleaned = {k: v for k, v in kwargs.items() if k not in forbidden_keys}
            
            # --- NEW: AUTO-CAST NUMERIC STRINGS TO INTEGERS ---
            # If the LLM sends "1" or "10" for a field that should be numeric, convert it!
            for key, value in cleaned.items():
                if isinstance(value, str) and value.isdigit():
                    # Fields like limit, parent_id (if purely numeric), etc.
                    if key in ["limit", "start", "max_results"]:
                        cleaned[key] = int(value)
                        
            return cleaned

        def _run(self, *args, **kwargs) -> Any:
            return self.original_tool.invoke(self._clean_args(kwargs), *args)

        async def _arun(self, *args, **kwargs) -> Any:
            return await self.original_tool.ainvoke(self._clean_args(kwargs), *args)
        
    mcp_tools = [SafeMCPToolWrapper(tool) for tool in raw_mcp_tools]
    
    # 3. Setup the Brain
    llm = ChatOpenAI(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.1, 
        base_url="https://api.groq.com/openai/v1"
    )
    
    # 4. Create the prebuilt tool-running agent loop
    mcp_executor = create_react_agent(llm, mcp_tools)
    
    past_answer_content = state.get("previous_answer", "").strip()
    print("\n--- [DEBUG 3: MCP AGENT NODE PROMPT BUILDING] ---")
    print(f"Extracted previous_answer: {repr(past_answer_content)}")
    print("-------------------------------------------------\n")
    if not past_answer_content or past_answer_content == "No prior summary text provided.":
        # Fallback safeguard in case the graph state state didn't pass down correctly
        past_answer_content = f"Summary overview for request: {user_query}"

    # 2. Re-architect the prompt with concrete boundaries separating instructions from data
    agent_prompt = (
    "SYSTEM MANDATE:\n"
    "You are an automated Atlassian data provisioner. Your sole task is to take the text provided in the "
    "DATA_BLOCK below and publish it cleanly to Confluence using your tools.\n\n"
    
    "CRITICAL CONFLUENCE IDEMPOTENCY RULES (PREVENT DUPLICATES):\n"
    "1. DO NOT blindly run 'confluence_create_page' first. You MUST inspect your available tools to see if a page "
    "with your target title already exists in the 'CKB' space.\n"
    "2. If you find a page with the exact same title already exists, or if a previous tool call failed with a 'title already exists' "
    "BadRequestException, you MUST dynamically alter your chosen title to make it completely unique. Append a short unique descriptive "
    "suffix or random tracker (e.g., instead of 'Summary', use 'Summary - GlobalProtect Documentation' or 'Summary - Info Context').\n"
    "3. Never attempt to create a page with a title that matches an existing page in space 'CKB'.\n\n"
    
    "CRITICAL TOOL SCHEMA RULES:\n"
    "1. For the 'content' parameter of 'confluence_create_page', copy the text inside the DATA_BLOCK verbatim. "
    "Do not truncate it, do not summarize it, and do not include system meta-phrases like 'The user wants to write...'. "
    "Use the raw text block content directly.\n"
    "2. The parameter 'enable_heading_anchors' MUST be a raw JSON boolean value (true or false). Do NOT put quotes around it.\n"
    "3. For ANY optional parameters like 'emoji', 'parent_id', 'labels', or 'description': If you do not have a specific value to provide, "
    "do NOT include those keys in your function call at all. Omit the keys completely from your JSON argument dictionary.\n"
    "4. Force the 'space_key' parameter to be exactly 'CKB'.\n\n"
    "5. All pagination, sizing, or counting parameters (such as 'limit', 'start', or 'max_results') MUST be passed as raw, naked integers (e.g., 1 or 5). Never wrap quotes around numbers when executing tool functions."
    
    "==================================================\n"
    "DATA_BLOCK (WRITE THIS ENTIRE CONTENT INTO THE PAGE BODY):\n"
    f"{past_answer_content}\n"
    "==================================================\n\n"
    
    f"USER DIRECTIVE: {user_query}\n\n"
    "EXECUTION INSTRUCTION:\n"
    "Begin by checking tool definitions, ensuring title uniqueness in the 'CKB' space, and then publish cleanly."
    )

    try:
        # Run the local loop natively
        agent_output = await mcp_executor.ainvoke({
            "messages": [("human", agent_prompt)]
        })
        
        # Extract the final textual response text from the agent loop
        final_answer = agent_output["messages"][-1].content
        print("[Node: MCP Agent] Modification actions executed successfully.")
        
    except Exception as execution_err:
        final_answer = f"⚠️ The Confluence tool execution failed: {str(execution_err)}"
        print(f"[Node: MCP Agent Error] Loop failure: {execution_err}")
    
    # 5. Build clean feedback elements for Chainlit
    created_sources = [{
        "title": "Confluence Workspace Link",
        "url": f"https://{os.getenv('CONFLUENCE_DOMAIN')}/wiki/spaces/CKB/overview",
        "last_updated": "Just Now"
    }]
    
    return {
        "current_answer": final_answer,
        "confidence_score": 1.0,
        "sources": created_sources
    }