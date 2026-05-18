# support-ai
AI Assistant for Support Service

# Description
**TBD**

# Tech Stack

- LangGraph (agents orchestration)
- FastAPI (endpoints)
- Ollama (LLMs)
- PostgreSQL (state persistence) 

# Features

- Agent graph with LLM and deterministic nodes and conditional edges
- Agent state persistence (AsyncPostgresSaver checkpointer)
- Input pydantic validation and sanitization
- Logging and LangSmith tracing
- Retry/fallback logic
- FastAPI endpoints
- Data models in SQLAlchemy
- Docker containers with App and db (Ollama models on localhost) 

# Dependencies

- Python 3.11.9
- requirements.txt
- llama3.1:latest

```
ollama pull llama3.1:latest
```

- postgres:18-alpine via Docker

```
docker run -d --name support-ai-db -e POSTGRES_USER=<your_user_name> -e POSTGRES_PASSWORD=<your_user_pass> -e POSTGRES_DB=support_db -p 5432:5432 -v postgres-data:/var/lib/postgresql postgres:18-alpine
```

# Try it out

Sample request #1
```curl -X 'POST' \
  'http://localhost:8080/tickets/' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{"thread_id": "docker_test_001", "user_input": "Не работает вход в систему"}'
```

Expected response

```
{
  "thread_id": "docker_test_001",
  "user_input": "Не работает вход в систему",
  "category": "technical",
  "priority": "high",
  "tags": [
    "login",
    "error",
    "bug"
  ],
  "status": "new",
  "id": 1,
  "created_at": "2026-05-18T20:00:20.405998Z",
  "updated_at": "2026-05-18T20:00:20.405998Z"
}
```

Sample request #2

```
curl -X 'POST' \
  'http://localhost:8080/tickets/' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{"thread_id": "docker_test_critical_002", "user_input": "Система не работает, данные пропали, пользовали не могут войти, логи не читаются"}'
```

Expected response

```
{
  "thread_id": "docker_test_critical_002",
  "user_input": "Система не работает, данные пропали, пользовали не могут войти, логи не читаются",
  "category": "technical",
  "priority": "critical",
  "tags": [
    "error",
    "crash",
    "bug"
  ],
  "status": "new",
  "id": 2,
  "created_at": "2026-05-18T20:08:05.491351Z",
  "updated_at": "2026-05-18T20:08:05.491351Z"
}
```