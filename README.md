# UBA Logistics AI-OPS Agent

A deployable AI support portal for logistics operations, featuring RAG-grounded policy retrieval, real-time order status tooling, feedback-driven tone adaptation, and optional observability.

## 🚀 Quickstart

### 1. Environment Setup
Copy `.env.example` to `.env` and update the runtime values.
```env
OPENAI_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here
ORDER_STATUS_API_URL=http://localhost:8081/orders/{order_id}
ORDER_API_BEARER_TOKEN=demo_token_123
ORDER_API_PORT=8081
ORDER_STATUS_TIMEOUT=8
OPENAI_BASE_URL=https://openai.vocareum.com/v1
LLM_MODEL=gpt-5.2
LLM_TEMPERATURE=0
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Start the Orders API Backend
The orders service uses SQLite for persistence and can migrate existing `data/orders.json` into `data/orders.db`.
```bash
ORDER_API_PORT=8081 python src/orders_api.py
```
If port `8081` is already in use, override with a different value:
```bash
ORDER_API_PORT=8091 python src/orders_api.py
```

### 4. Start the Streamlit Dashboard
```bash
streamlit run src/app.py
```
Open the app in your browser at `http://localhost:8501`.

---

## 📂 Project Structure
- `src/app.py` - Primary Streamlit dashboard UI, login flow, agent chat pane, and order analytics.
- `src/api.py` - Alternate Streamlit UI variant with a different branding layout.
- `src/agent.py` - CLI wrapper that runs `SupportAgent` in a local console loop.
- `src/support_agent.py` - Core agent logic, intent routing, tool binding, LangGraph agent executor, and fallback safety.
- `src/tools.py` - Tool implementations, including `get_order_status`.
- `src/rag.py` - Knowledge base ingestion, chunking, embedding, and Chroma retriever setup.
- `src/order_store.py` - SQLite schema and CRUD helpers for order persistence.
- `src/orders_api.py` - FastAPI backend exposing order status and update endpoints.
- `src/feedback.py` - Persistent feedback manager for tone and persona adjustment.
- `src/monitoring.py` - Prometheus-compatible metrics fallback and ASGI middleware.
- `src/tracing.py` - OpenTelemetry initialization and exporter support.
- `src/logging_config.py` - Structured JSON logging setup with rotation.
- `config.yaml` - Deployable configuration for RAG, tools, logging, and security.
- `data/kb.txt` - Knowledge base source for policy, shipping, refund, and escalation guidance.
- `data/orders.json` - Seed order data used for SQLite migration.
- `data/feedback.json` - Persisted user feedback and style preferences.
- `.env.example` - Example runtime environment variables.

## 🧠 Current Architecture
The app is deliberately split into three layers:

1. **User Interface**
   - `src/app.py` is the current Streamlit frontend.
   - It supports login, dashboard analytics, chat history, memory reset, and feedback submission.
   - `src/api.py` is a legacy alternate UI that can be used if needed.

2. **Agent Logic**
   - `src/support_agent.py` contains the actual support agent logic.
   - It uses `ChatOpenAI` plus `LangGraph` to bind tools and decide between direct answers and tool calls.
   - Intent routing is performed before the agent executor to improve reliability and reduce unnecessary loops.

3. **Data & Tools**
   - `src/orders_api.py` provides the order tracking backend.
   - `src/order_store.py` is the SQLite-backed persistent store used by the backend.
   - `src/rag.py` builds a semantic retriever over `data/kb.txt` using Chroma and Gemini embeddings.
   - `src/feedback.py` stores feedback in `data/feedback.json` and injects it into prompts.

---

## 🔧 Key Capabilities

### Retrieval-Augmented Generation (RAG)
- The knowledge base is loaded from `data/kb.txt`.
- Content is split with `RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=50)`.
- Embeddings are generated with `GoogleGenerativeAIEmbeddings(model=config.rag.embeddings_model)`.
- Chroma stores the vectors persistently under `data/chroma_store`.
- `SupportAgent` uses the retriever via `self.retriever.invoke(query)`.

### Tooling & Guardrails
- `get_order_status` is a tool in `src/tools.py` that safely calls the backend API.
- The agent only calls it for order status or escalation flows.
- Inputs are sanitized, and order IDs longer than 10 digits are rejected.
- The dynamic prompt enforces tool usage rules and prevents hallucinated status or policy answers.

### Memory & Feedback
- Short-term state is thread-scoped via `self._thread_order_ids`.
- Feedback is persisted in `data/feedback.json`.
- Feedback text is injected into the system prompt so the agent adapts tone and behavior.
- The UI supports clearing chat memory by generating a new `thread_id`.

### Backend Persistence
- `src/orders_api.py` starts a FastAPI service with SQLite-backed order storage.
- Existing `data/orders.json` is migrated to `data/orders.db` on startup.
- The backend also keeps a human-readable JSON export for compatibility.

### Observability
- `src/monitoring.py` provides in-memory metrics and optional Prometheus instrumentation.
- `src/tracing.py` initializes OpenTelemetry with console fallback and OTLP/Jaeger support if configured.
- `src/logging_config.py` configures structured JSON logging with rotation.

---

## 🛠️ Deployment Notes
- The Dockerfile installs dependencies and runs `src.agent` by default.
- For a production dashboard deployment, update the Docker `CMD` to run Streamlit or use `src/app.py` directly.
- Use `ORDER_API_PORT` to avoid port conflicts on the backend.
- The app is designed to be deployable in environments where `OPENAI_API_KEY` and `GOOGLE_API_KEY` are provided.

## ❗ Notes
- Always run the UI with `streamlit run src/app.py` for the current implementation.
- `src/agent.py` is the CLI fallback interface, not the main web app.
- `src/api.py` exists as an alternate Streamlit layout and is not the primary frontend.
- If you encounter `EADDRINUSE` on port `8081`, start the backend on another port with `ORDER_API_PORT=8091`.

## 📌 Example commands
```bash
pip install -r requirements.txt
ORDER_API_PORT=8081 python src/orders_api.py
streamlit run src/app.py
```

## ✅ Validation
- `python -m py_compile src/app.py src/orders_api.py src/support_agent.py src/rag.py src/order_store.py` should pass.
- Streamlit dashboard starts at `http://localhost:8501`.
- Orders API starts at `http://localhost:8081` unless overridden.
