# Feature: RAG-grounded follow-up dialog

**Status:** implemented on branch `feature_rag` (v1).  
Design history: `notes/feature_rag.txt`. Step plan: `docs/implementation_plan_rag.md`.  
Architecture: `docs/PROJECT_GUIDE.md`, `.cursor/rules/contribution.mdc`.

---

## What it does

After a ticket is saved, follow-up chat can answer from a local knowledge base (fake markdown corpus in Qdrant) so the user may close the ticket without human intervention within a fixed turn budget.

| Concern | v1 behavior |
|---------|-------------|
| When RAG runs | Follow-up only: `ticket_id` **and** `category` set |
| Create / triage | Unchanged; no retrieve on first `chat` |
| Query | User message + ticket tags; Qdrant filter by `category` |
| Failure | Empty/error → ungrounded chat + warning log |
| Citations | Optional `source_paths` on `ChatResponse` |
| Resolve | Only **success close** (`спасибо` / `помогло`, short, no `?`) → `status=resolved` via `dialog_end` |

### Close paths

| Path | Trigger | `dialog_closed` | Ticket status |
|------|---------|-----------------|---------------|
| Goodbye | `пока`, `до свидания` (not success) | yes | unchanged |
| Success | Short thanks / helped (excludes `?`, length > 40, goodbye words) | yes | **`resolved`** |
| Escalate | Keywords (`оператор`, `не помог`, …) | yes | unchanged |
| N-cap | `followup_turn_count > RAG_MAX_FOLLOWUP_TURNS` | yes | unchanged |

Detection order: escalate → success → goodbye → turn_cap → RAG/normal chat.

Graph: `START → chat`; `route_after_chat` checks **`ticket_id` before `dialog_closed`** so success-close still reaches async `dialog_end`.

---

## Operations setup

### Prerequisites

1. Postgres + Ollama (same as app).
2. **Qdrant** on the host (not in Compose in v1), default `http://localhost:6333`.
3. Python deps: `qdrant-client`, `sentence-transformers` (see `requirements.txt`).
4. First run downloads HuggingFace model `all-MiniLM-L6-v2` (384-d).

### Env (`.env` / `.env.example`)

```env
# === RAG / Qdrant ===
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=support_ai_kb
RAG_TOP_K=3
RAG_EMBED_MODEL=all-MiniLM-L6-v2
RAG_MAX_FOLLOWUP_TURNS=2
RAG_DOCS_PATH=data/rag_docs
```

Settings live in `app/config.py`.

### Corpus and ingest

- Docs: `data/rag_docs/{technical,billing,feature,other}/*.md`
- Ingest (from repo root, venv `ai-course`):

```bash
python scripts/ingest_rag_docs.py
```

Chunk ~450 / overlap 50; payload `{category, source_path, text}`; deterministic point ids.

### Offline eval (optional, not default pytest)

```bash
python scripts/eval_rag.py --retrieval-only   # Qdrant smoke
python scripts/eval_rag.py                    # + ragas (needs Ollama judge)
```

---

## API

`ChatResponse` adds optional:

```json
"source_paths": ["technical/login_error_401.md"]
```

or `null` when RAG was not used. Mapped from state `rag_source_paths` on chat POST and GET.

---

## Manual E2E (PowerShell)

Assumptions: app on `:8080`, Qdrant ingested, `RAG_MAX_FOLLOWUP_TURNS=2`, fresh `thread_id` per scenario. Use `curl.exe` as in [README.md](../README.md). Replace `{TICKET_ID}` with `id` from create.

**Note:** Avoid escalate substrings like `не помог` in follow-ups meant to stay open (use e.g. «не сработал»).

### Scenario A — Success close → `resolved` + `source_paths`

```powershell
curl.exe -X POST "http://localhost:8080/tickets/" `
  -H "Content-Type: application/json" `
  -d '{"thread_id":"rag_success_001","user_input":"Не могу войти в аккаунт, ошибка 401"}'

# Note TICKET_ID from response

curl.exe -X POST "http://localhost:8080/tickets/chat/rag_success_001/messages" `
  -H "Content-Type: application/json" `
  -d '{"content":"Ошибка 401 при вводе пароля"}'

curl.exe -X POST "http://localhost:8080/tickets/chat/rag_success_001/messages" `
  -H "Content-Type: application/json" `
  -d '{"content":"Пробовал сброс пароля, не сработал"}'

curl.exe -X POST "http://localhost:8080/tickets/chat/rag_success_001/messages" `
  -H "Content-Type: application/json" `
  -d '{"content":"Спасибо, помогло!"}'

curl.exe "http://localhost:8080/tickets/chat/rag_success_001"
curl.exe "http://localhost:8080/tickets/{TICKET_ID}"
```

| Check | Expect |
|-------|--------|
| Follow-ups | `"done": false`; `"source_paths"` non-empty when Qdrant hits |
| Success message | `"done": true` |
| Ticket GET | `"status": "resolved"` |

### Scenario B — N-cap (dialog closes, status unchanged)

```powershell
curl.exe -X POST "http://localhost:8080/tickets/" `
  -H "Content-Type: application/json" `
  -d '{"thread_id":"rag_ncap_001","user_input":"Не могу войти в аккаунт"}'

curl.exe -X POST "http://localhost:8080/tickets/chat/rag_ncap_001/messages" `
  -H "Content-Type: application/json" `
  -d '{"content":"Ошибка 401 при вводе пароля"}'

curl.exe -X POST "http://localhost:8080/tickets/chat/rag_ncap_001/messages" `
  -H "Content-Type: application/json" `
  -d '{"content":"Сброс пароля не сработал"}'

curl.exe -X POST "http://localhost:8080/tickets/chat/rag_ncap_001/messages" `
  -H "Content-Type: application/json" `
  -d '{"content":"Что ещё можно попробовать?"}'

curl.exe "http://localhost:8080/tickets/chat/rag_ncap_001"
curl.exe "http://localhost:8080/tickets/{TICKET_ID}"

curl.exe -X POST "http://localhost:8080/tickets/chat/rag_ncap_001/messages" `
  -H "Content-Type: application/json" `
  -d '{"content":"Ещё вопрос"}'
```

| Check | Expect |
|-------|--------|
| Turns 1–2 | `"done": false` |
| Turn 3 | `"done": true`; `last_response` mentions лимит |
| Ticket | status **not** `resolved` |
| Extra message | HTTP 400, `"detail": "Диалог завершён"` |

### Scenario C — Goodbye (status unchanged)

```powershell
curl.exe -X POST "http://localhost:8080/tickets/" `
  -H "Content-Type: application/json" `
  -d '{"thread_id":"rag_goodbye_001","user_input":"Не могу войти в аккаунт"}'

curl.exe -X POST "http://localhost:8080/tickets/chat/rag_goodbye_001/messages" `
  -H "Content-Type: application/json" `
  -d '{"content":"Ошибка 401 при вводе пароля"}'

curl.exe -X POST "http://localhost:8080/tickets/chat/rag_goodbye_001/messages" `
  -H "Content-Type: application/json" `
  -d '{"content":"Спасибо, пока!"}'

curl.exe "http://localhost:8080/tickets/chat/rag_goodbye_001"
curl.exe "http://localhost:8080/tickets/{TICKET_ID}"
```

| Check | Expect |
|-------|--------|
| Goodbye | `"done": true`; farewell reply |
| Ticket | status **not** `resolved` |

---

## Code map

| Area | Location |
|------|----------|
| Gate, turns, prompts, close | `app/agent/nodes/chat_handler.py` |
| Resolve on success | `app/agent/nodes/dialog_end.py` |
| Routing | `app/agent/graph.py` |
| Embeddings / retrieve | `app/agent/rag/` |
| API `source_paths` | `app/api/schemas/ticket.py`, `app/api/routes/tickets.py` |
| Ingest / eval | `scripts/ingest_rag_docs.py`, `scripts/eval_rag.py` |
| Corpus | `data/rag_docs/` |

---

## Out of scope (v1)

- Qdrant in Docker Compose  
- Live Confluence/wiki sync  
- RAG on the create response after save  
- Skipping RAG for critical/HIL  
- Full chat history in the retrieve query  
