# UBA Logistics AI-OPS Agent

A production-grade AI support portal for logistics operations, featuring RAG-enabled policy retrieval, automated order status tracking, and multi-stage escalation workflows.

## 🚀 Run Instructions

### 1. Environment Setup
Create a `.env` file in the root directory with the following keys:
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
python src/orders_api.py
```
*Port: 8081*

### 4. Launch the AI-OPS Dashboard (Frontend)
Run the Streamlit application to access the glassy portal.
```bash
streamlit run src/app.py
```
*Default URL: http://localhost:8501*

---

## 📂 Source Overview
- `src/agent.py`: Core logic for the `SupportAgent` class, LangGraph executor, and RAG setup.
- `src/app.py`: Streamlit UI with custom CSS glassmorphism.
- `src/orders_api.py`: FastAPI-based mock service for order status.
- `src/rag.py`: Embedding pipeline, persistent Chroma store, and semantic KB retrieval.
- `data/kb.txt`: Semantic Knowledge Base for policies (RAG source).
- `data/orders.json`: Simulated database for order tracking.

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
