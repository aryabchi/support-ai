# Feature: RAG-grounded follow-up dialog

Decision summary from design discussion. Prefer this doc + code over older notes when planning implementation.  
Source note: `notes/feature_rag.txt`. Architecture context: `docs/PROJECT_GUIDE.md`, `.cursor/rules/contribution.mdc`.

---

## 1. Initial feature statement

From `notes/feature_rag.txt`:

- Use **RAG in follow-up dialog** so that after the ticket is saved, discussion is grounded on relevant documents loaded into RAG.
- Keep a **ticket-first** approach: only follow-up becomes facts-oriented (wiki / Confluence-style docs).
- Intent: help the user solve the problem in a **fixed number of iterations**, so the already-created ticket can be closed **without support-team intervention**.

---

## 2. Architectural context (verified)

| Fact | Implication for this feature |
|------|------------------------------|
| Modular monolith; workflow in `app/agent/` | RAG belongs in agent layer, not a new service / `services/` package |
| `START → chat` always; follow-up skips triage when `ticket_id` is set | Retrieve must not break START→chat; no re-triage on follow-up |
| Chat history lives in LangGraph checkpoints | Dialog close ≠ ticket row update unless we explicitly call CRUD |
| Today goodbye only sets `dialog_closed` | Status `resolved`/`closed` is only via `PATCH` today |
| No RAG code under `app/` | `chromadb` / `langchain-qdrant` / `ragas` in deps are unused; `sentence-transformers` / `qdrant-client` commented out |
| Host Ollama for chat LLM; Compose has app + Postgres | Embeddings/Qdrant choices are new operational surface |

Closest existing hook: `chat_handler` prompt context + `route_after_chat` → `dialog_end`.

---

## 3. Decisions (condensed)

### When RAG runs
- **Follow-up only**, after `ticket_id` exists.
- Rationale: ticket-first; RAG payload filter needs triage results (`category`, and tags in the query).
- Create/triage path (`classifier → prioritizer → tagger → … → saver`) unchanged and does not call RAG.

### Retrieval placement (START → chat)
- Keep `START → chat`.
- Gate inside `chat_handler` (or helper it calls):  
  `ticket_id is not None` **and** `category is not None` → retrieve; else skip.
- On follow-up, checkpoint already has `category` / `tags` / `ticket_id` from the completed triage+save path.
- Create’s first `chat` has no `ticket_id` → no RAG (even though `category` is still unset at that moment).

### Query & filter
- Query: **latest user message + ticket category/tags** (v1).
- Qdrant payload filter by **category** (`technical` | `billing` | `feature` | `other`).
- May later add chat history to the query; not v1.

### Corpus & ingest
- Local markdown/text folder + **separate ingest script** (validate → chunk → embed → ids → upsert + payload: source name/path/text, **category**).
- Fake short docs (one file per doc, descriptive names) covering the four classifier categories.
- Live Confluence/wiki API: out of scope for v1.

### Vector store & embeddings
- **Qdrant** at `http://localhost:6333` via Settings (v1).
- Docker Compose Qdrant service: **not v1** (add later).
- Embeddings: **SentenceTransformer `all-MiniLM-L6-v2`** (384-d, HuggingFace), not Ollama embeddings.

### Failure behavior
- No hits / store down → **fall back to current ungrounded chat** + **log**.

### Turn budget
- Configurable max follow-up turns in `.env` / `.env.example`, mirrored in pydantic Settings (self-explanatory name; default e.g. **3**).
- Counter stored/updated in **graph state**, incremented each turn.
- When N reached → **forcibly close dialog**; ticket status **unchanged**.

### Dialog close paths

| Path | Trigger (v1 intent) | `dialog_closed` | Ticket status |
|------|---------------------|-----------------|---------------|
| Goodbye | Existing goodbye behavior (`пока`, `до свидания`, …) | yes | unchanged |
| Success close | User indicates help worked: `спасибо` / `помогло` / `спасибо, помогло` | yes | **`resolved`** |
| Escalate | User wants human support (agent suggestions not helpful) | yes | unchanged |
| N-cap | Follow-up turn budget reached | yes | unchanged |

- Success close is a **second path** alongside goodbye (not a replacement).
- Updating `resolved` is a **new** agent→CRUD write (via `crud/ticket.py` + `session` in config), not current behavior.

### Critical / HIL
- RAG for **all saved tickets** in v1 (may later depend on priority).

### API / observability
- **Optional** source document ids/paths on `ChatResponse` (additive).
- Log RAG responses / retrieval outcomes.

### Eval
- **Basic offline `ragas` eval** using the fake documents (not a substitute for mocked unit tests).

---

## 4. Test impact called out in discussion

- `tests/test_chat_history.py` → `test_thanks_without_goodbye_does_not_close_dialog` expects `"Спасибо, помогло!"` **not** to close.
- Success-close makes that input close + resolve → **update/replace** that test; add coverage for goodbye vs success-close paths (per contribution rules).

---

## 5. Remaining questions / uncertainties

1. **Turn counter scope** — Confirm increment only on follow-up messages after `ticket_id` (recommended), not the create message.
2. **Exact Settings key** — e.g. `RAG_MAX_FOLLOWUP_TURNS` (name TBD; must be self-explanatory).
3. **Success-phrase matching** — Bare substring `"спасибо"` risks mid-dialog false close (e.g. “Спасибо, а пароль?”). Prefer exact/normalized short utterances or “thanks without a new question.”
4. **Escalate detection** — Keywords vs LLM classifier; phrase list undefined.
5. **`ChatResponse` citation schema** — Field names/shape for ids/paths (optional list).
6. **Who writes `resolved`** — Confirm `chat_handler` (or small helper) calls `update_ticket` when success-close fires.
7. **Missing `category` with `ticket_id`** — Skip RAG + log vs search without filter.
8. **Ingest layout** — Concrete folder path, chunk size, collection name, Qdrant distance/metric.
9. **Unit vs offline eval** — Keep default `pytest` free of live Qdrant/HF/Ollama; put `ragas` in `scripts/` or optional marked suite.
10. **Deps** — Enable commented `sentence-transformers` / `qdrant-client` (and any transitive needs) explicitly in requirements.

---

## 6. Contradictions / tensions

### vs initial feature statement
| Topic | Note |
|-------|------|
| “Closed without support intervention” | Partially met: success-close → `resolved`; escalate / N-cap close dialog but **leave status unchanged** (ticket may still need humans). |
| “Wiki, Confluence, etc.” | v1 is **local fake/real markdown**, not live Confluence. |
| “Fixed amount of iterations” | Clarified as configurable hard cap + several close reasons — aligned in spirit. |

### vs “keep as today” wording (earlier answer)
| Topic | Note |
|-------|------|
| Ticket status on success | **Not** as today: agent will set `resolved`. Clarifications superseded the “leave status to PATCH only” option. |
| Success phrases | Intentionally changes current goodbye rules / the thanks test above. |

### vs project guide / contribution rules (watch during implementation)
| Topic | Note |
|-------|------|
| START → `chat` | Resolved by gated retrieve inside chat on follow-up only. |
| Minimize API surface | Optional citation fields OK if additive/backward compatible. |
| Embeddings | Diverges from Ollama-centric inference story (allowed; new host dependency / model download). |
| Qdrant URL | v1 localhost only; when Compose is added later, URL must follow local-vs-Docker pattern (`localhost` vs service hostname), like `DATABASE_URL`. |
| No `services/` package | Ingest stays in `scripts/`; runtime retrieve stays under `app/agent/`. |

### Internal product consistency
| Topic | Note |
|-------|------|
| Dialog close vs ticket resolve | Only **success close** sets `resolved`. Goodbye / escalate / N-cap close dialog only — explicit and consistent once documented. |

---

## 7. Suggested defaults for remaining items (not yet formally approved)

| Item | Suggested default |
|------|-------------------|
| Turn increment | Follow-up chats only (`ticket_id` already set) |
| Setting | `RAG_MAX_FOLLOWUP_TURNS=3` |
| Success match | Normalize; treat short thanks/helped as success; do not close if message still asks a question |
| Escalate | Keyword/phrases v1 (define list in plan) |
| No category | Skip RAG + log; ungrounded chat |
| Citations | Optional `sources: list[{id, path}] \| None` on `ChatResponse` |
| Eval | `scripts/` or optional pytest marker; fake docs |

---

## 8. Out of scope for v1 (explicit)

- Qdrant service in Docker Compose  
- Live Confluence/wiki sync  
- RAG on create response after save  
- Skipping RAG for critical/HIL  
- Query expansion with full chat history  
- Changing triage / HIL / alert routing  

---

## 9. Planning readiness

Enough is decided to draft an implementation plan. Before coding, lock the short list in §5 (especially turn scope, success-phrase matching, escalate detection, and citation schema).
