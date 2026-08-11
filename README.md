# Support Service AI Agent 

LangGraph App for Support Service

# Core Business Use-Case

User submits incident via API request  
→ Agent starts chat  
→ (If no incident ticket yet) Agent classifies incident, sets priority and tags  
→ (If `critical` or `high` + `requires_approval`) Sends TG alert (currently disabled)  
→ (Otherwise or after HIL confirmation) Saves incident to database  
→ App saves Agent state and sends web response  
→ (Unless dialog is closed: goodbye / success / escalate / turn cap) Follow-up chat may continue via new API calls; follow-ups can use RAG when Qdrant is available

# Agent Graph Flow

```mermaid
flowchart TD
    START([START]) --> chat[chat<br/>chat_handler]

    chat -->|route_after_chat| R0{ticket_id set?}
    R0 -->|yes: follow-up| dialogEnd[dialog_end<br/>resolve on success]
    R0 -->|no| R0b{dialog_closed?}
    R0b -->|yes| endNode[end<br/>dialog_closed=True]
    R0b -->|no: new ticket| classifier[classifier<br/>classify_ticket]

    classifier --> prioritizer[prioritizer<br/>prioritize_ticket]
    prioritizer --> tagger[tagger<br/>tag_ticket]

    tagger -->|route_after_tagger| R1{needs_alert?}
    R1 -->|yes| alert[alert<br/>send_critical_alert]
    R1 -->|no| R2{needs_confirmation?}
    R2 -->|yes| alert
    R2 -->|no| saver[saver<br/>save_ticket]

    alert -->|route_after_alert| R3{needs_confirmation?}
    R3 -->|yes| confirmation[confirmation<br/>confirmation_node]
    R3 -->|no| saver

    confirmation -->|route_after_confirmation| R4{confirmed is False?}
    R4 -->|yes / rejected| endNode
    R4 -->|no / approved| saver

    saver --> END([END])
    endNode --> END
    dialogEnd --> END
```

# Tech Stack

- LangGraph (tasks orchestration)
- FastAPI (REST API endpoints)
- Ollama (LLMs)
- PostgreSQL (state persistence and datastore)
- Qdrant (RAG vector store; host process, not in Compose for v1)
- SentenceTransformers / HuggingFace MiniLM (embeddings)
- Docker (app + Postgres containerization)

# Features

- Human-in-the-Loop
- Multiturn dialog (chat with history)
- RAG-grounded dialog follow-up (Qdrant + MiniLM)
- Dialog close: goodbye / success→ticket status `resolved` / escalate / turns limit hit
- Agent graph with LLM and deterministic nodes + conditional edges
- Agent state persistence (AsyncPostgresSaver checkpointer)
- FastAPI endpoints for http agent invocations
- Healthcheck endpoints
- Pydantic validation and sanitization
- JSON logging and LangSmith tracing
- Retry/fallback logic on LLM calls 
- Data models in SQLAlchemy with Alembic migrations 
- Docker containers with App and Postgres storage (Ollama is NOT containerized) 
- Pytests

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
uvicorn app.main:app --port=8080 --reload
```

# Test RAG follow-up (optional)

Full feature notes and E2E curls: [`docs/feature_rag.md`](docs/feature_rag.md).

1. Run Qdrant locally as Docker (default `http://localhost:6333`). **Not part** of Compose in v1.
Sample `docker-compose.yml`
```yml
services:
  qdrant:
    image: qdrant/qdrant:latest
    container_name: qdrant
    ports:
      - "6333:6333"   # REST API + Web UI
      - "6334:6334"   # gRPC API
    volumes:
      - ./qdrant_storage:/qdrant/storage
    environment:
      QDRANT__LOG_LEVEL: INFO
    restart: unless-stopped
    mem_limit: 4g
    cpus: 2
    healthcheck:
      test: ["CMD-SHELL", "bash -c ':> /dev/tcp/127.0.0.1/6333' || exit 1"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
```
2. Ensure `.env` includes the RAG block (see `.env.example`):

```env
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=support_ai_kb
RAG_TOP_K=3
RAG_EMBED_MODEL=all-MiniLM-L6-v2
RAG_MAX_FOLLOWUP_TURNS=2
RAG_DOCS_PATH=data/rag_docs
```

3. Ingest corpus:

```bash
python scripts/ingest_rag_docs.py
```

4. Optional offline eval:

```bash
python scripts/eval_rag.py --retrieval-only
```

Follow-up chat responses may include `"source_paths": ["technical/....md"]` when retrieval hits. Success phrase `"Спасибо, помогло!"` closes the dialog and sets ticket `status` to `resolved`.


# Test HIL Interrupt/Resume

HIL request (`user_input` contains "удалить" -> `high` + `requires_approval`)
```bash
curl.exe -X POST "http://localhost:8080/tickets/" -H "Content-Type: application/json" -d "{\`"thread_id\`": \`"user_hil_002\`", \`"user_input\`": \`"Хочу удалить свой аккаунт\`"}"  
```

Response
```
{"thread_id":"user_hil_002","user_input":"Хочу удалить свой аккаунт","category":"other","priority":"high","tags":["feature","access"],"status":"awaiting_confirmation","id":0,"created_at":"2026-07-31T17:43:09.956856Z","updated_at":"2026-07-31T17:43:09.956856Z"}
```

User confirms action
```bash
curl.exe -X POST "http://localhost:8080/tickets/confirm" -H "Content-Type: application/json" -d "{\`"thread_id\`": \`"user_hil_002\`", \`"decision\`": \`"yes\`"}
```

Response
```
{"ticket_id":6,"confirmed":true,"status":"in_progress","message":null}
```

Check status
```bash
curl.exe http://localhost:8080/tickets/6
```

Response
```
{"thread_id":"user_hil_002","user_input":"Хочу удалить свой аккаунт","category":"other","priority":"high","tags":["feature","access"],"status":"in_progress","id":6,"created_at":"2026-07-31T17:43:37.899160Z","updated_at":"2026-07-31T17:43:37.899160Z"}
```

Not HIL request (`critical`)
```bash
curl.exe -X POST "http://localhost:8080/tickets/" -H "Content-Type: application/json" -d 
"{\`"thread_id\`": \`"user_crit_001\`", \`"user_input\`": \`"Все упало, ничего не работает, пользователи не могут войти\`"}"
```

Response
```
{"thread_id":"user_crit_001","user_input":"Все упало, ничего не работает, пользователи не могут войти","category":"technical","priority":"critical","tags":["login","error","crash"],"status":"in_progress","id":7,"created_at":"2026-07-31T17:51:36.708119Z","updated_at":"2026-07-31T17:51:36.708119Z"}
```

# Test Multiturn Dialog with History

Request #1 (`user_input` doesn't contain keywords that trigger HIL interrupt/confirmation)
```bash
curl.exe -X POST "http://localhost:8080/tickets/" -H "Content-Type: application/json" -d "{\`"thread_id\`": \`"chat_test_002\`", \`"user_input\`": \`"Не могу войти в аккаунт\`"}"

```

Response
```
{"thread_id":"chat_test_002","user_input":"Не могу войти в аккаунт","category":"technical","priority":"high","tags":["login","error"],"status":"new","id":9,"created_at":"2026-08-01T18:24:32.285416Z","updated_at":"2026-08-01T18:24:32.285416Z","last_response":"Пожалуйста, проверьте правильность логина и пароля. Если проблема persists, попробуйте сбросить пароль или связаться с нами для дальнейшей помощи.","messages_count":2}
```

Request #2 (continue chat)
```bash
curl.exe -X POST "http://localhost:8080/tickets/chat/chat_test_002/messages" -H "Content-Type: application/json" -d "{\`"content\`": \`"Ошибка 401 при вводе пароля\`"}"
```

Response
```
{"thread_id":"chat_test_002","messages":[{"role":"user","content":"Не могу войти в аккаунт"},{"role":"assistant","content":"Пожалуйста, проверьте правильность логина и пароля. Если проблема persists, попробуйте сбросить пароль или связаться с нами для дальнейшей помощи."},{"role":"user","content":"Ошибка 401 при вводе пароля"},{"role":"assistant","content":"Попробуйте войти в аккаунт через браузер или другое устройство, чтобы исключить проблему с конкретным девайсом. Если проблема persists, давайте попробуем сбросить пароль вместе. Вы согласны?"}],"last_response":"Попробуйте войти в аккаунт через браузер или другое устройство, чтобы исключить проблему с конкретным девайсом. Если проблема persists, давайте попробуем сбросить пароль вместе. Вы согласны?","done":false,"ticket_id":9,"category":"technical","priority":"high"}
```

Request #3 (chat history)
```bash
curl.exe http://localhost:8080/tickets/chat/chat_test_002
```

Response
```
{"thread_id":"chat_test_002","messages":[{"role":"user","content":"Не могу войти в аккаунт"},{"role":"assistant","content":"Пожалуйста, проверьте правильность логина и пароля. Если проблема persists, попробуйте сбросить пароль или связаться с нами для дальнейшей помощи."},{"role":"user","content":"Ошибка 401 при вводе пароля"},{"role":"assistant","content":"Попробуйте войти в аккаунт через браузер или другое устройство, чтобы исключить проблему с конкретным девайсом. Если проблема persists, давайте попробуем сбросить пароль вместе. Вы согласны?"}],"last_response":"Попробуйте войти в аккаунт через браузер или другое устройство, чтобы исключить проблему с конкретным девайсом. Если проблема persists, давайте попробуем сбросить пароль вместе. Вы согласны?","done":false,"ticket_id":9,"category":"technical","priority":"high"}
```

Request #4 ("пока" ends chat)
```bash
curl.exe -X POST "http://localhost:8080/tickets/chat/chat_test_002/messages" -H "Content-Type: application/json" -d "{\`"content\`": \`"Спасибо, пока!\`"}"
```

Response
```
{"thread_id":"chat_test_002","messages":[{"role":"user","content":"Не могу войти в аккаунт"},{"role":"assistant","content":"Пожалуйста, проверьте правильность логина и пароля. Если проблема persists, попробуйте сбросить пароль или связаться с нами для дальнейшей помощи."},{"role":"user","content":"Ошибка 401 при вводе пароля"},{"role":"assistant","content":"Попробуйте войти в аккаунт через браузер или другое устройство, чтобы исключить проблему с конкретным девайсом. Если проблема persists, давайте попробуем сбросить пароль вместе. Вы согласны?"},{"role":"user","content":"Спасибо, пока!"},{"role":"assistant","content":"Приятно было вам помочь! До свидания!"}],"last_response":"Приятно было вам помочь! До свидания!","done":true,"ticket_id":9,"category":"technical","priority":"high"}
```

Request #5 (attempt to continue when `dialog_closed=True`)
```bash
curl.exe -X POST "http://localhost:8080/tickets/chat/chat_test_002/messages" -H "Content-Type: application/json" -d "{\`"content\`": \`"BULLSHIT\`"}
```

Response
```
{"detail":"Диалог завершён"}
```