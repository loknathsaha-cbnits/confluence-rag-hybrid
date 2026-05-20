import os
import chainlit as cl
from dotenv import load_dotenv
from langchain_core.runnables.config import RunnableConfig

# Import your master orchestrator graph
from src.graph.graph import main_agent_graph

load_dotenv()

@cl.on_chat_start
async def on_chat_start():
    """Runs when a user opens the chat UI session."""
    cl.user_session.set("user_id", "loknath_saha_2004")
    
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
    
    user_id = cl.user_session.get("user_id")
    
    initial_state = {
        "query": msg.content,
        "user_id": user_id
    }
    
    final_answer = cl.Message(content="")
    await final_answer.send()
    
    print(f"\n[Chainlit Session] Processing query: {msg.content}")
    
    try:
        # Run the entire graph execution pipeline
        result = await cl.make_async(main_agent_graph.invoke)(
            initial_state, 
            config=RunnableConfig(configurable={"thread_id": cl.context.session.id})
        )
        
        # 1. Extract values matching your schema output
        answer = result.get("answer") or result.get("final_answer") or "No response generated."
        confidence = result.get("confidence_score", 0.0)
        raw_sources = result.get("sources", [])
        
        # 2. Build Chainlit text elements for references (Clickable UI Cards)
        cl_elements = []
        seen_urls = set()
        
        for idx, src in enumerate(raw_sources, start=1):
            url = src.get("url", "")
            title = src.get("title", "").replace("+", " ") or f"Reference Doc {idx}"
            
            if url and url not in seen_urls:
                seen_urls.add(url)
                
                # We use cl.Text with a markdown clean link inside the body 
                # This keeps the reference card itself compact and professional
                card_content = f"🔗 **Official Documentation:**\n[{title}]({url})"
                cl_elements.append(
                    cl.Text(name=f"📄 {title}", content=card_content, display="inline")
                )
        
        formatted_response = f"{answer}\n\n---\n💡 *Confidence Score: {float(confidence) * 100:.0f}%*"
        
        final_answer.content = formatted_response
        final_answer.elements = cl_elements
        await final_answer.update()
        
    except Exception as e:
        final_answer.content = f"❌ An error occurred during graph processing: {str(e)}"
        await final_answer.update()     