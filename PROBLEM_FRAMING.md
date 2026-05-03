# Problem Framing: AI-OPS Logistics Support Agent

## 1. Problem Statement
In modern logistics, customer support volume is dominated by repetitive queries: "Where is my package?" and "What is your return policy?". Traditional chatbots often fail because they lack:
1.  **Contextual Awareness**: They cannot distinguish between a general policy question and an order-specific issue.
2.  **Tool Integration**: They cannot securely and accurately query real-time APIs.
3.  **Complex Reasoning**: They struggle with multi-stage flows (e.g., escalating a "Delivered" package that was never received).

## 2. Objective
To build a **production-grade AI-OPS Support Agent** that:
- Automates 80%+ of Tier-1 support queries.
- Connects a Semantic Knowledge Base (RAG) to the LLM for accurate policy retrieval.
- Implements a tool-calling loop (LangGraph) for real-time order tracking.
- Features a premium, operationally efficient UI (Glassmorphism Dashboard).

## 3. Key Challenges & Solutions

### A. RAG Precision vs. Latency
- **Challenge**: Embedding large policy documents can be slow, and small chunk sizes often lose context.
- **Solution**: Implemented a `RecursiveCharacterTextSplitter` with 600-character chunks and 100-character overlap, optimized for Google Gemini embeddings.

### B. Reliable Tool Calling
- **Challenge**: LLMs sometimes hallucinate order IDs or fail to trigger tools when queries are conversational (e.g., "order142").
- **Solution**: Built an "intent-aware" pre-processing layer using Regex and Capture Groups to extract and sanitize IDs before they reach the LLM.

### C. State Management & Escalation
- **Challenge**: Maintaining state during a conversation (e.g., knowing that a user already verified their location).
- **Solution**: Utilized **LangGraph MemorySaver** to persist thread states and implemented a "State-Machine" style logic for escalation confirmation.

## 4. Safety & Product Justification
- **Safety**: Implemented recursion limits (10 steps) to prevent infinite tool-calling loops and token drain.
- **Justification**: By offloading Tier-1 queries, humans can focus on high-complexity exceptions, reducing operational costs by an estimated 30-40%.
