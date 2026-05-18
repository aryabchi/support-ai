# support-ai
AI Assistant for Support Service

# Tech Stack

- LangGraph (agents orchestration)
- FastAPI (endpoints)
- Ollama (LLMs)
- PostgreSQL (state persistence) 

# Features

- Agent graph with nodes and conditional edges
- Agent state persistence (AsyncPostgresSaver checkpointer)
- Input pydantic validation and sanitization
- Logging and LangSmith tracing
- Retry/fallback logic
- FastAPI endpoints
- Data models in SQLAlchemy

# Dependencies

- Python 3.11.9
- requirements.txt
- llama3.1:latest

`ollama pull llama3.1:latest`

- postgres:18-alpine via Docker

`docker run -d --name support-ai-db -e POSTGRES_USER=<your_user_name> -e POSTGRES_PASSWORD=<your_user_pass> -e POSTGRES_DB=support_db -p 5432:5432 -v postgres-data:/var/lib/postgresql postgres:18-alpine`
