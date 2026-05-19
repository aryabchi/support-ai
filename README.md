# Support Service AI Agent 
LangGraph App for Support Service

# Core business use-case
User submits incident via web request -> Agent classifies incident, sets priority and tags -> (If "critical") Sends alert -> (Otherwise) Saves incident to database -> App saves Agent state and sends web response

# Tech Stack

- LangGraph (tasks orchestration)
- FastAPI (REST API endpoints)
- Ollama (LLMs)
- PostgreSQL (state persistence and datastore) 

# Features

- Agent graph with LLM and deterministic nodes and conditional edges
- Agent state persistence (AsyncPostgresSaver checkpointer)
- FastAPI endpoints for http agent invocations
- Healthcheck endpoints
- Input pydantic validation and sanitization
- JSON logging and LangSmith tracing
- Retry/fallback logic on LLM calls 
- Data models in SQLAlchemy with Alembic migrations 
- Docker containers with App and Postgres storage (Ollama is NOT containerized) 

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