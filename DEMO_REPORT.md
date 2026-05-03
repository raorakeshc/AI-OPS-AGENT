# Demo Script & Interaction Evidence

## 🎭 Forced Interaction Script

| Step | User Query | Expected Agent Behavior |
| :--- | :--- | :--- |
| 1 | "can you check the status of order142" | Extract ID '142', call `get_order_status`, return "Delivered". |
| 2 | "what is the refund policy ?" | Trigger RAG tool `search_knowledge_base`, ignore order history, return tiered policy. |
| 3 | "can i escalate order 128?" | Detect 'Delivered' status, prompt user to check location/neighbors. |
| 4 | "yes i verified with everyone, but not recieved" | Detect confirmation + typo 'recieved', initiate formal investigation, provide ticket ID. |
| 5 | "what is my order id?" | Access `MemorySaver` to recall the last mentioned ID (128). |

## 📜 Log Evidence (Terminal/Agent Log Snippet)

```text
2026-05-01 22:44:03 - INFO - search_knowledge_base called with query: refund policy
2026-05-01 22:45:10 - INFO - get_order_status called for order142 -> cleaned to 142
2026-05-01 22:47:15 - INFO - Escalation initiated for Order 128. Verification detected.
```

## 📸 Dashboard Preview
The dashboard utilizes a **Citrine & Sky** Glassmorphism aesthetic:
- **Background**: Frosted glass with subtle 20px blur.
- **Metrics**: Interactive cards with shadow lifts on hover.
- **Chat**: High-contrast, typo-tolerant, and state-aware bubbles.
