# 🚀 SQLite Database - Quick Start Guide

## 5-Minute Setup

### 1. Database is Already Integrated! ✅
All files have been created and integrated:
```
✅ src/db/models.py       - Data structures
✅ src/db/database.py     - Core database operations
✅ src/db/__init__.py     - Package exports
✅ main.py (modified)     - Database integration points
```

### 2. Start Your App
```bash
cd c:/Users/hp/Desktop/ops_engine
chainlit run main.py
```

### 3. Database Automatically Created
After first message, check:
```bash
ls -la data/ops_engine.db
```

### 4. Query Your Data
```bash
python scripts/query_interactions.py --user loknath_saha_2004
```

---

## What Gets Stored?

| Field | Example | Purpose |
|-------|---------|---------|
| Query | "How do I set up Jira?" | User's question |
| Answer | "To set up Jira, first..." | AI response |
| Confidence | 0.87 | Answer confidence (0-1) |
| Processing Time | 2341ms | Response time |
| Sources | [url1, title1, ...] | Reference documents |
| Status | "success" | Execution result |
| Timestamp | 2025-05-25 14:32:01 | When stored |

---

## Data Flow (Simple)

```
User sends message
        ↓
App processes with AI
        ↓
Extract: answer, confidence, sources, timing
        ↓
STORE IN DATABASE ✅
        ↓
Show response to user
```

---

## Useful Commands

### View Recent Interactions
```bash
# Last 10 interactions for a user
python scripts/query_interactions.py --user loknath_saha_2004 --limit 10

# Analytics overview
python scripts/query_interactions.py --analytics

# List all users
python scripts/query_interactions.py --list-users
```

### Direct Database Query
```bash
# Open SQLite CLI
sqlite3 data/ops_engine.db

# See all interactions
SELECT * FROM interactions LIMIT 5;

# See interactions with sources
SELECT i.query, i.answer, s.url, s.title 
FROM interactions i 
LEFT JOIN sources s ON i.interaction_id = s.interaction_id 
LIMIT 10;
```

### In Python Code
```python
from src.db import get_db_manager

db = get_db_manager()

# Get user's history
history = db.get_interaction_history('loknath_saha_2004', limit=50)

# Get analytics
stats = db.get_analytics('loknath_saha_2004')
print(f"Total interactions: {stats['total_interactions']}")
print(f"Avg confidence: {stats['average_confidence']}")
```

---

## Key Concepts

### 📊 Tables

**users** - Who is chatting
```
loknath_saha_2004 | created_at | last_active
```

**sessions** - Each conversation thread
```
session-123 | user-id | engine_mode | status
```

**interactions** - Each query-answer pair
```
id | session_id | query | answer | confidence | sources | time_ms
```

**sources** - Reference documents used
```
id | interaction_id | url | title | relevance_score
```

### 🔄 Relationships
```
user (1) ──→ many sessions
session (1) ──→ many interactions
interaction (1) ──→ many sources
```

---

## Files Created

| File | Purpose |
|------|---------|
| `src/db/models.py` | Data structures |
| `src/db/database.py` | DB operations & schema |
| `src/db/__init__.py` | Package exports |
| `scripts/query_interactions.py` | Query utility |
| `SETUP_DATABASE.md` | Complete setup guide |
| `DATABASE_FLOW.md` | Detailed flow diagrams |
| `QUICK_START.md` | This file |

---

## Files Modified

| File | Changes |
|------|---------|
| `main.py` | Added database imports & calls |

---

## Troubleshooting

**Q: Database file not created?**
- Check if `data/` directory exists and is writable
- Send a message to the chatbot

**Q: No interactions stored?**
- Check console logs for `[Database]` messages
- Verify database initialization: `sqlite3 data/ops_engine.db ".tables"`

**Q: Queries slow?**
- Run: `sqlite3 data/ops_engine.db "VACUUM;"`

**Q: Multiple errors?**
- Reset: Delete `data/ops_engine.db` and restart

---

## Next Steps

1. ✅ Run the app: `chainlit run main.py`
2. ✅ Send some test messages
3. ✅ Query the database: `python scripts/query_interactions.py --list-users`
4. ✅ Review the data: `SETUP_DATABASE.md`
5. ✅ Explore the flow: `DATABASE_FLOW.md`

---

## Performance Notes

- **Single app instance**: SQLite is perfect ✓
- **10K interactions**: Still fast ✓
- **100K interactions**: Getting slow, consider archiving
- **1M+ interactions**: Migrate to PostgreSQL

---

## Support

Need more details?
- See `SETUP_DATABASE.md` for complete setup guide
- See `DATABASE_FLOW.md` for detailed data flow
- Check database schema in `src/db/database.py` lines 25-110

---

**Database is now live and storing all interactions!** 🎉
