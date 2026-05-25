# UBA Logistics AI-OPS Agent

A production-grade AI support portal for logistics operations, featuring RAG-enabled policy retrieval, automated order status tracking, and multi-stage escalation workflows.

## 🚀 Run Instructions

### 1. Environment Setup
Create a `.env` file in the root directory with the following keys, or copy `.env.example` and update it:
```env
OPENAI_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here
ORDER_STATUS_API_URL=http://localhost:8081/orders/{order_id}
ORDER_API_BEARER_TOKEN=demo_token_123
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Start the Orders API (Backend)
The agent relies on a mock REST API for order tracking.
```bash
ORDER_API_PORT=8081 python src/orders_api.py
```
*Default port: 8081* (override with `ORDER_API_PORT` if the port is already in use)

### 4. Launch the AI-OPS Dashboard (Frontend)
Run the Streamlit application to access the glassy portal.
```bash
streamlit run src/app.py
```
*Default URL: http://localhost:8501*

---

## 📂 Source Overview
- `src/agent.py`: CLI wrapper and entrypoint for running the modular agent from the command line.
- `src/support_agent.py`: Actual agent logic, tool binding, LangGraph ReAct executor, intent routing, fallback handling, and dynamic prompt construction.
- `src/orders_api.py`: FastAPI-based mock service for order status.
- `src/rag.py`: RAG initialization pipeline, chunking, embeddings, Chroma vector store persistence, and semantic KB retrieval.
- `src/feedback.py`: Feedback persistence and prompt adaptation logic.
- `src/tools.py`: Tool definitions such as `get_order_status`.
- `src/app.py`: Streamlit dashboard UI and user interaction layer.
- `data/kb.txt`: Semantic Knowledge Base for policies, shipping rules, refunds, and escalation guidance.
- `data/orders.json`: Simulated order status data source.
- `data/feedback.json`: Persistent feedback and tone preferences used by the agent.

## 🏗️ Architecture & Reliability Patterns
This project is designed for stability and grounded answers through a mix of deterministic routing, semantic retrieval, and fallback safety.

- **RAG retrieval is built in `src/rag.py`.**
  * Loads `data/kb.txt` and splits it with `RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=50)`.
  * Uses `GoogleGenerativeAIEmbeddings(model=config.rag.embeddings_model)` to embed chunks.
  * Stores embeddings in Chroma and reloads the persisted store on startup.

- **Tools are bound in `src/support_agent.py`.**
  * `search_knowledge_base(query)` retrieves KB snippets via `self.retriever.invoke(query)`.
  * `get_order_status` is imported from `src/tools.py` and used for order tracking.
  * The agent binds these tools to the LLM with `self.llm.bind_tools(self.tools)`.

- **Intent routing and tool selection happen before the agent loop.**
  * Regex-based pre-routing handles status checks, KB queries, escalation, order-id recall, and non-receipt cases.
  * Simple status/KB requests often bypass the full ReAct flow for speed and reliability.

- **Prompt guardrails and feedback adaptation are enforced in `_build_dynamic_prompt()`.**
  * The prompt includes safety rules, tool usage instructions, and the active order ID context.
  * User feedback is injected as a critical tone-adaptation block via `FeedbackManager`.

- **Recursive and fallback safety are built into `ask()`.**
  * `recursion_limit=10` protects against runaway loops.
  * If the agent fails or returns an unsafe response, `_safe_single_pass_response()` provides a safe answer.
  * Tool errors are caught and returned as user-friendly explanations instead of crashing.

- **Short-term memory is thread-scoped.**
  * `self._thread_order_ids` tracks the active Order ID for each `thread_id`.
  * Feedback persistence lives in `data/feedback.json` and survives restarts.

- **UI and user flow.**
  * `src/app.py` provides a Streamlit dashboard for users to ask questions and submit feedback.
  * `src/agent.py` offers a command-line fallback interface with `clear` and `feedback:` commands.

## 🔍 Semantic Retrieval Pipeline
The agent uses a retrieval-augmented pipeline to ground customer answers in the KB instead of relying on model memory.

Pipeline steps:
1. Load `data/kb.txt`.
2. Split content into overlapping chunks using `RecursiveCharacterTextSplitter`.
3. Embed chunks with Google Gemini embeddings (`models/gemini-embedding-2`).
4. Persist a local Chroma vector store in `data/chroma_store`.
5. Reload the store on each startup to skip repeated embedding work.

### Why this improves responses
- Semantic retrieval finds the most relevant KB paragraphs for policy, returns, shipping, and refund questions.
- It reduces hallucinations by returning exact knowledge-base text instead of guessing.
- The persistent store makes repeated runs fast and efficient.

### Example retrieval relevance
- Query: `Can I return electronics after 20 days?`
  - Retrieved snippet: `Electronics: Return within 15 days of delivery.`
- Query: `What does Out for Delivery mean?`
  - Retrieved snippet: `Out for Delivery: Package is expected to be delivered today.`
- Query: `Can I cancel after my order is packed?`
  - Retrieved snippet: `If status is Packed/Shipped/In Transit, cancellation is not possible.`

These examples show how semantic retrieval surfaces concise KB facts and keeps answers grounded in documented policy.
