from datetime import datetime
import os
import uuid
import re
from typing import Any, Dict
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import BaseTool
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage
from src.graph.state import State

def _check_page_creation_success(tool_name: str, tool_result: str) -> bool:
    """Detect if confluence_create_page succeeded."""
    if tool_name != "confluence_create_page":
        return False
    if not tool_result:
        return False
    result_lower = str(tool_result).lower()
    return (
        "success" in result_lower or
        "created" in result_lower or
        "page_id" in result_lower or
        ("error" not in result_lower and len(tool_result) > 10)
    )


class SafeMCPToolWrapper(BaseTool):
    """Wrapper to clean and validate MCP tool arguments."""
    original_tool: Any = None

    def __init__(self, tool: Any):
        super().__init__(
            name=tool.name,
            description=tool.description,
            args_schema=tool.args_schema
        )
        self.original_tool = tool

    def _clean_args(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        forbidden_keys = ["default_context", "run_manager", "config", "callbacks", "ctx", "context", "self"]
        cleaned = {k: v for k, v in kwargs.items() if k not in forbidden_keys}
        cleaned = {k: v for k, v in cleaned.items() if v is not None}

        for key, value in cleaned.items():
            if isinstance(value, str) and value.isdigit():
                if key in ["limit", "start", "max_results", "parent_id", "page_id"]:
                    cleaned[key] = int(value)

        print(f"[DEBUG SafeMCPToolWrapper] Tool: {self.original_tool.name}")
        print(f"[DEBUG SafeMCPToolWrapper] Cleaned kwargs: {list(cleaned.keys())}")
        return cleaned

    def _run(self, *args, **kwargs) -> Any:
        return self.original_tool.invoke(self._clean_args(kwargs), *args)

    async def _arun(self, *args, **kwargs) -> Any:
        return await self.original_tool.ainvoke(self._clean_args(kwargs), *args)


async def _direct_file_path(state: State, transcript: str, client: Any, llm: ChatOpenAI) -> Dict[str, Any]:
    """
    Fast path: File attached (transcript exists)
    - LLM formats the transcript
    - Directly call confluence_create_page tool (no ReAct agent)
    - Generate response summary
    """
    print("\n[mcp_agent_node] Routing to DIRECT FILE PATH")
    print("\n[DEBUG] === DIRECT FILE PATH START ===")

    # 1. Fetch and wrap tools
    print("[DEBUG STEP 1] Fetching MCP tools...")
    raw_mcp_tools = await client.get_tools()
    ALLOWED_TOOLS = {"confluence_create_page"}
    filtered_tools = [t for t in raw_mcp_tools if t.name in ALLOWED_TOOLS]
    print(f"[DEBUG STEP 1] ✓ Got {len(filtered_tools)} tools")

    create_page_tool = SafeMCPToolWrapper(filtered_tools[0]) if filtered_tools else None
    if not create_page_tool:
        return {
            "current_answer": "⚠️ confluence_create_page tool not available",
            "page_created": False,
            "confidence_score": 0.0,
            "sources": []
        }

    # 2. Use LLM to format transcript into page content
    print("[DEBUG STEP 2] Formatting transcript with LLM...")
    format_prompt = (
        "You are a professional meeting document formatter. "
        "Structure the following meeting transcript into a clean Confluence page with these sections:\n"
        "**Attendees**, **Agenda**, **Action Items**, **Decisions Made**, **Notes**.\n"
        "Extract relevant content into each section. Omit sections with no content. "
        "Use clear formatting and bullet points.\n\n"
        f"TRANSCRIPT:\n{'='*60}\n{transcript[:2000]}\n{'='*60}\n\n"
        "Return ONLY the formatted page content, ready for Confluence."
    )

    format_msg = await llm.ainvoke([
        {"role": "system", "content": "You are a professional document formatter."},
        {"role": "user", "content": format_prompt}
    ])
    formatted_content = format_msg.content
    print(f"[DEBUG STEP 2] ✓ Content formatted, length: {len(formatted_content)} chars")

    # 3. Generate unique title with UUID
    print("[DEBUG STEP 3] Generating unique page title...")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    unique_suffix = str(uuid.uuid4())[:8].upper()
    page_title = f"Meeting Notes - {timestamp} [{unique_suffix}]"
    print(f"[DEBUG STEP 3] ✓ Title: {page_title}")

    # 4. Call confluence_create_page directly
    print("[DEBUG STEP 4] Calling confluence_create_page tool directly...")
    try:
        tool_result = await create_page_tool._arun(
            space_key="CKB",
            title=page_title,
            content=formatted_content,
            enable_heading_anchors=True
        )
        print(f"[DEBUG STEP 4] ✓ Tool call returned")
        print(f"[DEBUG STEP 4] Result: {str(tool_result)[:200]}")

        page_created = _check_page_creation_success("confluence_create_page", str(tool_result))

        # Extract page ID
        created_page_id = None
        if page_created and "page_id" in str(tool_result).lower():
            match = re.search(r'page_id["\s:]*(\d+)', str(tool_result), re.IGNORECASE)
            if match:
                created_page_id = match.group(1)
                print(f"[DEBUG STEP 4] Extracted page_id: {created_page_id}")

        final_answer = str(tool_result)

    except Exception as tool_err:
        print(f"[DEBUG STEP 4] ✗ Tool call failed: {tool_err}")
        page_created = False
        created_page_id = None
        final_answer = f"⚠️ Tool execution failed: {str(tool_err)}"

    # 5. Generate response summary from transcript
    print("[DEBUG STEP 5] Generating response summary...")
    generated_response = None
    if page_created:
        try:
            response_llm = ChatOpenAI(
                model="llama-3.3-70b-versatile",
                api_key=os.getenv("GROQ_API_KEY"),
                temperature=0.5,
                base_url="https://api.groq.com/openai/v1"
            )

            response_prompt = (
                "You are a professional meeting summarizer. "
                "Based on the transcript, generate:\n"
                "1. A 2-3 sentence executive summary\n"
                "2. Top 3 key decisions or action items\n"
                "3. One important insight\n\n"
                f"TRANSCRIPT:\n{'='*60}\n{transcript[:2000]}\n{'='*60}"
            )

            response_msg = await response_llm.ainvoke([
                {"role": "system", "content": "You are a professional meeting analyzer."},
                {"role": "user", "content": response_prompt}
            ])
            generated_response = response_msg.content
            print(f"[DEBUG STEP 5] ✓ Response generated, length: {len(generated_response)} chars")

        except Exception as response_err:
            print(f"[DEBUG STEP 5] ✗ Response generation failed: {response_err}")
            generated_response = f"⚠️ Could not generate response: {str(response_err)}"

    # 6. Build result
    created_sources = [{
        "title": "Confluence Workspace Link",
        "url": f"https://{os.getenv('CONFLUENCE_DOMAIN')}/wiki/spaces/CKB/overview",
        "last_updated": "Just Now"
    }]

    display_answer = generated_response if (page_created and generated_response) else final_answer

    result_dict = {
        "current_answer": display_answer,
        "page_created": page_created,
        "confidence_score": 1.0 if page_created else 0.0,
        "sources": created_sources,
        "generated_response": generated_response
    }

    if created_page_id:
        result_dict["created_page_id"] = created_page_id

    print("[DEBUG] === DIRECT FILE PATH END ===\n")
    return result_dict


async def _react_query_path(state: State, user_query: str, client: Any, llm: ChatOpenAI) -> Dict[str, Any]:
    """
    Intelligent path: No file (query only)
    - Use ReAct agent to reason, search, and create page
    - Handle duplicate titles with retry logic
    """
    print("\n[mcp_agent_node] Routing to REACT QUERY PATH")
    print("\n[DEBUG] === REACT QUERY PATH START ===")

    # Get tools
    print("[DEBUG STEP 1] Fetching and wrapping tools...")
    raw_mcp_tools = await client.get_tools()
    ALLOWED_TOOLS = {"confluence_create_page", "confluence_get_pages", "confluence_search"}
    filtered_tools = [t for t in raw_mcp_tools if t.name in ALLOWED_TOOLS]
    print(f"[DEBUG STEP 1] ✓ Got {len(filtered_tools)} tools")

    mcp_tools = [SafeMCPToolWrapper(tool) for tool in filtered_tools]

    # Create ReAct agent
    print("[DEBUG STEP 2] Creating ReAct agent...")
    mcp_executor = create_react_agent(llm, mcp_tools)
    print("[DEBUG STEP 2] ✓ ReAct agent created")

    # Get content to publish
    past_answer_content = state.get("previous_answer", "").strip()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    unique_suffix = str(uuid.uuid4())[:8].upper()

    if not past_answer_content or past_answer_content == "No prior summary text provided.":
        print("[DEBUG] No content available")
        return {
            "current_answer": "⚠️ No content available to publish. Please ask a question first.",
            "page_created": False,
            "confidence_score": 0.0,
            "sources": []
        }

    data_block = past_answer_content[:2000]
    page_title_hint = f"Summary - {timestamp}"
    content_instruction = "The DATA_BLOCK is a pre-written summary. Publish it as-is."

    agent_prompt = (
        "You are an Atlassian Confluence publisher. Follow these steps:\n\n"
        "STEP 1 — CHOOSE A UNIQUE TITLE:\n"
        f"Your target title is: '{page_title_hint}'\n"
        "Use confluence_search to check if this exact title exists in space 'CKB'.\n"
        f"If it exists, append a unique suffix like [{unique_suffix}]\n\n"

        "STEP 2 — FORMAT THE CONTENT:\n"
        f"{content_instruction}\n\n"

        "STEP 3 — PUBLISH:\n"
        "Call confluence_create_page with space_key='CKB', enable_heading_anchors=True\n\n"

        f"DATA_BLOCK:\n{'='*50}\n{data_block}\n{'='*50}\n\n"
        f"USER REQUEST: {user_query}"
    )

    # Agent loop
    print("[DEBUG STEP 3] Starting ReAct agent loop...")
    messages = [HumanMessage(content=agent_prompt)]
    page_created = False
    created_page_id = None
    max_iterations = 3
    iteration = 0
    final_answer = None

    while iteration < max_iterations and not page_created:
        iteration += 1
        print(f"\n[LOOP ITERATION {iteration}/{max_iterations}]")

        try:
            agent_output = await mcp_executor.ainvoke(
                {"messages": messages},
                {"recursion_limit": 15}
            )
            messages = agent_output["messages"]

            # Scan for success
            for msg in messages:
                if isinstance(msg, ToolMessage) and _check_page_creation_success(getattr(msg, 'name', ''), str(msg.content)):
                    print(f"[DEBUG] ✓ PAGE CREATION SUCCESS")
                    page_created = True
                    tool_result = str(msg.content)

                    if "page_id" in tool_result.lower():
                        match = re.search(r'page_id["\s:]*(\d+)', tool_result, re.IGNORECASE)
                        if match:
                            created_page_id = match.group(1)

                    final_answer = tool_result
                    break

            if page_created:
                break

            last_message = messages[-1]
            if isinstance(last_message, (AIMessage, HumanMessage)):
                if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
                    final_answer = last_message.content
                    break

        except Exception as agent_err:
            agent_err_str = str(agent_err).lower()
            if "already exists" in agent_err_str or "page with this title" in agent_err_str:
                if iteration < max_iterations:
                    print(f"[DEBUG] Retrying with unique suffix...")
                    messages.append(AIMessage(
                        content=f"Please retry by appending [v{iteration}] to make title unique."
                    ))
                    continue
                else:
                    final_answer = f"Could not create page: {str(agent_err)}"
                    break
            else:
                raise

        if iteration >= max_iterations:
            final_answer = "Max iterations reached"
            break

    created_sources = [{
        "title": "Confluence Workspace Link",
        "url": f"https://{os.getenv('CONFLUENCE_DOMAIN')}/wiki/spaces/CKB/overview",
        "last_updated": "Just Now"
    }]

    result_dict = {
        "current_answer": final_answer or "Agent completed",
        "page_created": page_created,
        "confidence_score": 1.0 if page_created else 0.5,
        "sources": created_sources
    }

    if created_page_id:
        result_dict["created_page_id"] = created_page_id

    print("[DEBUG] === REACT QUERY PATH END ===\n")
    return result_dict


async def mcp_agent_node(state: State) -> Dict[str, Any]:
    """
    Main dispatcher: Route to direct file path or ReAct query path.
    - File present (transcript) → _direct_file_path() [fast, LLM-only]
    - Query only (no file)      → _react_query_path() [intelligent, agent-based]
    """
    print("\n" + "="*80)
    print("[DEBUG] mcp_agent_node ENTRY - DISPATCHER")
    print("="*80)

    user_query = state.get("query", "")
    transcript = state.get("transcript", "").strip() if state.get("transcript") else ""
    page_already_created = state.get("page_created", False)

    print(f"[DEBUG] user_query: {repr(user_query[:100] if user_query else '')}")
    print(f"[DEBUG] transcript length: {len(transcript)} chars")
    print(f"[DEBUG] page_already_created: {page_already_created}")

    # Early exit if already created
    if page_already_created:
        print(f"[DEBUG] ✓ EARLY EXIT: Page already created in this session")
        return {
            "current_answer": "Page creation already completed in this session.",
            "confidence_score": 1.0,
            "sources": [],
            "page_created": True
        }

    # Initialize MCP client (used by both paths)
    print("\n[DEBUG] Initializing MCP client...")
    try:
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
        print("[DEBUG] ✓ MCP client initialized")
    except Exception as e:
        print(f"[DEBUG] ✗ MCP client init failed: {e}")
        raise 

    # Initialize LLM (used by both paths)
    print("[DEBUG] Initializing LLM...")
    try:
        llm = ChatOpenAI(
            model="llama-3.3-70b-versatile",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.1,
            base_url="https://api.groq.com/openai/v1"
        )
        print("[DEBUG] ✓ LLM initialized")
    except Exception as e:
        print(f"[DEBUG] ✗ LLM init failed: {e}")
        raise

    # BRANCHING LOGIC
    if transcript and len(transcript) > 0:
        # FILE PATH: Direct LLM + Tool call
        return await _direct_file_path(state, transcript, client, llm)
    else:
        # QUERY PATH: ReAct agent
        return await _react_query_path(state, user_query, client, llm)