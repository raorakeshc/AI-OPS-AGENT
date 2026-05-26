# Prompt Analysis & Evolution

The Support Agent's dynamic prompt has evolved through four iterative variants, each addressing specific failure modes discovered during development and testing.

---

## 📊 Detailed Comparison Table

| Variant | Strategy | Safety Level | Tool Adherence | Latency | Best For |
|:--------|:---------|:------------|:---------------|:--------|:---------|
| **V1: Baseline** | Vague instructions: "Be a helpful agent." | Low | ~60 % — often answered from memory | Low | Quick prototypes |
| **V2: Guarded** | Complex "Critical Stop Guards" and intent checks | High | ~80 % — too defensive, asked for clarification instead of using tools | Medium | Safety-first demos |
| **V3: Authoritative (Current)** | Mandatory guidelines + Intent Flags + Error Injection | Very High | ~98 % — tools called when required, errors handled gracefully | Medium | **Production agents** |
| **V4: Chain-of-Thought** | Step-by-step reasoning with full trace | Very High | ~95 % — good but verbose | High | Debugging / auditability |

---

## 🔄 Prompt Variant Examples

### V1: Baseline Prompt
```
You are a helpful customer support agent. Answer the user's questions.
```
**Failure**: Asked "What is your return policy?", the model answered from training data instead of calling the knowledge base tool. Hallucinated a 30-day return window that didn't match the actual policy.

### V2: Guarded Prompt
```
CRITICAL: Before answering ANY question, check if it requires a tool.
If unsure, ask the user for clarification.
Never answer policy questions without checking the knowledge base.
```
**Failure**: User asked "Can I return a damaged item?" — agent responded with "Could you clarify what type of item?" instead of searching the KB. Overly cautious.

### V3: Authoritative Prompt (Current)
```
SAFETY & TASK GUIDELINES:
1. If the user asks about policy/returns/shipping, use `search_knowledge_base`.
2. If the user asks about order status and an order ID is available, use `get_order_status`.
3. Never answer policy or status questions from your own memory.

CURRENT CONTEXT:
- Active Order ID: 456
- User intent likely requires KB search: True
- Last message was a tool response: False
```
**Result**: 98 % tool adherence. Model follows the mandatory rules and uses context flags to select the correct tool.

### V4: Chain-of-Thought
```
Think step by step:
1. What is the user asking?
2. Does this require a tool? Which one?
3. What is the tool result?
4. Formulate a customer-facing answer.
Show your reasoning.
```
**Tradeoff**: Excellent for debugging but adds ~40 % more output tokens. Not suitable for production customer support.

---

## 🛡️ Dynamic Error Injection Strategy

The `_build_dynamic_prompt()` method implements **real-time loop protection** by scanning the conversation's `ToolMessage` history for error indicators:

### How It Works

1. The prompt builder iterates backward through messages, starting from the most recent.
2. For each `ToolMessage`, it checks the content for error keywords:
   - `"error"`, `"failed"`, `"unavailable"`, `"not configured"`
   - `"unable to reach"`, `"service returned an error"`, `"lookup failed"`
3. It counts **consecutive** tool failures (stopping at the first success or the last `HumanMessage`).

### Injection Levels

| Consecutive Failures | Injected Directive |
|:---------------------|:------------------|
| 1 | `CRITICAL SAFETY OVERRIDE: The last tool execution FAILED. You MUST NOT call any more tools. Respond DIRECTLY to the user explaining the issue.` |
| 2+ | `CRITICAL SAFETY OVERRIDE (MULTIPLE FAILURES): Multiple consecutive tool calls have FAILED. You are STRICTLY FORBIDDEN from calling ANY tools.` |

### Why This Works

- The directive is injected **into the system prompt itself**, not as a separate message. The LLM treats system-level CRITICAL directives with the highest priority.
- This catches failures **before** the recursion limit (10 steps) is hit, providing a graceful user-facing response instead of a hard crash.
- The `recursion_limit=10` in LangGraph serves as a hard backstop if the prompt-level guard somehow fails.

```python
# Simplified loop detection logic
for msg in reversed(messages):
    if is_tool_message(msg):
        if has_error_keywords(msg.content):
            consecutive_tool_failures += 1
        else:
            break  # Stop at first successful tool result
    elif isinstance(msg, HumanMessage):
        break  # Stop looking past the latest user message
```

---

## 🔒 Safety Guards in the Prompt

The V3 prompt enforces multiple layers of safety:

| Guard | Mechanism | Prevents |
|:------|:----------|:---------|
| **Mandatory tool use** | "Never answer policy or status questions from your own memory" | Hallucinated policies / statuses |
| **Tool error refusal** | Dynamic CRITICAL override injected on ToolMessage errors | Infinite tool-calling loops |
| **Order ID validation** | "If the user has not provided an order ID, ask for it" | Tool calls with missing arguments |
| **Single-action rule** | "Do not mix tools in the same response" | Confused multi-tool behavior |
| **PII protection** | Feedback is sanitized before injection into prompt | Prompt injection via PII |
| **Recursion backstop** | `recursion_limit=10` in LangGraph config | Runaway token consumption |

---

## 🎨 Tone Adaptation Mechanism

The agent supports **dynamic tone adaptation** through the `FeedbackManager`:

1. **Operator submits feedback** via the Streamlit sidebar (e.g., "Always respond formally" or "Use emoji in responses").
2. **Feedback is sanitized**: emails and phone numbers are redacted, text is capped at 400 chars.
3. **Feedback is persisted** to `data/feedback.json` as a cumulative list.
4. **At prompt-build time**, `get_feedback_string()` injects all feedback entries into the prompt:

```
CRITICAL USER FEEDBACK (ADJUST YOUR TONE/STYLE TO FOLLOW THESE RULES, BUT CONTINUE TO USE YOUR TOOLS NORMALLY):
- Always respond formally
- Use empathetic language for complaints
```

5. The prompt header states: "Use the feedback block to adapt tone, but always remain professional and helpful." This ensures tone changes never override safety rules or tool-use policies.

---

## 🧩 Context Injection Architecture

The dynamic prompt injects five real-time context signals:

| Signal | Source | Purpose |
|:-------|:-------|:--------|
| `Active Order ID` | Regex extraction from current + history messages | Tells the LLM which order to query without re-asking |
| `Latest user text` | Last `HumanMessage` in state | Provides raw query for intent analysis |
| `KB search flag` | Regex match on policy/FAQ keywords | Hints the LLM to prefer `search_knowledge_base` |
| `Status lookup flag` | Regex match on tracking/status keywords | Hints the LLM to prefer `get_order_status` |
| `Escalation / Non-receipt flags` | Regex match on escalation/missing keywords | Signals multi-step flow (check status → escalate) |
| `Last message was tool response` | Type check on last message | Tells the LLM whether to summarize a tool result or make a new call |

These signals are **advisory, not prescriptive** — the LLM still makes the final tool-selection decision through the LangGraph ReAct executor. The signals reduce ambiguity and improve first-pass accuracy.

---

## 💡 Key Insights

- **Force, don't ask**: In production logistics, the model should be forced to use the KB for policies. Prompting "If flag is True, you MUST call tool" proved 5× more effective than "Search if needed."
- **Error injection > recursion limits**: Prompt-level error guards catch failures in 1–2 steps. The recursion limit (10 steps) is a backstop, not the primary defense.
- **Context isolation matters**: By routing all intents through the agent executor (no regex bypasses), the LLM applies feedback and safety rules uniformly to every response type.
- **Feedback is tone-only**: The feedback injection block is clearly separated from safety rules, preventing operator feedback from overriding tool-use policies.
