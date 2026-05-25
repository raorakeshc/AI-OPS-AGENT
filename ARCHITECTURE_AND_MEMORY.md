# Architecture, Flows, Components, and Memory Policy

This document describes the system architecture, component roles, request/tool routing, multi-step task decomposition, and memory scope/retention/reset policies for the AI-OPS Agent project.

## Components & Roles

- SupportAgent (`src/support_agent.py`): orchestrates intent detection, prompt construction, tool selection, and final response formatting. Responsible for safety rules (no hallucination) and single-action-per-turn enforcement.
- Retriever / RAG (`src/rag.py`): builds and persists a Chroma vector store from `data/kb.txt`, exposes a retriever to surface KB snippets for policy and FAQ queries.
- Order Store (`src/order_store.py`): SQLite-backed store for shipment/order status; provides `init_db`, `get_order_status`, `upsert_order`, `list_orders`, and `migrate_from_json` utilities.
- Orders API (`src/orders_api.py`): FastAPI service that exposes order status endpoints and uses `order_store` as the source of truth (with legacy JSON export for human readability).
- Streamlit UI (`src/app.py`): user-facing interface that accepts user queries and shows conversation history; communicates with the `SupportAgent` backend.
- Tools: small, well-scoped adapters that expose constrained functionality to the LLM:
  - `get_order_status(order_id)`: returns factual shipping state from the Orders API / SQLite store.
  - `search_knowledge_base(query)`: returns KB snippets from the RAG retriever.

## High-Level Request Flow

1. User sends a query via UI or API.
2. `SupportAgent` extracts recent user text and context (active order id, previous tool outputs) and evaluates intent using deterministic heuristics and regexes.
3. The agent builds a structured prompt that includes:
   - System identity and task constraints
   - Safety & task guidelines (tool selection rules, no hallucination)
   - Current context (active order id, last tool usage)
   - A required reply format: `Action`, `Reasoning`, `Response`.
4. Agent chooses a single action:
   - `TOOL_CALL` → call `get_order_status` or `search_knowledge_base`.
   - `DIRECT_ANSWER` → produce a customer-facing answer without tool use.
5. If `TOOL_CALL`, the agent calls the tool, obtains results, and summarizes them in the `Response`. If the tool reveals missing information (e.g., no order id), the agent asks a clarifying question.

## Tool Scoping & Routing Logic (Explainable)

- Intent signals:
  - KB intent: presence of keywords like `refund`, `return`, `policy`, or `?` in the last user text.
  - Status intent: keywords like `track`, `status`, `where is my order`, and numeric order ID patterns.
- Routing decision: a small deterministic decision tree in `SupportAgent._build_dynamic_prompt` maps signals to the single action. The prompt then instructs the LLM to follow that decision and return `Action` + `Reasoning`.
- Auditable outcome: because the reply format requires `Action` and `Reasoning`, it is possible to log and audit why a tool was selected.

## Multi-step / Task Decomposition Example

Example user request: "My order 123 is delayed and I want a refund — what do I do?"

Decomposed steps the agent should perform:
1. Identify active order ID (`123`) and classify intent (status + escalation/refund).
2. Call `get_order_status(123)` to confirm current shipping state.
3. If status is `Delivered` or `Returned`, route to refund steps; otherwise, call `search_knowledge_base("refund policy electronics")` to find eligibility windows.
4. Summarize findings and present next operational steps (how to file claim, time windows, evidence required).

This decomposition is encoded in the prompt's Task Flow section (order status → KB lookup → escalate/advise). The agent executes one atomic tool call per turn and then returns a clear next-step instruction for the user or system.

## Memory: Scopes, Retention, Reset, and Impact

Memory is intentionally simple and separated into three scopes:

- **Session Memory** (`/memories/session/`): short-lived, conversation-scoped state (active_order_id, last tool results). Cleared when the session ends or after a TTL (configurable). Use cases: keeping track of multi-turn clarifications, tool results between steps.
- **Repository Memory** (`/memories/repo/`): project-scoped facts and conventions (KB build metadata, verified training artifacts). Intended for maintainers, not user data. Persisted in repository and only changed by code or explicit migration scripts.
- **User Memory** (`/memories/`): optional, user-specific preferences (preferred tone, frequent questions). If enabled, keep minimal, allow opt-out, store only non-sensitive preferences, and enforce retention policies.

Retention & reset rules:
- Session Memory: TTL default 1 hour (configurable via `AgentConfig.thread_ttl_seconds`); resets on session close.
- User Memory: retain for 30 days by default; require explicit consent and offer a reset API/CLI to erase a user's memory.
- Repo Memory: manual control; reset only via maintainer commands.

Privacy/safety note: never store secrets (API keys, passwords, PII) in any memory scope. Inputs longer than `SecurityConfig.max_input_length` are truncated.

Impact on quality:
- Short retention (session-only) keeps responses focused and reduces stale context problems but requires explicit re-provisioning of state (order ids) from users.
- Long retention improves personalization and reduces repeated clarifications but increases risk of stale/incorrect assumptions and privacy exposure.

## Memory Management Recommendations

- Provide a `POST /memory/reset` admin endpoint (or CLI) to clear session and/or user memory for a thread id.
- Log memory actions (create/read/delete) with minimal metadata to aid debugging without exposing sensitive contents.
- For production, prefer a secure, encrypted store with audit logging and role-based access.

## Example of a Multi-step Plan Format (for internal planning)

1. Verify order status for `order_id`.
2. If `status` == `Delivered`:
   - Check return eligibility via KB.
   - If eligible, provide refund initiation steps.
3. If `status` in transit/delayed:
   - Open carrier investigation (operational step), then inform customer of expected timeline.

Represent plans as an ordered TODO for the agent or operators; each bullet is a single, testable step.

---

If you want, I can:
- add a small `scripts/memory_reset.py` and `src/admin_memory.py` endpoints to demonstrate reset mechanics, or
- create a short notebook that runs example multi-step scenarios showing the action/reasoning/response outputs.
