# Demo Script: AI-OPS Agent Interactions

This document outlines five forced interactions to demonstrate the capabilities of the UBA Logistics Support Agent.

## 1. Authentication & Role-Based Access
**Scenario**: An admin logs in to see full operational metrics.
- **Action**: Login with `admin` / `admin123`.
- **Expected Result**: Sidebar displays both "Dashboard" and "Agent".
- **Evidence**:
![Dashboard Mockup](file:///C:/Users/raora/.gemini/antigravity/brain/a092107b-d6eb-4f75-88e1-e9a633a1eea5/dashboard_mockup_1777639220177.png)

## 2. Order Status Retrieval (Direct ID)
**Scenario**: User provides an order ID and asks for its status.
- **Interaction**:
    - **User**: "Where is order 101?"
    - **Agent**: "Order 101 status: Out for Delivery"
- **Internal Logic**: The agent extracts `101`, saves it to thread memory, and calls `get_order_status`.
- **Logs**:
```text
INFO:root:Extracted order_id: 101
INFO:root:Calling get_order_status(order_id='101')
INFO:root:Tool result: Out for Delivery
```

## 3. Contextual Recall (Memory)
**Scenario**: User asks for their order ID without re-specifying it.
- **Interaction**:
    - **User**: "What is my order number?"
    - **Agent**: "Your current order id or order number is 101."
- **Internal Logic**: The agent uses the updated `_order_id_recall_pattern` to fetch the ID from `self._thread_order_ids`.

## 4. Policy Inquiry (RAG)
**Scenario**: User asks about the refund policy.
- **Interaction**:
    - **User**: "What is your refund policy?"
    - **Agent**: "Based on our knowledge base, refunds are processed within 5-7 business days for non-delivered items..."
- **Internal Logic**: Agent detects a KB query, calls `search_knowledge_base`, and synthesizes an answer.

## 5. Escalation for Non-Receipt
**Scenario**: User complains about a delivered item they haven't received.
- **Interaction**:
    - **User**: "My order 101 says delivered but I don't have it. Escalate this!"
    - **Agent**: "Yes — I can escalate this for Order 101. Since it is marked Delivered but not received, I will open a carrier investigation immediately. Priority SLA: initial response within 6 hours."
- **Evidence**:
![Agent Chat Mockup](file:///C:/Users/raora/.gemini/antigravity/brain/a092107b-d6eb-4f75-88e1-e9a633a1eea5/agent_chat_mockup_1777639241410.png)
