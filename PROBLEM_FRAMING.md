# Problem Framing: AI-OPS Logistics Support Agent

## 1. Problem Statement

In modern logistics and e-commerce, customer support is overwhelmed by high volumes of repetitive, time-sensitive queries. Industry data shows that 60–70 % of Tier-1 support tickets fall into three categories: **order-status inquiries**, **policy/FAQ lookups**, and **escalation requests** for missing or delayed shipments. Traditional rule-based chatbots and static FAQ pages fail to handle these because they lack:

1. **Contextual Awareness** — They cannot distinguish a general policy question from an order-specific complaint, leading to irrelevant responses.
2. **Real-Time Tool Integration** — They cannot securely query live order-tracking APIs and combine the result with conversational context.
3. **Multi-Step Reasoning** — They struggle with complex flows (e.g., checking whether a "Delivered" package was actually received, verifying with the customer, and then initiating a carrier investigation).
4. **Adaptive Tone** — They cannot dynamically adjust communication style based on operator feedback or customer sentiment.

The **AI-OPS Support Agent** addresses each of these gaps with a LangGraph-based agentic architecture backed by a semantic knowledge base (RAG), real-time tool calling, multi-scope memory, and dynamic prompt engineering.

---

## 2. Target Users & Roles

| Role | Description | Primary Workflow | Pain Points |
|:-----|:-----------|:----------------|:------------|
| **End Customer** | Online shopper who placed an order through UBA Logistics / AI-OPS STORE. | Asks "Where is my package?", checks return eligibility, requests escalation. | Long wait times; generic chatbot responses; having to repeat order IDs. |
| **Tier-1 Support Operator** | Frontline agent who monitors the Streamlit dashboard and adjusts the AI agent's behavior via style feedback. | Submits tone-adaptation feedback (e.g., "Be more empathetic"); reviews conversation logs; clears session memory. | Manual copy-pasting of order statuses; inconsistent tone across shifts. |
| **Operations / QA Manager** | Oversees service quality, audits conversation logs, and tunes safety policies. | Reviews audit logs at `/admin/feedback/audit`; resets memory scopes via `/admin/memory/reset`; checks metrics at `/metrics`. | Lack of observability; inability to wipe stale session data; no PII-safe logging. |

---

## 3. Business Context & End-to-End Workflow

The AI-OPS agent is embedded into the post-purchase support lifecycle of a logistics company:

```
Order Placed ──► Shipment Created ──► In Transit ──► Delivered ──► Post-Delivery Support
                                        │                │                │
                                        ▼                ▼                ▼
                                  "Where is my       "It says          "I never received
                                   package?"          Delivered"         my package!"
                                        │                │                │
                                        ▼                ▼                ▼
                               Agent calls          Agent calls        Agent calls
                              get_order_status     get_order_status   get_order_status
                                        │                │           + escalation flow
                                        ▼                ▼                │
                                  Status returned   Status confirmed     ▼
                                  to customer       + policy lookup   Carrier investigation
                                                    via KB search     ticket raised
```

### Supported Intents

| Intent | Trigger Examples | Agent Action |
|:-------|:----------------|:-------------|
| Order Status | "Where is order 456?", "Track my package" | `get_order_status(order_id)` |
| Policy / FAQ | "What is your return policy?", "Can I get a refund?" | `search_knowledge_base(query)` |
| Escalation | "Escalate this", "I want to speak to a manager" | Check status → provide escalation guidance |
| Non-Receipt | "I didn't receive my order", "Package missing" | Check status → verify delivery → initiate investigation |
| General Chat | "Hello", "Thanks" | Direct conversational response |

---

## 4. System Inputs, Outputs & Constraints

### Inputs

| Input | Source | Format |
|:------|:-------|:-------|
| User query (natural language) | Streamlit chat UI | Free-text string |
| Order ID | Extracted from query via regex | Numeric string, 3–10 digits |
| Knowledge base documents | `data/kb.txt` (static file) | Plain text, chunked at 600 chars / 100 overlap |
| Style feedback | Tier-1 operator via Streamlit sidebar | Free-text string (PII-sanitized before storage) |
| Thread ID | Session management | String identifier per conversation |

### Outputs

| Output | Destination | Format |
|:-------|:-----------|:-------|
| Conversational response | Streamlit chat UI | Natural language text |
| Order status | Embedded in response | Status string from Orders API |
| KB-sourced policy answer | Embedded in response | Summarized text from retrieved chunks |
| Escalation ticket reference | Embedded in response | Generated ticket ID (format: `UBA-<order_id>`) |
| Audit log entry | `data/audit/feedback_audit.log` | JSON Lines (JSONL) |

### Constraints

| Constraint | Value | Rationale |
|:-----------|:------|:----------|
| API response latency | < 2 seconds (target) | Customer experience SLA |
| Agent recursion limit | 10 steps | Prevents infinite tool-calling loops and token drain |
| Order ID max length | 10 digits | Prevents injection / abuse |
| PII redaction | Emails and phone numbers | GDPR / privacy compliance |
| Feedback text cap | 400 characters | Prevents prompt injection via oversized feedback |
| Embedding model | Google Gemini (`models/embedding-001`) | Environment constraint |
| LLM model | GPT-series via OpenAI-compatible proxy | Environment constraint |

---

## 5. Assumptions

1. **Order IDs are numeric and ≤ 10 digits.** Non-numeric or overly long IDs are rejected at the tool level.
2. **The knowledge base is pre-loaded from a static text file** (`data/kb.txt`) and embedded at startup. It is not updated at runtime.
3. **Google Gemini embedding service is available** at startup for vector store initialization. If unavailable, the RAG pipeline retries up to 3 times with a 2-second backoff.
4. **The Orders API is a separate microservice** running on a configurable port (default 8081). The agent communicates with it via HTTP.
5. **Conversations are single-user, single-thread.** Each Streamlit session maps to one LangGraph thread for memory isolation.
6. **Feedback is cumulative and global.** Style feedback submitted by operators applies to all subsequent responses until explicitly cleared.
7. **The agent operates in English only.** Multi-language support is out of scope.

---

## 6. Success Criteria

| Metric | Target | Measurement Method |
|:-------|:-------|:------------------|
| **Tool Adherence Rate** | ≥ 95 % | Fraction of policy/status queries that trigger the correct tool call |
| **KB Retrieval Precision** | ≥ 90 % | Manual review of top-k chunks returned for sample queries |
| **Escalation Flow Completion** | 100 % | All escalation intents reach a ticket reference or clear next-step guidance |
| **Tone Adaptation** | Verified | After submitting feedback, subsequent responses reflect the requested style |
| **PII Redaction** | 100 % | No raw emails or phone numbers stored in feedback or audit logs |
| **Loop Protection** | 0 infinite loops | Agent stops retrying after first tool failure; never hits recursion limit under normal operation |
| **Latency** | < 3 seconds p95 | Measured via Prometheus `request_duration_seconds` histogram |

---

## 7. Failure Cases & Mitigations

| # | Failure Scenario | Root Cause | Mitigation |
|:-:|:-----------------|:-----------|:-----------|
| 1 | **Orders API is down** | Network failure or service crash | Tool returns a descriptive error string; dynamic prompt detects `ToolMessage` error and injects `CRITICAL` stop directive — agent responds directly without retrying. |
| 2 | **Knowledge base is empty or corrupt** | Chroma collection deleted or embedding failure | `setup_rag()` detects an empty collection via test search, deletes the corrupt store, and rebuilds from source. If all retries fail, `self.retriever` is `None` and the tool returns "Knowledge base is unavailable." |
| 3 | **Invalid / missing order ID** | User provides no ID or a malformed one | Agent prompt instructs: "If no order ID is available, ask for it clearly." Tool-level validation rejects IDs > 10 digits. |
| 4 | **Gemini embedding batch proxy bug** | Proxy returns only 1 embedding for N inputs | `SafeGoogleGenerativeAIEmbeddings` wrapper overrides `embed_documents()` to call `embed_query()` sequentially, bypassing the batch endpoint. |
| 5 | **Infinite tool-calling loop** | Agent repeatedly calls the same failing tool | Dynamic prompt scans recent `ToolMessage` history for error keywords. After 1 failure: "Do NOT retry." After 2+: "STRICTLY FORBIDDEN from calling ANY tools." Recursion limit (10) serves as a hard backstop. |
| 6 | **Chroma collection name validation** | Collection name `"kb"` rejected (min 3 chars) | Renamed to `"knowledge_base"` (≥ 3 characters). |
| 7 | **Prompt injection via feedback** | Malicious operator submits adversarial feedback | Feedback is capped at 400 characters, PII is redacted, and the feedback block is clearly delineated in the prompt with role separation. |
| 8 | **Recursion limit reached** | Complex multi-tool queries exhaust 10 steps | Agent catches the `GraphRecursionError`, logs it, and returns a graceful apology message. |

---

## 8. Safety & Governance

### PII Protection
- **Regex-based redaction** in `FeedbackManager.add_feedback()`: emails (`[redacted_email]`) and phone numbers (`[redacted_phone]`) are stripped before storage.
- **No PII in logs**: audit entries record sanitized feedback text, timestamps, and counts — never raw user data.

### Audit Trail
- Every feedback submission is logged to `data/audit/feedback_audit.log` in JSON Lines format with `timestamp`, `added_feedback`, `before_count`, and `after_count`.
- Audit logs are auto-rotated: entries older than 90 days are pruned by `_rotate_audit_logs()`.
- The `/admin/feedback/audit` endpoint exposes audit data with `since`, `until`, and `limit` query parameters.

### Recursion & Loop Guards
- LangGraph `recursion_limit=10` prevents runaway tool loops.
- Dynamic prompt error injection detects `ToolMessage` failures and stops further tool calls at the prompt level — before the recursion limit is reached.

### Memory Administration
- `/admin/memory/reset` allows operators to clear session, user, or repository-level memory scopes.
- `/admin/memory/list` provides a count of stored memory artifacts per scope for observability.
- `MemorySaver` provides in-memory thread persistence with `delete_thread()` for targeted cleanup.

### Bearer Token Authentication
- The Orders API supports optional `ORDER_API_BEARER_TOKEN` environment variable for endpoint authentication.
- Missing or invalid tokens return `401 Unauthorized`.
