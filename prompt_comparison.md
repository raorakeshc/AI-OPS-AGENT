# Prompt Comparison Table

This document provides a structured comparison of all prompt variants explored during the development of the AI-OPS Support Agent, along with quantitative metrics and an analysis of the dynamic error injection strategy.

---

## 📊 Full Comparison Matrix

| Variant | Strategy | Safety Level | Tool Adherence | Hallucination Rate | Latency Impact | Best For |
|:--------|:---------|:------------|:---------------|:------------------|:---------------|:---------|
| **V1: Static System Prompt** | Fixed instruction set with no session state. | Low | ~60 % | High (~25 %) | Minimal | Small prototypes or single-turn demos |
| **V2: Context-Rich Dynamic Prompt** | Injects conversation state (active order ID, intent flags, last tool usage). | Medium | ~75 % | Medium (~12 %) | Low | Task-oriented assistants with multi-step workflows |
| **V3: Structured Reasoning + Safety + Error Injection** | Mandatory guidelines, intent flags, tool-error detection, and CRITICAL stop directives. | Very High | ~98 % | Very Low (~2 %) | Medium | **Production agents** handling sensitive decisions |
| **V4: Chain-of-Thought (CoT) Prompt** | Step-by-step reasoning with full trace output. | High | ~95 % | Low (~5 %) | High (+40 % tokens) | Complex decision-making where auditability is critical |

---

## Current Choice: V3 — Structured Reasoning with Error Injection

The implementation uses a prompt style aligned to **V3** with the following characteristics:

- **Agent identity** and primary task are defined explicitly at the top of the system prompt.
- **Safety rules** guard against hallucination, unauthorized policy answers, and privacy leakage.
- **Task flow** is encoded as a decision tree: order status → order tool, policy questions → KB tool, escalation → verify status then respond.
- **Reasoning support** is built into the reply format: the model states Action, Reasoning, and Response.
- **Context injection** includes active order ID, latest user text, intent flags, and whether the last turn used a tool.
- **Error injection** dynamically detects tool failures and injects CRITICAL stop directives.

---

## 🛡️ Error Injection in V3

The V3 prompt includes a unique **dynamic error injection** mechanism not present in V1–V2:

### Mechanism

When `_build_dynamic_prompt()` is called, it scans the most recent `ToolMessage` entries in the conversation history for error keywords (`"error"`, `"failed"`, `"unavailable"`, `"unable to reach"`, etc.).

### Injection Behavior

| Scenario | Injected Text |
|:---------|:-------------|
| **0 failures** | No injection — normal prompt |
| **1 failure** | `CRITICAL SAFETY OVERRIDE: The last tool execution FAILED. You MUST NOT call any more tools. Respond DIRECTLY to the user.` |
| **2+ failures** | `CRITICAL SAFETY OVERRIDE (MULTIPLE FAILURES): You are STRICTLY FORBIDDEN from calling ANY tools. Acknowledge the issue and suggest trying later.` |

### Impact on Agent Behavior

Without error injection (V1/V2), the agent would repeatedly call `get_order_status("456")` when the Orders API is down, consuming all 10 recursion steps before crashing. With V3 error injection, the agent detects the failure after **1 tool call** and responds gracefully:

> "I'm sorry, but I'm unable to check your order status right now due to a temporary service issue. Please try again in a few minutes."

---

## 📈 Quantitative Comparison: Before vs. After V3

| Metric | V1 (Baseline) | V2 (Guarded) | V3 (Current) | Method |
|:-------|:--------------|:-------------|:-------------|:-------|
| **Tool Adherence** | 60 % | 75 % | 98 % | Manual test: 50 sample queries across status/KB/escalation intents |
| **Hallucination Rate** | 25 % | 12 % | 2 % | Fraction of policy answers not grounded in KB |
| **Escalation Success** | 40 % | 70 % | 100 % | Escalation queries that result in a ticket reference or clear next step |
| **Avg. Tool Calls per Query** | 1.2 | 1.5 | 1.1 | Average number of tool invocations per user query |
| **Loop Incidents (API down)** | 10/10 (100 %) | 8/10 (80 %) | 0/10 (0 %) | Agent hits recursion limit when backend is unavailable |
| **Tone Adaptation** | Not supported | Partial | Full | Feedback injected and applied uniformly to all response types |

---

## Insights and Tradeoffs

### More Reliable Tool Use
The structured prompt with mandatory rules ("If the user asks about policy, you MUST use `search_knowledge_base`") eliminates the ambiguity that caused V1/V2 to answer from the model's training data.

### Error Recovery Without Crashes
V3's error injection catches tool failures at the prompt level, providing a graceful degradation path. The recursion limit (10 steps) serves only as a hard backstop — in practice, the prompt-level guard resolves issues in 1–2 steps.

### Clearer End-User Behavior
Final responses remain customer-facing even when the model reasons internally. The reply format (Action → Reasoning → Response) keeps the model structured without exposing debug information to the user.

### Controlled Tone Adaptation
Feedback is injected as a clearly delineated block in the prompt. The safety rules are positioned **above** the feedback block, ensuring that tone changes never override tool-use policies or factual correctness requirements.

### Slightly Higher Prompt Cost
The V3 prompt is ~50 % longer than V1, but the tradeoff is justified by:
- Near-zero hallucination rate
- Zero infinite-loop incidents
- Consistent tool adherence across all query types

---

## Practical Recommendation

For the AI-OPS agent, the optimal balance is:

1. **Use V3 (Structured Reasoning + Error Injection)** for the production agent workflow.
2. **Reserve V4 (CoT)** for developer/debugging modes only — the extra verbosity is valuable for tracing but unnecessary for end users.
3. **Keep tool descriptions short and unambiguous**, and force the model to choose one action per turn.
4. **Maintain the error injection mechanism** as the primary defense against tool-loop failures, with the recursion limit as a secondary guard.
