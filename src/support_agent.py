import os
import re
import time
import json
import logging
from urllib.parse import urlencode
from langchain_openai import ChatOpenAI
from langchain_core.messages import ToolMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.tools import tool
from dotenv import load_dotenv
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

try:
    from .feedback import FeedbackManager
    from .tools import get_order_status
    from .rag import setup_rag
except ImportError:
    from feedback import FeedbackManager
    from tools import get_order_status
    from rag import setup_rag


class SupportAgent:
    def __init__(self, openai_api_key: str | None = None):
        # Load environment variables from .env to support Streamlit importing this module
        load_dotenv()
        openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY not found. Check your .env file.")

        self.llm = ChatOpenAI(
            model=os.getenv("LLM_MODEL", "gpt-5.2"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0")),
            base_url=os.getenv("OPENAI_BASE_URL", "https://openai.vocareum.com/v1"),
            api_key=openai_api_key,
        )

        self.feedback_manager = FeedbackManager()
        self._thread_order_ids: dict[str, str] = {}

        # Intent / extraction patterns (used for CONTEXT INJECTION only, not bypasses)
        self._order_id_pattern = re.compile(r"(?:order|#)?\s*(\d{3,10})", re.IGNORECASE)
        self._status_intent_pattern = re.compile(r"\b(status|where|track(?:ing)?|check|update|location|eta|delivered|shipped)\b", re.IGNORECASE)
        self._kb_intent_pattern = re.compile(r"\b(policy|refund|return|shipping|faq|how|can\s+i|what|why|when)\b", re.IGNORECASE)
        self._escalation_intent_pattern = re.compile(r"\b(escalate|escalation|complaint|supervisor|manager|raise\s+(?:a\s+)?ticket)\b", re.IGNORECASE)
        self._non_receipt_pattern = re.compile(r"\b(not\s+rec[ie]{2}ved|didn['\u2019]?t\s+rec[ie]{2}ve|not\s+delivered|missing)\b", re.IGNORECASE)

        # RAG setup
        self.retriever = setup_rag()

        # Build a knowledge-base tool bound to this agent (needs access to self.retriever)
        @tool
        def search_knowledge_base(query: str) -> str:
            """Search the knowledge base for policy/FAQ entries and return concatenated results."""
            logging.info(f"search_knowledge_base tool called with query: {query}")
            if not getattr(self, "retriever", None):
                return "Knowledge base is unavailable."
            docs = self.retriever.invoke(query)
            return "\n\n".join(doc.page_content for doc in docs)

        self.tools = [get_order_status, search_knowledge_base]
        self.memory = MemorySaver()
        self.tools_map = {tool.name: tool for tool in self.tools}

        self.llm_with_tools = self.llm.bind_tools(self.tools)
        logging.info("SupportAgent initialized successfully.")

    # ------------------------------------------------------------------ #
    # Dynamic Prompt with Loop Protection & Context Injection
    # ------------------------------------------------------------------ #
    def _build_dynamic_prompt(self, state) -> str:
        messages = state.get("messages", [])
        feedback_str = self.feedback_manager.get_feedback_string()
        latest_user_text = self._latest_human_text(messages)
        active_order_id = state.get("active_order_id") or self._extract_active_order_id(messages, latest_user_text)
        last_message = messages[-1] if messages else None
        last_tool_used = self._is_tool_message(last_message)
        is_kb_query = bool(self._kb_intent_pattern.search(latest_user_text)) or "?" in latest_user_text
        is_status_query = bool(self._status_intent_pattern.search(latest_user_text))
        is_escalation = bool(self._escalation_intent_pattern.search(latest_user_text))
        is_non_receipt = bool(self._non_receipt_pattern.search(latest_user_text))
        active_order_line = active_order_id if active_order_id else "None"

        # ----- LOOP PROTECTION: detect tool errors in recent history -----
        tool_error_guard = ""
        consecutive_tool_failures = 0
        tool_ids_seen = set()
        for msg in reversed(messages):
            if self._is_tool_message(msg):
                content = self._to_text(getattr(msg, "content", ""))
                content_lower = content.lower()
                is_error = any(kw in content_lower for kw in [
                    "error", "failed", "unavailable", "not configured",
                    "unable to reach", "service returned an error",
                    "not found", "lookup failed",
                ])
                # Track tool call IDs to detect repeated calls to the same tool
                tool_name = getattr(msg, "name", None) or ""
                call_key = f"{tool_name}:{content[:50]}"
                if is_error:
                    consecutive_tool_failures += 1
                    tool_ids_seen.add(call_key)
                else:
                    break  # Stop at the first successful tool result
            elif isinstance(msg, HumanMessage):
                break  # Stop looking past the latest user message

        if consecutive_tool_failures >= 1:
            tool_error_guard = """
CRITICAL SAFETY OVERRIDE:
The last tool execution FAILED or returned an error. You MUST NOT call any more tools.
Respond DIRECTLY to the user explaining the issue in a helpful, empathetic way.
Suggest they try again later or provide alternative assistance.
DO NOT attempt to retry the same tool call.
"""
        if consecutive_tool_failures >= 2:
            tool_error_guard = """
CRITICAL SAFETY OVERRIDE (MULTIPLE FAILURES):
Multiple consecutive tool calls have FAILED. This indicates a service outage.
You are STRICTLY FORBIDDEN from calling ANY tools.
Respond to the user directly: acknowledge the issue, apologize, and suggest they try again later.
DO NOT call get_order_status or search_knowledge_base.
"""

        return f"""
SYSTEM:
You are a customer support agent for AI-OPS STORE (UBA Logistics).
You must help users with order tracking, shipment status, returns, refunds, shipping policy, and escalations.
Do not invent order IDs, delivery status, or policy details.
If you do not have enough verified data, ask for clarification or say that the information is unavailable.

SAFETY & TASK GUIDELINES:
1. If the user asks about policy, returns, shipping, refunds, or eligibility, use `search_knowledge_base`.
2. If the user asks about order status, tracking, or shipment location and an order ID is available, use `get_order_status`.
3. If the user asks for a tool but the tool is not applicable, answer directly with a safe, factual response.
4. Never answer policy or status questions from your own memory when the knowledge base or order tool is the correct source.
5. If the user has not provided an order ID when one is needed, ask for it clearly and politely.
6. When escalation or missing delivery is reported, verify the order status first using `get_order_status`, then explain the next operational step.
7. Use the feedback block to adapt tone, but always remain professional and helpful.

CRITICAL STOPPING RULE:
After you receive a tool result, process it and provide the customer-facing answer in your next response.
THEN STOP immediately. Do not call any more tools after providing your answer.
You must always stop after answering the user's question, even if you think you need more information.

AVAILABLE TOOLS:
- get_order_status(order_id): Returns shipping status for a valid order ID.
- search_knowledge_base(query): Returns policy, return, and shipping guidance from the knowledge base.

CURRENT CONTEXT:
- Active Order ID: {active_order_line}
- Latest user text: {latest_user_text}
- User intent likely requires KB search: {is_kb_query}
- User intent likely requires status lookup: {is_status_query}
- User is requesting escalation: {is_escalation}
- User reports non-receipt: {is_non_receipt}
- Last message was a tool response: {last_tool_used}

{tool_error_guard}

TONE ADAPTATION:
{feedback_str}

REPLY FORMAT:
Provide your response directly to the customer. Be concise and helpful.
Do not explain your reasoning or steps—just answer the question.
""".strip()

    # ------------------------------------------------------------------ #
    # Helper Methods
    # ------------------------------------------------------------------ #
    def _to_text(self, content) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    parts.append(str(item["text"]))
                else:
                    parts.append(str(item))
            return " ".join(parts)
        return str(content)

    def _is_tool_message(self, message) -> bool:
        return isinstance(message, ToolMessage) or getattr(message, "type", None) == "tool"

    def _latest_human_text(self, messages) -> str:
        for message in reversed(messages):
            if isinstance(message, HumanMessage):
                return self._to_text(message.content)
        return ""

    def _latest_index(self, messages, predicate) -> int:
        for idx in range(len(messages) - 1, -1, -1):
            if predicate(messages[idx]):
                return idx
        return -1

    def _extract_active_order_id(self, messages, latest_user_text: str):
        # Prefer the more conservative extractor which filters out address-like contexts
        explicit = self._extract_order_id_from_query(latest_user_text)
        if explicit:
            return explicit

        # Fallback: look through history but avoid extracting numbers from address-like messages
        address_kw = [
            "flat",
            "flat no",
            "apt",
            "apartment",
            "building",
            "house",
            "house no",
            "hno",
            "pin",
            "pincode",
            "pin code",
            "street",
            "road",
            "lane",
            "area",
        ]

        for message in reversed(messages):
            text = self._to_text(getattr(message, "content", ""))
            # Skip messages that clearly look like address fragments
            lowered = text.lower()
            if any(kw in lowered for kw in address_kw):
                continue
            history_match = self._order_id_pattern.search(text)
            if history_match:
                return history_match.group(1) or history_match.group(0)
        return None

    def _save_escalation(self, ticket_id: str, order_id: str, reason: str, thread_id: str, details: dict | None = None):
        """Persist escalation to a JSON file. Path can be overridden with `ESCALATION_STORE_PATH`."""
        store_path = os.getenv("ESCALATION_STORE_PATH")
        if not store_path:
            store_path = Path(__file__).resolve().parent.parent / "data" / "escalations.json"
        store_path = Path(store_path)
        try:
            store_path.parent.mkdir(parents=True, exist_ok=True)
            if store_path.exists():
                try:
                    with store_path.open("r", encoding="utf-8") as fh:
                        payload = json.load(fh)
                        if not isinstance(payload, list):
                            payload = []
                except Exception:
                    payload = []
            else:
                payload = []

            record = {
                "ticket_id": ticket_id,
                "order_id": order_id,
                "reason": reason,
                "thread_id": thread_id,
                "details": details or {},
                "timestamp": time.time(),
            }
            payload.append(record)
            with store_path.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
        except Exception as e:
            logging.error(f"Failed to persist escalation to {store_path}: {e}")

    def _post_escalation_webhook(self, ticket_record: dict):
        """POST escalation JSON to configured webhook URL (ESCALATION_WEBHOOK_URL)."""
        webhook = os.getenv("ESCALATION_WEBHOOK_URL", "").strip()
        if not webhook:
            return False
        try:
            data = json.dumps(ticket_record).encode("utf-8")
            req = Request(webhook, data=data, headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(req, timeout=6) as resp:
                # Treat any 2xx as success
                return 200 <= getattr(resp, "status", 200) < 300
        except HTTPError as he:
            logging.error(f"Escalation webhook HTTP error: {he}")
        except URLError as ue:
            logging.error(f"Escalation webhook URL error: {ue}")
        except Exception as e:
            logging.error(f"Escalation webhook failed: {e}")
        return False

    def _content_to_text(self, content) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join([
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and "text" in item
            ])
        return str(content)

    def _extract_order_id_from_query(self, query_text: str):
        # More conservative extraction: prefer explicit order references and avoid picking
        # up numeric fragments that are part of addresses (e.g., "flat D-505").
        for match in self._order_id_pattern.finditer(query_text):
            try:
                candidate = match.group(1) or match.group(0)
            except IndexError:
                candidate = match.group(0)

            # Look behind for address-like keywords to avoid false positives
            start = match.start()
            context_before = query_text[max(0, start - 30):start].lower()
            address_indicators = [
                "flat",
                "flat no",
                "apt",
                "apartment",
                "building",
                "house",
                "hno",
                "street",
                "road",
                "lane",
                "area",
                "pin",
                "pincode",
                "pin code",
            ]
            if any(kw in context_before for kw in address_indicators):
                continue

            # If the query explicitly mentions 'order' or uses '#' treat it as an order id
            if re.search(r"\border\b|order\s*(?:no|number|id)?|#", query_text, re.IGNORECASE):
                return candidate

            # If the user included a status/tracking keyword with digits, accept it
            if re.search(r"\b(status|track|tracking|where|eta)\b", query_text, re.IGNORECASE):
                return candidate

            # If the entire message is just digits, it's likely an order id
            if query_text.strip().isdigit() and 3 <= len(query_text.strip()) <= 10:
                return candidate

            # Otherwise be conservative and skip this match
        return None

    # ------------------------------------------------------------------ #
    # Main Entry Point — Simple 2-turn loop (no infinite loops)
    # ------------------------------------------------------------------ #
    def ask(self, query: str, thread_id: str = "default_thread"):
        """Execute a query with at most one tool call."""
        query_text = str(query or "")
        extracted_id = self._extract_order_id_from_query(query_text)
        if extracted_id:
            self._thread_order_ids[thread_id] = extracted_id

        active_order_id = self._thread_order_ids.get(thread_id)

        recall_order_id_request = bool(active_order_id and re.search(r"\b(order number|order id|my order)\b", query_text, re.IGNORECASE))
        if recall_order_id_request and not self._status_intent_pattern.search(query_text):
            logging.info(f"Recalling stored order ID for thread {thread_id}: {active_order_id}")
            return f"Your current order number is {active_order_id}."

        # If the user requests escalation (or reports non-receipt) and we have an order id,
        # perform a deterministic status check and open an escalation ticket if appropriate.
        is_escalation_request = bool(self._escalation_intent_pattern.search(query_text)) or bool(self._non_receipt_pattern.search(query_text))
        if is_escalation_request and active_order_id:
            logging.info(f"Escalation requested for thread {thread_id}, order {active_order_id}")
            tool = self.tools_map.get("get_order_status")
            if tool:
                tool_result = tool.invoke(active_order_id)
                tool_text = self._to_text(tool_result).lower()
                if "not found" in tool_text or "not found" in str(tool_result).lower():
                    return (
                        "I can't find that order in our system. "
                        "Please provide the full order ID, tracking number, or the phone/email used at checkout so I can escalate."
                    )
                # If order appears delivered or missing, escalate
                if any(k in tool_text for k in ["delivered", "left", "missing", "not delivered", "out for delivery"]):
                    ticket_id = f"UBA-{active_order_id}-{int(time.time())%10000}"
                    logging.info(f"Escalation opened: {ticket_id} for order {active_order_id}")
                    ticket_record = {
                        "ticket_id": ticket_id,
                        "order_id": active_order_id,
                        "reason": "User requested escalation / non-receipt",
                        "thread_id": thread_id,
                        "status": tool_text,
                        "created_at": time.time(),
                    }
                    # Persist and notify webhook (best-effort)
                    try:
                        self._save_escalation(ticket_id, active_order_id, ticket_record["reason"], thread_id, details={"status": tool_text})
                        self._post_escalation_webhook(ticket_record)
                    except Exception as e:
                        logging.error(f"Error persisting or notifying escalation: {e}")

                    return (
                        f"I've opened an escalation for Order {active_order_id} (Ticket {ticket_id}). "
                        "Our specialist team will contact you within 24 hours."
                    )

        start_time = time.time()
        try:
            # Build system prompt
            system_prompt = self._build_dynamic_prompt({"messages": [], "active_order_id": active_order_id})

            # TURN 1: Get LLM response (may include tool calls)
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=query_text),
            ]
            response = self.llm_with_tools.invoke(messages)
            
            # If the response has no tool calls, return it directly
            if not hasattr(response, 'tool_calls') or not response.tool_calls:
                latency = time.time() - start_time
                logging.info(f"Query processed (direct answer). Thread: {thread_id}, Latency: {latency:.2f}s")
                # Coerce response content to text
                return self._content_to_text(getattr(response, 'content', response))
            
            # TURN 2: Execute the first tool call and respond
            tool_call = response.tool_calls[0]
            tool_name = tool_call.get("name") or tool_call.get("type")
            tool_input = tool_call.get("args", {})
            tool_call_id = tool_call.get("id") or str(tool_name)
            
            logging.info(f"Calling tool: {tool_name} with args: {tool_input}")
            
            # Execute the tool
            if tool_name in self.tools_map:
                tool_result = self.tools_map[tool_name].invoke(tool_input)
            else:
                tool_result = f"Unknown tool: {tool_name}"
            
            # TURN 2b: Get final response from LLM with tool result
            # Coerce assistant message into an AIMessage (preserve content and tool call info if present)
            if isinstance(response, AIMessage):
                assistant_msg = response
            else:
                assistant_content = self._to_text(getattr(response, 'content', response))
                assistant_msg = AIMessage(content=assistant_content, tool_calls=getattr(response, 'tool_calls', []))

            # Ensure tool_result is a string for the ToolMessage
            tool_result_text = self._to_text(tool_result)
            tool_msg = ToolMessage(content=tool_result_text, tool_call_id=tool_call_id)

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=query_text),
                assistant_msg,
                tool_msg,
            ]
            final_response = self.llm_with_tools.invoke(messages)
            
            latency = time.time() - start_time
            logging.info(f"Query processed (with tool). Thread: {thread_id}, Latency: {latency:.2f}s")
            
            return self._content_to_text(getattr(final_response, 'content', final_response))
            
        except Exception as e:
            latency = time.time() - start_time
            logging.error(f"Error processing query. Thread: {thread_id}, Error: {str(e)}, Latency: {latency:.2f}s")
            return "I apologize, but I am currently experiencing technical difficulties. Please try again later."
