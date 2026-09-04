# 📚 Confluence Hybrid RAG & Agent

> An AI-powered knowledge assistant that combines **hybrid search**, **LangGraph**, **LLM-based answer generation**, and **MCP-based Confluence actions** to retrieve and work with technical knowledge stored in Confluence.

![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)
![LangGraph](https://img.shields.io/badge/LangGraph-Agentic_Workflow-orange.svg)
![Chainlit](https://img.shields.io/badge/Chainlit-UI-green.svg)
![Pinecone](https://img.shields.io/badge/Pinecone-Vector_Search-purple.svg)
![License](https://img.shields.io/badge/Status-POC-yellow.svg)

## What It Does

The Confluence Hybrid RAG Agent provides a conversational interface for querying technical knowledge from a Confluence knowledge base.

Instead of relying on only semantic/vector search, the system combines:

* **Dense vector search** using Pinecone and Sentence Transformers
* **Sparse keyword search** using BM25
* **Reciprocal Rank Fusion (RRF)** to combine both result sets
* **FlashRank reranking** to select the most relevant chunks
* **LLM generation** using Llama 3.3 through Groq
* **LangGraph** to control the execution flow
* **MCP tools** to perform write operations against Confluence
* **SQLite** to store conversation history, sources, confidence scores, and execution metadata
* **Chainlit** to provide the chat interface

The result is an assistant that can retrieve relevant Confluence information, generate an answer from the retrieved context, show source references, and perform explicitly requested Confluence write operations.

---

## Tech Stack

| Technology                       | Purpose                                    |
| -------------------------------- | ------------------------------------------ |
| **Python 3.12+**                 | Application runtime                        |
| **LangGraph**                    | Graph-based workflow orchestration         |
| **LangChain**                    | LLM and tool integration                   |
| **Groq / Llama 3.3 70B**         | Query classification and answer generation |
| **Pinecone**                     | Dense vector retrieval                     |
| **Sentence Transformers**        | Query embeddings                           |
| **BM25**                         | Keyword-based retrieval                    |
| **Reciprocal Rank Fusion**       | Combines dense and sparse results          |
| **FlashRank**                    | Reranks retrieved documents                |
| **Chainlit**                     | Web-based conversational UI                |
| **MCP / LangChain MCP Adapters** | Confluence write operations                |
| **SQLite**                       | Conversation and interaction persistence   |
| **Pydantic**                     | Structured state/output models             |
| **python-dotenv**                | Environment configuration                  |

The project's `pyproject.toml` requires Python 3.12+ and includes LangGraph, LangChain, Chainlit, Pinecone, Sentence Transformers, FlashRank, BM25, Torch, and MCP adapter dependencies.

---

# Quick Start

## 1. Clone the Repository

```bash
git clone https://github.com/loknathsaha-cbnits/confluence-rag-hybrid.git
cd confluence-rag-hybrid
```

## 2. Create a Virtual Environment

Python **3.12 or later** is required.

```bash
python -m venv .venv
```

Activate it:

### Windows

```bash
.venv\Scripts\activate
```

### Linux / macOS

```bash
source .venv/bin/activate
```

## 3. Install Dependencies

The repository contains a `pyproject.toml` and `uv.lock`. `uv` is recommended for installation.

```bash
pip install uv
uv sync
```

Alternatively:

```bash
pip install -e .
```

The project is configured to use the CPU-only PyTorch package, avoiding unnecessary CUDA dependencies.

---

## 4. Configure Environment Variables

Create a `.env` file in the project root.

```env
# LLM
GROQ_API_KEY=your_groq_api_key

# Pinecone
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX_NAME=your_pinecone_index

# Confluence
CONFLUENCE_DOMAIN=your-domain.atlassian.net
CONFLUENCE_EMAIL=your_confluence_email
CONFLUENCE_API_TOKEN=your_confluence_api_token
```

The application uses `GROQ_API_KEY` for the Llama 3.3 model, while the hybrid retriever uses `PINECONE_API_KEY` and `PINECONE_INDEX_NAME`. Confluence MCP operations use the Confluence domain, email, and API token.

---

## 5. Prepare the Retrieval Data

The hybrid retriever expects the following local files:

```text
data/
└── upload/
    ├── bm25_corpus.json
    └── bm25_index.pkl
```

These files are used by the BM25 retrieval component.

The Pinecone index must also contain the corresponding vectorized Confluence chunks and metadata.

The retriever loads:

* `sentence-transformers/all-MiniLM-L6-v2` for embeddings
* Pinecone for dense retrieval
* BM25 for sparse retrieval
* FlashRank for final reranking

---

## 6. Start the Application

Run Chainlit:

```bash
chainlit run main.py
```

The application will start the Chainlit chat interface.

Open the displayed local URL in your browser.

---

# How It Works

The system is implemented as a parent LangGraph containing a Confluence retrieval subgraph.

```text
                    User Query
                        │
                        ▼
              ┌──────────────────┐
              │   Chainlit UI    │
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │ Query Processing │
              │   LangGraph     │
              └────────┬─────────┘
                       │
                       ▼
             ┌─────────────────────┐
             │ Confluence Subgraph │
             └──────────┬──────────┘
                        │
                        ▼
                 ┌─────────────┐
                 │  Supervisor │
                 └──────┬──────┘
                        │
              ┌─────────┴─────────┐
              │                   │
              ▼                   ▼
          RAG Query          MCP Action
              │                   │
              ▼                   ▼
       Hybrid Retrieval     Confluence Tools
              │
              ▼
       ┌───────────────┐
       │ Dense Search  │
       │   Pinecone    │
       └───────┬───────┘
               │
               ├──────────────┐
               │              │
               ▼              ▼
        Sparse Search     Dense Search
            BM25           Pinecone
               │              │
               └──────┬───────┘
                      ▼
             Reciprocal Rank
                 Fusion
                      │
                      ▼
                FlashRank
                 Reranking
                      │
                      ▼
             Top Context Chunks
                      │
                      ▼
              Llama 3.3 / Groq
                      │
                      ▼
             Structured Answer
              + Confidence
              + Sources
                      │
                      ▼
                Chainlit UI
                      │
                      ▼
              SQLite Database
```

The actual parent graph contains two nodes:

```text
START
  │
  ▼
process_query
  │
  ▼
retrieval_flow_subgraph
  │
  ▼
 END
```

The parent graph delegates the main work to the Confluence subgraph.

---

# Hybrid Retrieval

The main retrieval feature is the combination of **dense semantic search** and **sparse keyword search**.

### 1. Dense Retrieval

The user query is converted into an embedding using:

```text
sentence-transformers/all-MiniLM-L6-v2
```

The resulting vector is searched against Pinecone.

```text
User Query
    │
    ▼
Sentence Transformer
    │
    ▼
Query Embedding
    │
    ▼
Pinecone
    │
    ▼
Dense Results
```

### 2. Sparse Retrieval

The same query is tokenized and searched against the BM25 index.

```text
User Query
    │
    ▼
Tokenization
    │
    ▼
BM25 Search
    │
    ▼
Sparse Results
```

### 3. Reciprocal Rank Fusion

The dense and sparse results are combined using **Reciprocal Rank Fusion**.

```text
Dense Results ─────┐
                   ├──► RRF ──► Combined Candidates
Sparse Results ────┘
```

The implementation uses an RRF constant of `k=60`.

### 4. Reranking

The fused candidates are passed through **FlashRank**.

Only the highest-ranked chunks are retained for the final LLM context.

The current retriever requests up to 15 candidates and returns the final 3 chunks after reranking.

---

# Answer Generation

After retrieval, the selected Confluence chunks are passed to the Llama 3.3 model through Groq.

The generation node builds a context containing:

```text
Source Document
Context Snippet
```

for every retrieved document.

The model is instructed to answer using the supplied source context rather than relying on unrelated outside knowledge.

The generated result is represented using:

```python
class GenerationOutput(BaseModel):
    current_answer: str
    confidence_score: float
```

The confidence score is returned between `0.0` and `1.0`.

---

# Query Routing

Before retrieval, a supervisor node determines what the user is trying to do.

Two routes are currently defined:

```text
                User Query
                    │
                    ▼
               Supervisor
                    │
             ┌──────┴──────┐
             │             │
             ▼             ▼
            rag        mcp_action
             │             │
             ▼             ▼
          Retrieve      MCP Agent
             │             │
             ▼             ▼
         Generate      Confluence
                       Write Action
```

The supervisor uses Llama 3.3 with a deterministic configuration and classifies the request as either:

* `rag` — information retrieval, questions, explanations, summaries
* `mcp_action` — explicit requests to create, update, or publish content in Confluence

This prevents normal questions from accidentally triggering Confluence modification operations.

---

# MCP Confluence Actions

For requests that explicitly require a Confluence modification, the MCP path is used.

The project creates an MCP client using:

```text
mcp-atlassian
```

through `stdio`.

```text
User Command
     │
     ▼
Supervisor
     │
     ▼
mcp_action
     │
     ▼
MCP Client
     │
     ▼
mcp-atlassian
     │
     ▼
Confluence
```

The MCP agent is implemented using LangGraph's ReAct agent functionality.

Before creating a page, the agent is instructed to check whether a page with the same title already exists in the `CKB` space. If a duplicate title is found, a unique title is generated instead.

The MCP integration also contains argument-cleaning logic for tool parameters and converts numeric string values into integers where required.

---

# Conversation Memory

LangGraph's `MemorySaver` is used by the parent graph to maintain state across the current conversation thread.

The application retrieves the previous answer before processing a new message and passes it into the graph as:

```text
previous_answer
```

This allows follow-up questions to be handled with awareness of the previous turn.

---

# SQLite Persistence

In addition to LangGraph's graph state, the application maintains a SQLite database for interaction history and analytics.

The database is created at:

```text
data/ops_engine.db
```

The following information is stored:

| Data             | Description                       |
| ---------------- | --------------------------------- |
| User             | User information                  |
| Session          | Conversation/session information  |
| Query            | User's question                   |
| Answer           | Generated response                |
| Confidence       | Model confidence score            |
| Sources          | Retrieved source documents        |
| Router Decision  | Selected execution path           |
| Execution Status | Success/error                     |
| Processing Time  | Response time                     |
| Error Message    | Error information when applicable |

The database layer is implemented as a thread-safe `DatabaseManager`.

---

# Project Structure

```text
confluence-rag-hybrid/
│
├── main.py
├── pyproject.toml
├── uv.lock
│
├── src/
│   ├── config/
│   │   └── confluence_mcp_config.py
│   │
│   ├── db/
│   │   ├── database.py
│   │   ├── models.py
│   │   └── __init__.py
│   │
│   ├── graph/
│   │   ├── graph.py
│   │   ├── state.py
│   │   └── __init__.py
│   │
│   ├── subgraphs/
│   │   ├── confluence/
│   │   │   ├── agent.py
│   │   │   ├── graph.py
│   │   │   ├── mcp_action.py
│   │   │   ├── retriever.py
│   │   │   ├── supervisor.py
│   │   │   └── tools/
│   │   │
│   │   ├── jira/
│   │   └── support/
│   │
│   └── utils/
│
├── scripts/
│   └── query_interactions.py
│
├── data/
│   └── upload/
│       ├── bm25_corpus.json
│       └── bm25_index.pkl
│
├── DATABASE_FLOW.md
├── IMPLEMENTATION_SUMMARY.md
├── QUICK_START.md
└── SETUP_DATABASE.md
```

The repository currently contains dedicated Confluence, Jira, and Support subgraph directories, while the active parent graph is wired to the Confluence subgraph.

---

# Configuration

| Variable               | Purpose                               |
| ---------------------- | ------------------------------------- |
| `GROQ_API_KEY`         | Authentication for Groq/Llama 3.3     |
| `PINECONE_API_KEY`     | Authentication for Pinecone           |
| `PINECONE_INDEX_NAME`  | Pinecone index used for vector search |
| `CONFLUENCE_DOMAIN`    | Atlassian/Confluence domain           |
| `CONFLUENCE_EMAIL`     | Confluence account email              |
| `CONFLUENCE_API_TOKEN` | Confluence API authentication         |

The LLM configuration is currently defined directly in the Python implementation using:

```text
llama-3.3-70b-versatile
```

and the Groq OpenAI-compatible endpoint.

---

# Useful Database Commands

View recent interactions:

```bash
python scripts/query_interactions.py --limit 10
```

View analytics:

```bash
python scripts/query_interactions.py --analytics
```

List users:

```bash
python scripts/query_interactions.py --list-users
```

The repository also contains dedicated documentation for database setup and data flow:

```text
QUICK_START.md
SETUP_DATABASE.md
DATABASE_FLOW.md
```

These documents describe the interaction tables, source tracking, analytics, and database flow.

---

# Current Limitations

This project is currently structured as a **proof of concept**.

A few implementation details should be kept in mind:

* The retrieval pipeline depends on pre-built BM25 files being available locally.
* Dense retrieval depends on an existing Pinecone index.
* The LLM model is currently specified directly in the source code.
* Confluence source metadata currently uses `last_updated="Unknown"` in the retrieval result.
* The parent graph currently invokes the Confluence subgraph directly.
* Jira and Support components exist in the repository but are not part of the current parent graph execution path.
* The MCP write path modifies a real Confluence workspace, so valid credentials and appropriate permissions are required.
* SQLite is suitable for the current local/small-scale implementation; larger deployments would require a more scalable persistence layer.

---

# Architecture Summary

The core architecture can be summarized as:

```text
                    ┌─────────────────┐
                    │    Chainlit     │
                    │    Chat UI      │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   LangGraph     │
                    │  Parent Graph   │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   Supervisor    │
                    │ Intent Routing  │
                    └───────┬─────────┘
                            │
                 ┌──────────┴──────────┐
                 │                     │
                 ▼                     ▼
           ┌────────────┐       ┌────────────┐
           │ Hybrid RAG │       │  MCP Agent │
           └─────┬──────┘       └─────┬──────┘
                 │                    │
       ┌─────────┴─────────┐          ▼
       │                   │      Confluence
       ▼                   ▼
   Pinecone               BM25
       │                   │
       └─────────┬─────────┘
                 ▼
                RRF
                 │
                 ▼
            FlashRank
                 │
                 ▼
             Top Chunks
                 │
                 ▼
          Llama 3.3 / Groq
                 │
                 ▼
        Answer + Confidence
                 │
                 ▼
        Sources + SQLite
```

This architecture combines a deterministic LangGraph workflow with LLM-based intent classification, hybrid retrieval, LLM answer generation, and a separate ReAct/MCP path for explicit Confluence write operations.

