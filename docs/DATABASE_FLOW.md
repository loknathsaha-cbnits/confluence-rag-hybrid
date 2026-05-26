# OpsEngine - SQLite Database Architecture & Data Flow

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CHAINLIT UI LAYER                                 │
│                  (Browser - Chat Interface)                              │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             │ User Input
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    MAIN.PY - REQUEST HANDLER                            │
│                                                                           │
│  @on_chat_start()          @on_message()                               │
│  ├─ Create Session    ├─ Start Timer ⏱️                               │
│  ├─ Set User ID       ├─ Get Checkpoint State                         │
│  └─ Store in DB       ├─ Invoke Graph                                  │
│                       ├─ Extract Results                                │
│                       ├─ Calculate Time                                 │
│                       └─ Save to DB ✅                                │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             │ Graph Invocation
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                  MAIN AGENT GRAPH (LangGraph)                           │
│                                                                           │
│  ├─ Router Node                                                          │
│  │  └─ Decides: Confluence / Jira / Support                           │
│  │                                                                       │
│  ├─ Confluence Subgraph               ├─ Jira Subgraph                │
│  │  ├─ Hybrid Retriever              │  ├─ Jira Tools                │
│  │  │  ├─ BM25 Sparse Index          │  ├─ Jira API                  │
│  │  │  └─ Pinecone Vector DB         │  └─ Issue Retrieval           │
│  │  ├─ LLM (Groq/OpenAI)             │                               │
│  │  └─ Confidence Scoring            └─ Support Subgraph            │
│  │                                       ├─ FAQ Matching             │
│  │                                       └─ Automation               │
│  │                                                                    │
│  └─ Response Generation                                              │
│      └─ Structured Output with Sources                              │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             │ Results
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│               RESULTS EXTRACTION (main.py, lines 84-91)                 │
│                                                                           │
│  Extracted Data:                                                         │
│  ├─ answer: str (LLM response)                                         │
│  ├─ confidence_score: float (0.0-1.0)                                 │
│  ├─ sources: List[dict] with url, title, chunk_id, score            │
│  ├─ router_decision: str (which subgraph)                            │
│  ├─ execution_status: str (success/error)                            │
│  └─ processing_time_ms: int (elapsed time)                           │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             │ Call save_interaction()
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              DATABASE LAYER - src/db/database.py                        │
│                                                                           │
│  DatabaseManager.save_interaction():                                    │
│  1. Ensure user exists → INSERT/UPDATE users table                     │
│  2. Ensure session exists → INSERT/UPDATE sessions table              │
│  3. Insert interaction → INSERT interactions table                    │
│  4. Insert sources → INSERT multiple rows in sources table           │
│  5. COMMIT transaction                                                 │
│                                                                           │
│  Thread-Safe: ✓ Using threading.RLock()                               │
│  Automatic: ✓ On every message                                        │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────────┐
        │     SQLITE DATABASE FILE                │
        │  data/ops_engine.db                    │
        │  (Created if doesn't exist)            │
        └────────────────────────────────────────┘
                    │
         ┌──────────┼──────────┬──────────┐
         │          │          │          │
         ▼          ▼          ▼          ▼
    ┌────────┐ ┌────────┐ ┌────────────┐ ┌────────┐
    │ users  │ │sessions│ │interactions│ │sources │
    ├────────┤ ├────────┤ ├────────────┤ ├────────┤
    │user_id │ │session │ │query       │ │url     │
    │created │ │user_id │ │answer      │ │title   │
    │last act│ │created │ │confidence  │ │int_id  │
    │        │ │engine  │ │time_ms     │ │score   │
    │        │ │status  │ │status      │ │        │
    │        │ │        │ │error_msg   │ │        │
    └────────┘ └────────┘ └────────────┘ └────────┘
```

---

## Detailed Data Flow: From User Input to Database

### PHASE 1: Chat Start
```
USER OPENS BROWSER
        │
        ▼
CHAINLIT @on_chat_start triggered
        │
        ├─► Create user_id: "loknath_saha_2004"
        │
        ├─► Get session_id from Chainlit context
        │
        ├─► db.create_session(session_id, user_id)
        │   │
        │   └─► INSERT into users (if new)
        │   └─► INSERT into sessions
        │
        └─► Show engine_mode selector
            (Confluence / Jira / Support)
```

**Database State After Phase 1:**
```sql
users table:
├─ user_id: "loknath_saha_2004"
├─ created_at: "2025-05-25 14:00:00"
└─ last_active: "2025-05-25 14:00:00"

sessions table:
├─ session_id: "abc-123-xyz-def"
├─ user_id: "loknath_saha_2004"
├─ created_at: "2025-05-25 14:00:00"
├─ engine_mode: "Confluence-Hybrid-RAG"
└─ status: "active"
```

---

### PHASE 2: Message Received
```
USER SENDS MESSAGE: "How do I configure Jira?"
        │
        ▼
CHAINLIT @on_message triggered (main.py line 45)
        │
        ├─► start_time = time.time() ⏱️ (line 54)
        │
        ├─► Extract:
        │   ├─ user_id: "loknath_saha_2004"
        │   ├─ session_id: "abc-123-xyz-def"
        │   └─ msg.content: "How do I configure Jira?"
        │
        └─► Load checkpoint state (previous answer)
```

---

### PHASE 3: Graph Processing
```
INVOKE main_agent_graph.ainvoke()
        │
        ├─► ROUTER NODE
        │   │
        │   └─► Analyzes query
        │       └─ Decision: "jira_subgraph"
        │
        ├─► JIRA SUBGRAPH
        │   ├─ Tool Calls (Jira API)
        │   ├─ Search Jira tickets
        │   └─ Extract relevant info
        │
        ├─► LLM GENERATION
        │   ├─ Model: Groq or OpenAI
        │   ├─ Prompt: query + retrieved data
        │   └─ Output: answer + sources
        │
        └─► CONFIDENCE SCORING
            └─ Rank models / output scores
```

---

### PHASE 4: Results Extraction
```
GRAPH RETURNS result dict
        │
        ├─► answer = "To configure Jira, first login..."
        │
        ├─► confidence_score = 0.87
        │
        ├─► sources = [
        │   {
        │       'url': 'https://docs.../jira-setup',
        │       'title': 'Jira Configuration Guide',
        │       'chunk_id': 'doc_42',
        │       'score': 0.95
        │   },
        │   {
        │       'url': 'https://docs.../jira-perms',
        │       'title': 'Jira Permissions',
        │       'chunk_id': 'doc_55',
        │       'score': 0.82
        │   }
        │ ]
        │
        ├─► router_decision = "jira_subgraph"
        │
        ├─► execution_status = "success"
        │
        └─► processing_time_ms = 2341
            (time.time() - start_time) * 1000
```

---

### PHASE 5: Database Storage
```
CALL db.save_interaction() (line 136)
        │
        ├─► STEP 1: Ensure user exists
        │   └─ create_or_update_user(user_id)
        │      └─ UPDATE users.last_active = NOW()
        │
        ├─► STEP 2: Ensure session exists
        │   └─ Already created in @on_chat_start
        │
        ├─► STEP 3: Insert interaction
        │   │
        │   └─► INSERT into interactions:
        │       ├─ interaction_id: AUTO (1, 2, 3...)
        │       ├─ session_id: "abc-123-xyz-def"
        │       ├─ user_id: "loknath_saha_2004"
        │       ├─ query: "How do I configure Jira?"
        │       ├─ answer: "To configure Jira, first..."
        │       ├─ confidence_score: 0.87
        │       ├─ router_decision: "jira_subgraph"
        │       ├─ execution_status: "success"
        │       ├─ processing_time_ms: 2341
        │       ├─ created_at: NOW()
        │       └─ error_message: NULL
        │
        │   Result: interaction_id = 42
        │
        ├─► STEP 4: Insert sources (1 row per source)
        │   │
        │   └─► First source:
        │       INSERT into sources:
        │       ├─ source_id: AUTO (1)
        │       ├─ interaction_id: 42
        │       ├─ url: "https://docs.../jira-setup"
        │       ├─ title: "Jira Configuration Guide"
        │       ├─ chunk_id: "doc_42"
        │       └─ relevance_score: 0.95
        │
        │   └─► Second source:
        │       INSERT into sources:
        │       ├─ source_id: AUTO (2)
        │       ├─ interaction_id: 42
        │       ├─ url: "https://docs.../jira-perms"
        │       ├─ title: "Jira Permissions"
        │       ├─ chunk_id: "doc_55"
        │       └─ relevance_score: 0.82
        │
        └─► STEP 5: COMMIT transaction
            └─ All changes saved to data/ops_engine.db ✅
```

---

### PHASE 6: Response Display
```
UPDATE UI with answer
        │
        ├─► Display formatted answer
        │   └─ "To configure Jira, first..."
        │
        ├─► Show confidence score
        │   └─ "💡 Confidence Score: 87%"
        │
        ├─► Display source cards (Clickable)
        │   ├─ 📄 Jira Configuration Guide
        │   │   🔗 https://docs.../jira-setup
        │   │
        │   └─ 📄 Jira Permissions
        │       🔗 https://docs.../jira-perms
        │
        └─► Conversation visible to user
            (But ALSO in database for history!)
```

---

## Complete Database State After 2 Interactions

```sql
-- users table
┌────────────────────────────────────────────────┐
│ user_id            │ created_at      │ last_active   │
├────────────────────────────────────────────────┤
│ loknath_saha_2004  │ 2025-05-25 14:00:00 │ 2025-05-25 14:05:32 │
└────────────────────────────────────────────────┘

-- sessions table
┌──────────────────────────────────────────────────────────┐
│ session_id      │ user_id           │ engine_mode       │
├──────────────────────────────────────────────────────────┤
│ abc-123-xyz-def │ loknath_saha_2004 │ Confluence-H...   │
└──────────────────────────────────────────────────────────┘

-- interactions table (2 rows)
┌─────┬───────┬────────────────────────┬─────┬───────┬──────────┐
│ id  │ query │ answer                 │conf │ time  │ status   │
├─────┬───────┬────────────────────────┬─────┬───────┬──────────┤
│  41 │ "How  │ "First, check if you   │ 0.89│ 2341  │ success  │
│     │ do I  │ have Jira admin rights │     │       │          │
│     │ setup │ by logging in..."      │     │       │          │
│     │ Jira?"│                        │     │       │          │
├─────┼───────┼────────────────────────┼─────┼───────┼──────────┤
│  42 │ "What │ "In Jira, permissions  │ 0.92│ 1823  │ success  │
│     │ are   │ are managed through     │     │       │          │
│     │ Jira  │ Project Roles..."      │     │       │          │
│     │ roles?"│                       │     │       │          │
└─────┴───────┴────────────────────────┴─────┴───────┴──────────┘

-- sources table (4 rows - 2 per interaction)
┌────┬──────────┬────────────────────────┬──────────────┐
│ id │ int_id   │ url                    │ title        │
├────┼──────────┼────────────────────────┼──────────────┤
│  1 │ 41       │ https://docs/.../setup │ Jira Setup   │
│  2 │ 41       │ https://docs/.../perms │ Permissions  │
│  3 │ 42       │ https://docs/.../roles │ Project Roles│
│  4 │ 42       │ https://docs/.../admin │ Admin Guide  │
└────┴──────────┴────────────────────────┴──────────────┘
```

---

## Key Features Highlighted

### 1. **Automatic Initialization**
- Database created on first run
- All tables created with proper indexes
- Thread-safe for concurrent requests

### 2. **Complete Audit Trail**
- Every interaction timestamped
- Processing time measured
- Success/error status tracked
- Error messages logged

### 3. **Session Tracking**
- Multiple interactions grouped by session
- Multi-turn conversations linked
- Engine mode recorded per session

### 4. **Source Attribution**
- Each source tracked separately
- Relevance scores preserved
- Document titles and URLs stored
- Chunk IDs for traceability

### 5. **Confidence Scoring**
- Confidence metric (0.0-1.0) stored
- Allows filtering low-confidence responses
- Analytics available

### 6. **Performance Monitoring**
- Processing time tracked per interaction
- Average response time calculable
- Identify slow queries

---

## Example Queries

### Get all interactions from current session
```sql
SELECT i.query, i.answer, i.confidence_score, COUNT(s.source_id) as source_count
FROM interactions i
LEFT JOIN sources s ON i.interaction_id = s.interaction_id
WHERE i.session_id = 'abc-123-xyz-def'
GROUP BY i.interaction_id
ORDER BY i.created_at;
```

### Find failed interactions
```sql
SELECT * FROM interactions
WHERE execution_status = 'error'
ORDER BY created_at DESC
LIMIT 10;
```

### Get average performance by engine mode
```sql
SELECT s.engine_mode,
       COUNT(i.interaction_id) as count,
       AVG(i.confidence_score) as avg_conf,
       AVG(i.processing_time_ms) as avg_time
FROM interactions i
JOIN sessions s ON i.session_id = s.session_id
GROUP BY s.engine_mode;
```

### Find top referenced documents
```sql
SELECT url, title, COUNT(*) as reference_count
FROM sources
GROUP BY url
ORDER BY reference_count DESC
LIMIT 10;
```

---

## Summary

✅ Every user interaction is now **permanently stored** in SQLite
✅ Full **audit trail** with timestamps and processing metrics
✅ **Source attribution** for every answer
✅ **Session tracking** for multi-turn conversations
✅ **Performance metrics** for monitoring
✅ **Error logging** for debugging
✅ **Thread-safe** for production use

Database fully integrated and operational! 🚀
