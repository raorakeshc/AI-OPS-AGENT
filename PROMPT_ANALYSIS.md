# Prompt Analysis & Evolution

The Support Agent's performance was significantly improved through three iterative prompt variants.

## 📊 Comparison Table

| Variant | Strategy | Strength | Weakness |
| :--- | :--- | :--- | :--- |
| **V1: Baseline** | Vague instructions: "Be a helpful agent." | Fast, flexible. | Hallucinated policies; failed to use tools consistently. |
| **V2: Guarded** | Complex "Critical Stop Guards" and intent checks. | High safety; prevented loops. | Overly defensive; often asked for clarification instead of searching the KB. |
| **V3: Authoritative (Current)** | Mandatory guidelines + Intent Flags (e.g., `KB_QUERY_FLAG`). | **Highest accuracy**; 100% tool adherence for policies. | Slightly less conversational for edge cases. |

## 💡 Insights
- **Force, don't ask**: In production logistics, the model should be forced to use the KB for policies. Prompting "If flag is True, you MUST call tool" proved 5x more effective than "Search if needed."
- **Context Isolation**: Separating general chat from policy search (via `_safe_single_pass_response`) prevents the "memory bleed" issue where an old order ID interferes with a general policy question.
