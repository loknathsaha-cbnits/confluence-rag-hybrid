# SQLite Database Setup & Configuration Guide

## Overview
This guide provides step-by-step instructions to set up and use the SQLite database for storing interactions in OpsEngine.

## What Has Been Implemented

### 1. **Database Files Created**

```
src/db/
├── __init__.py          # Package exports
├── models.py            # Data model definitions
└── database.py          # Core database operations
```

### 2. **Main Changes to main.py**

- **Lines 5, 11**: Added imports for database and timing
- **Line 16**: Database initialization at startup
- **Lines 24-27**: Session creation when user starts chat
- **Lines 53-54**: Start time recording for performance metrics
- **Lines 90-91**: Extract router_decision and execution_status
- **Lines 93-94, 101-118**: Prepare and format sources for database storage
- **Lines 133-150**: Store successful interactions
- **Lines 152-177**: Handle and store failed interactions

### 3. **Database Tables**

```sql
users
├── user_id (PRIMARY KEY)
├── created_at
└── last_active

sessions
├── session_id (PRIMARY KEY)
├── user_id (FOREIGN KEY)
├── created_at
├── engine_mode
└── status

interactions
├── interaction_id (PRIMARY KEY, AUTO-INCREMENT)
├── session_id (FOREIGN KEY)
├── user_id (FOREIGN KEY)
├── query (the user's question)
├── answer (the LLM's response)
├── confidence_score (0.0-1.0)
├── router_decision (which subgraph handled it)
├── execution_status (success/error)
├── processing_time_ms (milliseconds)
├── created_at
└── error_message (if status=error)

sources
├── source_id (PRIMARY KEY, AUTO-INCREMENT)
├── interaction_id (FOREIGN KEY)
├── url (document URL)
├── title (document title)
├── chunk_id (if chunked)
├── relevance_score
└── created_at
```

---

## Step-by-Step Setup Instructions

### Step 1: Verify Installation
The database module is already integrated. Verify the files exist:
```bash
cd c:/Users/hp/Desktop/ops_engine
ls -la src/db/
```

Expected output:
```
__init__.py
database.py
models.py
```

### Step 2: Run the Application
The database initializes automatically on first run:
```bash
chainlit run main.py
```

The database file will be created at: `data/ops_engine.db`

### Step 3: Verify Database Creation
Check that the database file was created:
```bash
ls -la data/ops_engine.db
```

### Step 4: Send Test Messages
1. Open the Chainlit UI (usually at `http://localhost:8000`)
2. Send 2-3 test messages to the chatbot
3. Each message should appear in the database

### Step 5: Query the Database
Use the provided `query_interactions.py` script (see below)

---

## Data Flow: How Interactions Are Stored

### Flow Diagram
```
┌─────────────────────────────────────────────┐
│  1. USER SENDS MESSAGE                      │
│     (msg: "How do I do X?")                 │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  2. CHAINLIT TRIGGER: @on_message           │
│     ├─ Extract user_id, session_id          │
│     ├─ Record start_time                    │
│     └─ Set initial_state                    │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  3. CALL: main_agent_graph.ainvoke()        │
│     ├─ Route to appropriate subgraph        │
│     ├─ Retrieve from Pinecone + BM25       │
│     ├─ Generate answer via LLM             │
│     └─ Get confidence_score, sources       │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  4. EXTRACT RESULTS                         │
│     ├─ answer: str                         │
│     ├─ confidence: float (0.0-1.0)        │
│     ├─ sources: List[{url, title, ...}]   │
│     ├─ router_decision: str                │
│     └─ processing_time_ms: int             │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  5. DATABASE OPERATION                      │
│     db.save_interaction(                    │
│       session_id, user_id, query, answer,  │
│       confidence, sources, ...             │
│     )                                       │
└────────────────┬────────────────────────────┘
                 │
        ┌────────┴─────────┐
        ▼                  ▼
┌──────────────────┐  ┌──────────────────┐
│ INSERT into      │  │ INSERT into      │
│ interactions     │  │ sources          │
│ table            │  │ table            │
│ ├─ query        │  │ (one row per     │
│ ├─ answer       │  │  source doc)     │
│ ├─ confidence   │  │                  │
│ └─ timing info  │  │                  │
└──────────────────┘  └──────────────────┘
        │                      │
        └──────────┬───────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │ DATABASE COMMITTED   │
        │ data/ops_engine.db   │
        └──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  6. RETURN RESPONSE TO USER                 │
│     ├─ Display answer with formatting      │
│     ├─ Show source links as cards          │
│     └─ Display confidence score            │
└─────────────────────────────────────────────┘

✅ INTERACTION FULLY STORED IN SQLITE
```

### What Gets Stored for Each Interaction

**Main Interaction Record (1 row in `interactions` table)**:
```python
{
    'interaction_id': 1,           # Auto-generated
    'session_id': 'abc-123-xyz',   # Chainlit session ID
    'user_id': 'loknath_saha_2004',
    'query': 'How do I configure Jira?',
    'answer': 'To configure Jira, you need to...',
    'confidence_score': 0.89,      # 0.0 to 1.0
    'router_decision': 'jira_subgraph',  # Which graph handled it
    'execution_status': 'success',  # or 'error'
    'processing_time_ms': 2341,     # Total time in milliseconds
    'created_at': '2025-05-25 14:32:01',
    'error_message': None           # Only if status='error'
}
```

**Source Records (1 row per document reference)**:
```python
{
    'source_id': 1,               # Auto-generated
    'interaction_id': 1,          # Links back to interaction
    'url': 'https://docs.../page1',
    'title': 'Jira Configuration Guide',
    'chunk_id': 'chunk_42',       # If chunked
    'relevance_score': 0.95,      # Retriever confidence
    'created_at': '2025-05-25 14:32:01'
}
```

### Example: Multi-turn Conversation

**Turn 1: User asks "How do I set up Jira?"**
- New interaction created
- 2 sources found
- Stored in database

**Turn 2: User asks follow-up "What about permissions?"**
- New interaction created (separate from Turn 1)
- Both in same session (session_id links them)
- Previous answer available via `previous_answer` field

**Query database to see conversation flow**:
```sql
SELECT 
    interaction_id,
    query,
    answer,
    confidence_score,
    processing_time_ms,
    created_at
FROM interactions
WHERE session_id = 'abc-123-xyz'
ORDER BY created_at ASC;
```

---

## Querying the Database

### Option 1: Using the Provided Script
Create file `scripts/query_interactions.py`:

```bash
python scripts/query_interactions.py --user loknath_saha_2004 --limit 10
```

### Option 2: Direct SQLite CLI
```bash
sqlite3 data/ops_engine.db

# List all interactions
SELECT * FROM interactions LIMIT 5;

# Get interactions with sources
SELECT i.*, s.url, s.title 
FROM interactions i 
LEFT JOIN sources s ON i.interaction_id = s.interaction_id
WHERE i.user_id = 'loknath_saha_2004'
LIMIT 10;

# Get analytics
SELECT 
    COUNT(*) as total_queries,
    AVG(confidence_score) as avg_confidence,
    AVG(processing_time_ms) as avg_time_ms
FROM interactions;
```

### Option 3: In Python Code
```python
from src.db import get_db_manager

db = get_db_manager()

# Get user's interaction history
history = db.get_interaction_history('loknath_saha_2004', limit=10)

# Get session conversation
session_interactions = db.get_session_interactions('session-id-here')

# Get analytics
analytics = db.get_analytics('loknath_saha_2004')
print(f"Total interactions: {analytics['total_interactions']}")
print(f"Avg confidence: {analytics['average_confidence']}")
```

---

## Database Performance & Optimization

### Current Indexes
- `idx_interactions_user_id`: Fast lookup by user
- `idx_interactions_session_id`: Fast lookup by session
- `idx_sources_interaction_id`: Fast source retrieval
- `idx_sessions_user_id`: Fast session lookup

### Scaling Considerations
- **Small deployments** (< 10K interactions): SQLite is perfect
- **Medium** (10K - 100K): SQLite works, consider periodic backups
- **Large** (> 1M): Migrate to PostgreSQL

### Backup
```bash
# Create backup
cp data/ops_engine.db data/ops_engine.backup.db

# Export to CSV
sqlite3 data/ops_engine.db ".mode csv" ".output interactions.csv" "SELECT * FROM interactions;"
```

---

## Troubleshooting

### Database file not created
**Problem**: `data/ops_engine.db` doesn't exist after running the app
- **Solution**: Check write permissions in `data/` directory
- Create directory manually: `mkdir -p data`

### Lock errors
**Problem**: "database is locked" error
- **Solution**: Ensure only one Chainlit instance is running
- Or increase connection timeout in `database.py`

### Query returns empty
**Problem**: No interactions in database despite sending messages
- **Solution**: 
  1. Check console for `[Database]` log messages
  2. Verify database initialization: `chainlit run main.py`
  3. Send a test message and wait for response

### Slow queries
**Problem**: Queries taking > 1 second
- **Solution**: Check if database needs optimization
  ```bash
  sqlite3 data/ops_engine.db "VACUUM;"
  ```

---

## API Reference

### `DatabaseManager` Class

```python
from src.db import get_db_manager

db = get_db_manager()

# Create/update user
user = db.create_or_update_user(user_id: str) -> UserRecord

# Create session
session = db.create_session(session_id: str, user_id: str, engine_mode: str) -> SessionRecord

# Save interaction
interaction = db.save_interaction(
    session_id: str,
    user_id: str,
    query: str,
    answer: str,
    confidence_score: float,
    sources: List[dict],
    router_decision: Optional[str],
    execution_status: str,
    processing_time_ms: int,
    error_message: Optional[str]
) -> InteractionRecord

# Get history
history = db.get_interaction_history(user_id: str, limit: int = 50) -> List[dict]

# Get session interactions
interactions = db.get_session_interactions(session_id: str) -> List[dict]

# Get analytics
stats = db.get_analytics(user_id: Optional[str] = None) -> dict
```

---

## Summary

✅ **SQLite database fully integrated**
✅ **Auto-initialization on startup**
✅ **All interactions stored with metadata**
✅ **Sources tracked with each interaction**
✅ **Performance metrics captured**
✅ **Error handling and logging**
✅ **Ready for production use**

Database is now storing every user interaction, question, answer, confidence score, processing time, and source references!
