# SupportAI — Architecture

LangGraph-based support ticket processing API. A user submits an incident via HTTP; the agent classifies it, sets priority and tags, optionally sends a Telegram alert for critical cases, and persists the ticket to PostgreSQL.

## Tech stack

| Component | Role |
|-----------|------|
| **FastAPI** | REST API; `POST /tickets/` runs the agent |
| **LangGraph** | Orchestrates nodes with conditional routing |
| **Ollama** | Local LLM (`ChatOllama`) for classify / prioritize / tag |
| **PostgreSQL** | Tickets + LangGraph checkpoint tables |
| **Telegram** | Optional alert for `critical` priority |
| **LangSmith** | Optional tracing via env vars in `llm.py` |
| **Docker** | App + Postgres (`docker-compose`); Ollama runs on the host |

---

## System overview (runtime)

```mermaid
flowchart TB
    subgraph Client
        UI[Web / curl client]
    end

    subgraph Docker["Docker (docker-compose)"]
        APP[FastAPI app<br/>uvicorn :8080]
        PG[(PostgreSQL<br/>tickets + checkpoints)]
    end

    subgraph Host["Host (not in Docker)"]
        OLLAMA[Ollama<br/>ChatOllama API :11434]
    end

    subgraph External
        TG[Telegram Bot API]
        LS[LangSmith<br/>optional tracing]
    end

    UI -->|HTTP REST| APP
    APP --> PG
    APP -->|LLM invoke| OLLAMA
    APP -->|critical alert| TG
    APP -.->|env LANGSMITH_*| LS
    OLLAMA -.-> LS
```

---

## Application layers

```mermaid
flowchart TB
    subgraph API["app/api"]
        R1["/tickets/*"]
        R2["/health"]
        SCH[Pydantic schemas]
    end

    subgraph Core["app/core"]
        DEP[get_agent_graph<br/>get_telegram_client]
    end

    subgraph Agent["app/agent"]
        G[graph.py<br/>StateGraph]
        N[nodes/]
        ST[state.py AgentState]
        LLM[llm.py ChatOllama]
        CP[checkpointer.py]
        RT[retry.py]
    end

    subgraph Data["app/db + crud"]
        SESS[session.py]
        MOD[models: Ticket, History]
        CRUD[crud/ticket.py]
    end

    subgraph CrossCutting
        CFG[config.py Settings]
        SEC[security/sanitizers]
        LOG[logging_config]
    end

    MAIN[main.py FastAPI] --> API
    R1 --> DEP
    R1 --> Agent
    R1 --> CRUD
    N --> LLM
    N --> SEC
    N --> CRUD
    G --> N
    G --> ST
    CP --> PG[(PostgreSQL)]
    CRUD --> SESS --> PG
    Agent --> CFG
    API --> CFG
```

---

## Ticket creation flow

```mermaid
sequenceDiagram
    participant C as Client
    participant API as POST /tickets/
    participant CP as AsyncPostgresSaver
    participant G as LangGraph agent
    participant LLM as Ollama
    participant TG as Telegram
    participant DB as PostgreSQL

    C->>API: TicketCreate(thread_id, user_input)
    API->>CP: open checkpointer
    API->>G: ainvoke(AgentState, config)
    Note over G: config: session, telegram_client, thread_id

    G->>G: classifier (LLM)
    G->>LLM: invoke
    LLM-->>G: category

    G->>G: prioritizer (LLM)
    G->>LLM: invoke
    LLM-->>G: priority

    G->>G: tagger (LLM)
    G->>LLM: invoke
    LLM-->>G: tags JSON

    alt priority == critical
        G->>TG: send_critical_alert
    end

    G->>DB: saver → ticket_crud.create
    G-->>API: AgentState + ticket_id
    API->>DB: get_ticket_by_id
    API-->>C: TicketResponse 201
    CP->>DB: checkpoint writes
```

---

## LangGraph agent (nodes & routing)

Linear chain: **classifier → prioritizer → tagger**.

Branch: **tagger → alert** when `priority == "critical"` and alert not sent yet; otherwise **tagger → saver**. **alert** always continues to **saver**.

```mermaid
stateDiagram-v2
    [*] --> classifier: START

    classifier --> prioritizer: always
    prioritizer --> tagger: always

    tagger --> alert: needs_alert()\npriority == critical
    tagger --> saver: else

    alert --> saver: always
    saver --> [*]: END

    note right of classifier
        LLM + sanitizers + retry
        → category
    end note

    note right of prioritizer
        LLM + retry
        → priority
    end note

    note right of tagger
        LLM + JSON parse
        → tags
    end note

    note right of alert
        async httpx → Telegram
        (non-fatal if misconfigured)
    end note

    note right of saver
        async SQLAlchemy
        → tickets table
    end note
```

---

## AgentState through the pipeline

```mermaid
flowchart LR
    IN["thread_id<br/>user_input"]
    C["+ category"]
    P["+ priority"]
    T["+ tags<br/>reasoning"]
    A["+ alert_sent"]
    OUT["+ ticket_id<br/>done"]

    IN --> C --> P --> T --> A --> OUT
```

Errors are stored on `error`. Validation or injection failures in classifier/tagger short-circuit with safe defaults (e.g. `category: other`).

---

## Repository layout

```text
support-ai/
├── app/
│   ├── main.py              # FastAPI app, CORS, lifespan
│   ├── config.py            # Settings (.env)
│   ├── api/routes/          # tickets, health
│   ├── core/dependencies.py # graph builder, Telegram client
│   ├── agent/
│   │   ├── graph.py         # StateGraph wiring
│   │   ├── state.py         # AgentState
│   │   ├── llm.py           # ChatOllama singleton
│   │   ├── checkpointer.py  # LangGraph Postgres checkpoints
│   │   ├── retry.py         # tenacity on LLM calls
│   │   └── nodes/           # classifier, prioritizer, tagger, alert, saver
│   ├── crud/ticket.py
│   ├── db/                  # SQLAlchemy models, session
│   └── security/sanitizers.py
├── alembic/                 # DB migrations
├── tests/
├── docs/
│   └── architecture.md      # this file
└── docker-compose.yml       # app + postgres (Ollama on host)
```

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/tickets/` | Create ticket via agent pipeline |
| `GET` | `/tickets/` | List tickets by `thread_id` |
| `GET` | `/tickets/{id}` | Get ticket by id |
| `PATCH` | `/tickets/{id}` | Partial update |
| `DELETE` | `/tickets/{id}` | Delete ticket |
| `GET` | `/health` | Health check |
| `GET` | `/` | API info + docs links |
