# Support Service AI Agent 

LangGraph App for Support Service

# Core Business Use-Case

User submits incident via web request --> Agent classifies incident, sets priority and tags --> (If `critical` or `high` + `requires_approval`) Sends TG alert (currently disabled) --> (Otherwise or after HIL confirmation) Saves incident to database --> App saves Agent state and sends web response

# Agent Graph Flow

```mermaid
flowchart TD
    START([START]) --> classifier[classifier<br/>classify_ticket]
    classifier --> prioritizer[prioritizer<br/>prioritize_ticket]
    prioritizer --> tagger[tagger<br/>tag_ticket]

    tagger -->|route_after_tagger| R1{needs_alert?}
    R1 -->|yes| alert[alert<br/>send_critical_alert]
    R1 -->|no| R2{needs_confirmation?}
    R2 -->|yes| alert
    R2 -->|no| saver

    alert -->|route_after_alert| R3{needs_confirmation?}
    R3 -->|yes| confirmation[confirmation<br/>confirmation_node]
    R3 -->|no| saver[saver<br/>save_ticket]

    confirmation -->|route_after_confirmation| R4{confirmed is False?}
    R4 -->|yes / rejected| endNode[end<br/>done=True]
    R4 -->|no / approved| saver

    saver --> END([END])
    endNode --> END
```

# Tech Stack

- LangGraph (tasks orchestration)
- FastAPI (REST API endpoints)
- Ollama (LLMs)
- PostgreSQL (state persistence and datastore) 
- Docker (app containerization)

# Features

- Agent graph with LLM and deterministic nodes + conditional edges
- Human-in-the-Loop
- Agent state persistence (AsyncPostgresSaver checkpointer)
- FastAPI endpoints for http agent invocations
- Healthcheck endpoints
- Input pydantic validation and sanitization
- JSON logging and LangSmith tracing
- Retry/fallback logic on LLM calls 
- Data models in SQLAlchemy with Alembic migrations 
- Docker containers with App and Postgres storage (Ollama is NOT containerized) 
- Tests

# Dependencies

- Python 3.11.9
- see `requirements.txt`
- llama3.1:latest

```
ollama pull llama3.1:latest
```

- postgres:18-alpine via Docker


# Run the app locally

* In `.env` change

```python
DATABASE_URL=postgresql+asyncpg://support:support_pass@localhost:5432/support_db
# DATABASE_URL=postgresql+asyncpg://support:support_pass@db:5432/support_db

DB_HOST=localhost
# DB_HOST=db

OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_BASE_URL=http://host.docker.internal:11434
```

* Ensure Ollama service is running and `llama3.1:latest` is loaded

* Then run
```
docker run -d --name support-ai-db -e POSTGRES_USER=support -e POSTGRES_PASSWORD=support_pass -e POSTGRES_DB=support_db -p 5432:5432 -v postgres-data:/var/lib/postgresql postgres:18-alpine
```

```bash
uvicorn app.main:app --port 8080
```


# Try it out

HIL request (`high` + `requires_approval`)
```bash
curl -X POST "http://localhost:8080/tickets/" -H "Content-Type: application/json" -d "{\`"thread_id\`": \`"user_hil_002\`", \`"user_input\`": \`"Хочу удалить свой аккаунт\`"}"  
```
Response
```
{"thread_id":"user_hil_002","user_input":"Хочу удалить свой аккаунт","category":"other","priority":"high","tags":["feature","access"],"status":"awaiting_confirmation","id":0,"created_at":"2026-07-31T17:43:09.956856Z","updated_at":"2026-07-31T17:43:09.956856Z"}
```

User confirms action

```bash
curl -X POST "http://localhost:8080/tickets/confirm" -H "Content-Type: application/json" -d "{\`"thread_id\`": \`"user_hil_002\`", \`"decision\`": \`"yes\`"}
```
Response
```
{"ticket_id":6,"confirmed":true,"status":"in_progress","message":null}
```

Check status
```bash
curl http://localhost:8080/tickets/6
```

Response
```
{"thread_id":"user_hil_002","user_input":"Хочу удалить свой аккаунт","category":"other","priority":"high","tags":["feature","access"],"status":"in_progress","id":6,"created_at":"2026-07-31T17:43:37.899160Z","updated_at":"2026-07-31T17:43:37.899160Z"}
```

Not HIL request (`critical`)

```bash
curl -X POST "http://localhost:8080/tickets/" -H "Content-Type: application/json" -d 
"{\`"thread_id\`": \`"user_crit_001\`", \`"user_input\`": \`"Все упало, ничего не работает, пользователи не могут войти\`"}"
```

Response
```
{"thread_id":"user_crit_001","user_input":"Все упало, ничего не работает, пользователи не могут войти","category":"technical","priority":"critical","tags":["login","error","crash"],"status":"in_progress","id":7,"created_at":"2026-07-31T17:51:36.708119Z","updated_at":"2026-07-31T17:51:36.708119Z"}
```