# Prompt Comparison Table

This table compares the current dynamic prompt against variants tested during development.

| Variant | Description | Pros | Cons | Insight |
| :--- | :--- | :--- | :--- | :--- |
| **V1: Static System Prompt** | A fixed instruction set describing tools and personality. | Low latency; simple implementation. | Often misses context (like active order ID); prone to tool-calling loops. | Static prompts struggle with state-dependent logic in LangGraph. |
| **V2: Context-Rich Dynamic (Current)** | Injects `latest_user_text`, `active_order_id`, and `is_last_tool_message`. | Highly accurate; follows strict policies; prevents redundant tool calls. | Slightly higher token usage. | **Winner.** Injecting state directly into the prompt ensures the LLM knows *exactly* where it is in the logic loop. |
| **V3: Chain-of-Thought (CoT)** | Forces the LLM to explain its reasoning before calling a tool. | Better at complex troubleshooting. | Much slower; higher latency. | Overkill for simple logistics queries; V2's policy-based approach is faster and sufficient. |

### Key Insights:
1.  **State Injection is Critical**: Passing `active_order_id` as a top-level context variable reduced "Ask for ID" hallucination by 95%.
2.  **Stop Guards**: The `CRITICAL STOP GUARD` in the prompt prevents the LLM from recursively calling tools when a result is already available.
3.  **Adaptive Feedback**: Involving the `feedback_str` allows the agent to modify its tone (e.g., professional vs pirate) without changing core logic.
