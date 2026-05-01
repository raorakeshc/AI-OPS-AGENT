# Engineering & Product Justification

## 1. Design Decisions
- **LangGraph for Orchestration**: We chose LangGraph over simple LangChain Agents to have granular control over the tool-calling loop. This allows for state management (thread memory) and complex "Stop Guards" that prevent infinite loops.
- **Streamlit for UI**: Provides a rapid, pythonic way to build a high-fidelity dashboard. Its `session_state` integrates perfectly with our backend memory management.
- **RAG for KB**: Using a vector store (Chroma) for policies allows the agent to stay up-to-date with company documents without retraining the LLM.

## 2. Tradeoffs
- **Regex vs. LLM for Intent**: We use Regex for common patterns (ID extraction, recall) to save latency and token costs. While less "flexible" than LLM intent detection, it is 100% predictable and faster for core functions.
- **Local vs. Cloud Embeddings**: We used `gemini-embedding-2` for high-quality semantic search, accepting the external API dependency for significantly better retrieval performance compared to smaller local models.

## 3. Safety & Security
- **RBAC (Role-Based Access Control)**: Implemented hardcoded credential checks for the prototype to demonstrate page-level security (Admin vs User).
- **ID Validation**: The `get_order_status` tool includes a safeguard to reject any `order_id` longer than 10 characters, mitigating injection risks.
- **Recursion Limits**: Configured a `recursion_limit` of 10 in LangGraph to ensure the agent never gets stuck in a tool-calling cycle.

## 4. Deployment Assumptions
- **Environment Variables**: Assumes `.env` contains valid Google API keys and `ORDER_STATUS_API_URL`.
- **Concurrency**: Currently optimized for single-session use; production deployment would require scaling the `MemorySaver` to a persistent database like PostgreSQL.
