# Prompt Comparison Table

This table compares prompt patterns used in the agent and explains why the current workflow favors structured reasoning, safety, and task flow.

| Variant | Description | Pros | Cons | When to Use |
| :--- | :--- | :--- | :--- | :--- |
| **V1: Static System Prompt** | A fixed instruction set with no session state. | Simple and low overhead. | Lacks contextual state; can hallucinate or miss tool hooks. | Small prototypes or single-turn demos. |
| **V2: Context-Rich Dynamic Prompt** | Injects conversation state such as active order ID, intent flags, and last tool usage. | Better tool selection, fewer hallucinations, maintains session continuity. | More token usage; requires careful state extraction. | Task-oriented assistants with multi-step workflows. |
| **V3: Structured Reasoning + Safety Prompt** | Explicit action/reasoning/response format, strong tool-call policy, and safety rules. | Most reliable tool integration, clear decision logic, safer user-facing output. | Longer prompt and slightly more complexity. | Production agents handling sensitive decisions and policy enforcement. |
| **V4: Chain-of-Thought (CoT) Prompt** | Instructs the model to show reasoning step-by-step. | Improved transparency and debugging. | Highest latency and output verbosity. | Complex decision-making where auditability is critical, not general customer support. |

## Current Choice: Structured Reasoning with Context
The implementation now uses a prompt style aligned to **V3** with the following characteristics:

- **Agent identity** and primary task are defined explicitly.
- **Safety rules** guard against hallucination, unauthorized policy answers, and privacy leakage.
- **Task flow** is encoded as a decision tree: order status → order tool, policy questions → KB tool, escalation → verify status then respond.
- **Reasoning support** is built into the prompt format: the model is asked to state Action, Reasoning, and Response.
- **Context injection** includes active order ID, latest user text, and whether the last turn used a tool.

## Insights and Tradeoffs
- **More reliable tool use**: The structured prompt reduces the chance the model answers without tools when tools are required.
- **Clearer end-user behavior**: Final responses are intended to remain customer-facing even when the model reasons internally.
- **Controlled tone adaptation**: Feedback is still allowed, but it does not override safety or factual correctness.
- **Slightly higher prompt cost**: The prompt is longer, but the tradeoff is worth it for stability in the agent workflow.

## Practical recommendation
For this agent, the best balance is:
- Use a structured, context-rich prompt for the core agent workflow.
- Reserve CoT-style prompting for developer/debugging modes only.
- Keep tool descriptions short and unambiguous, and force the model to choose one action per turn.
