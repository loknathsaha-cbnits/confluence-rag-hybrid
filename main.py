import os
import chainlit as cl
from dotenv import load_dotenv
from langchain_core.runnables.config import RunnableConfig
import time

# Import your master orchestrator graph
from src.graph.graph import main_agent_graph

# Import database module
from src.db import init_database, get_db_manager

load_dotenv()

# Initialize database on startup
init_database()

@cl.on_chat_start
async def on_chat_start():
    """Runs when a user opens the chat UI session."""
    user_id = "loknath_saha_2004"
    cl.user_session.set("user_id", user_id)

    # Store session in database
    db = get_db_manager()
    session_id = cl.context.session.id
    db.create_session(session_id, user_id)

    # Send a clean welcome greeting
    # await cl.Message(
    #     content="Welcome! Ask me anything about your confluence PRDs"
    # ).send()

    from chainlit.input_widget import Select
    await cl.ChatSettings([
        Select(
            id="engine_mode",
            label="🤖 OpsEngine Active Subgraph",
            values=["Confluence-Hybrid-RAG", "Jira-Sprints", "Support-Automation"],
            initial_index=0
        )
    ]).send()


@cl.on_message
async def on_message(msg: cl.Message):
    """Runs whenever a user sends a message in the UI."""

    print(f"\n[DEBUG] msg.content: {repr(msg.content)}")
    print(f"[DEBUG] msg.elements count: {len(msg.elements) if msg.elements else 0}")
    if msg.elements:
        for el in msg.elements:
            print(f"[DEBUG] element → name={el.name}, path={getattr(el, 'path', 'N/A')}, type={type(el).__name__}")
    

    user_id = cl.user_session.get("user_id")
    thread_id = cl.context.session.id
    config = RunnableConfig(configurable={"thread_id": thread_id})

    # Record start time for processing duration
    start_time = time.time()

    # ── STEP 0: Handle uploaded transcript files ───────────────────────────────
    transcript_text = None

    if msg.elements:
        for element in msg.elements:
            if hasattr(element, "path") and element.path:
                if element.name.lower().endswith((".txt", ".md", ".text")):
                    try:
                        with open(element.path, "r", encoding="utf-8") as f:
                            transcript_text = f.read().strip()

                        print(f"\n[Chainlit] Transcript file received: {element.name} ({len(transcript_text)} chars)")

                        await cl.Message(
                            content=f"📄 Transcript **{element.name}** received ({len(transcript_text)} characters). Creating Confluence page..."
                        ).send()

                    except Exception as file_err:
                        await cl.Message(
                            content=f"❌ Failed to read file `{element.name}`: {file_err}"
                        ).send()
                        return
                else:
                    await cl.Message(
                        content=f"⚠️ Unsupported file type: `{element.name}`. Please upload a `.txt` or `.md` transcript file."
                    ).send()
                    return
    # ──────────────────────────────────────────────────────────────────────────

    # 1. Fetch the existing state from the checkpoint memory before triggering a new turn
    past_answer = ""
    try:
        current_graph_state = await main_agent_graph.aget_state(config)
        if current_graph_state and current_graph_state.values:
            past_answer = current_graph_state.values.get("current_answer", "")

        print("\n--- [DEBUG 1: MAIN.PY CHECKPOINT ENTRY] ---")
        print(f"Loaded past_answer from memory: {repr(past_answer)}")
        print("-------------------------------------------\n")
    except Exception as state_err:
        print(f"[Chainlit Session Warning] Could not fetch checkpoint state: {state_err}")

    # 2. Package the initial state — include transcript if a file was uploaded
    initial_state = {
        "query": msg.content or "Create a Confluence page from the uploaded meeting transcript.",
        "user_id": user_id,
        "previous_answer": past_answer,
        **({"transcript": transcript_text} if transcript_text else {})
    }

        # TEMP DEBUG
    print(f"[DEBUG] transcript_text extracted: {repr(transcript_text[:200]) if transcript_text else None}")
    print(f"[DEBUG] initial_state keys: {list(initial_state.keys())}")

    final_answer = cl.Message(content="")
    await final_answer.send()

    print(f"\n[Chainlit Session] Processing query: {msg.content}")

    try:
        # 3. Run the entire graph execution pipeline
        result = await main_agent_graph.ainvoke(initial_state, config=config)

        # Extract values matching your updated schema output
        answer = result.get("current_answer") or result.get("final_answer") or "No response generated."
        confidence = result.get("confidence_score", 0.0)
        raw_sources = result.get("sources", [])
        router_decision = result.get("router_decision")
        execution_status = result.get("execution_status", "success")

        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)

        # 4. Build Chainlit text elements for references (Clickable UI Cards)
        cl_elements = []
        seen_urls = set()

        # Prepare sources for database storage
        db_sources = []

        for idx, src in enumerate(raw_sources, start=1):
            url = src.get("url", "")
            title = src.get("title", "").replace("+", " ") or f"Reference Doc {idx}"
            chunk_id = src.get("chunk_id")
            score = src.get("score")

            if url and url not in seen_urls:
                seen_urls.add(url)

                db_sources.append({
                    'url': url,
                    'title': title,
                    'chunk_id': chunk_id,
                    'score': score
                })

                card_content = f"🔗 **Official Documentation:**\n[{title}]({url})"
                cl_elements.append(
                    cl.Text(name=f"📄 {title}", content=card_content, display="inline")
                )

        # Suppress confidence score display for transcript/MCP action flows
        if transcript_text:
            formatted_response = answer
        else:
            formatted_response = f"{answer}\n\n---\n💡 *Confidence Score: {float(confidence) * 100:.0f}%*"

        final_answer.content = formatted_response
        final_answer.elements = cl_elements
        await final_answer.update()

        # 5. Store interaction in database
        db = get_db_manager()
        try:
            db.save_interaction(
                session_id=thread_id,
                user_id=user_id,
                query=msg.content or f"[Transcript Upload: {len(transcript_text or '')} chars]",
                answer=answer,
                confidence_score=float(confidence),
                sources=db_sources,
                router_decision=router_decision,
                execution_status=execution_status,
                processing_time_ms=processing_time_ms,
                error_message=None
            )
            print(f"[Database] Interaction stored for user: {user_id}")
        except Exception as db_err:
            print(f"[Database Warning] Could not store interaction: {db_err}")

    except Exception as e:
        processing_time_ms = int((time.time() - start_time) * 1000)
        error_msg = str(e)

        final_answer.content = f"❌ An error occurred during graph processing: {error_msg}"
        await final_answer.update()

        db = get_db_manager()
        try:
            db.save_interaction(
                session_id=thread_id,
                user_id=user_id,
                query=msg.content or "[Transcript Upload]",
                answer="Error in processing",
                confidence_score=0.0,
                sources=[],
                router_decision=None,
                execution_status="error",
                processing_time_ms=processing_time_ms,
                error_message=error_msg
            )
            print(f"[Database] Error interaction stored for user: {user_id}")
        except Exception as db_err:
            print(f"[Database Warning] Could not store error interaction: {db_err}")
