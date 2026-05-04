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
- `data/kb.txt`: Semantic Knowledge Base for policies (RAG source).
- `data/orders.json`: Simulated database for order tracking.
