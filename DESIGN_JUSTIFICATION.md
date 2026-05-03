# Engineering & Product Justification

## 1. Design Decisions

### Why LangGraph?
We chose **LangGraph** over simple chains because support workflows are non-linear. The ability to use `MemorySaver` for state persistence and `checkpoints` for error recovery is critical for "long-lived" support threads where users might leave and return.

### Why ChromaDB?
ChromaDB provides an lightweight, efficient local vector store that perfectly suits our structured policy Knowledge Base (`kb.txt`). Its integration with `RecursiveCharacterTextSplitter` allows for semantic retrieval that outperforms keyword-based search for "Policy Eligibility" queries.

## 2. Tradeoffs & Optimization

### Latency vs. Precision
- **Tradeoff**: Larger RAG chunks improve context but increase LLM synthesis time.
- **Decision**: We standardized on **600-character chunks**. This ensures an entire "Return Window" or "Shipping Fee" section is retrieved in one pass, avoiding the "fragmented policy" failure common in smaller chunk settings.

### Guarded Prompting vs. Intelligence
- **Tradeoff**: Strict prompts (MUST use tool) reduce the "naturalness" of the chat.
- **Decision**: For AI-OPS, **accuracy is higher priority than personality**. We sacrificed some conversational flair to ensure the agent never provides incorrect shipping timelines from its training data.

## 3. Safety & Deployment

### Safety Approach
1.  **Recursion Guard**: Forced 10-step limit on the ReAct loop.
2.  **Input Sanitization**: Regex extraction prevents SQL-injection-style attacks on the mock Orders API.
3.  **PII Privacy**: The current demo uses generic order IDs (3-10 digits) to avoid handling sensitive customer names in the RAG loop.

### Deployment Assumptions
- **Host**: Streamlit Cloud or AWS EC2.
- **API Connectivity**: Assumes the Orders Service is reachable via internal VPC or secure endpoint.
- **Scalability**: The `Chroma` vectorstore is currently in-memory/local but can be swapped for `Pinecone` or `Weaviate` if the KB grows beyond 10,000 articles.
