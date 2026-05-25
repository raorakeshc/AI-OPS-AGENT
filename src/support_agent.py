import os
import re
import time
import json
import logging
from urllib.parse import urlencode
from langchain_openai import ChatOpenAI
from langchain_core.messages import ToolMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.tools import tool
from dotenv import load_dotenv

from .feedback import FeedbackManager
from .tools import get_order_status
from .rag import setup_rag


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

        # Intent / extraction patterns
        self._order_id_pattern = re.compile(r"(?:order|#)?\s*(\d{3,10})", re.IGNORECASE)
        self._status_intent_pattern = re.compile(r"\b(status|where|track(?:ing)?|check|update|location|eta|delivered|shipped)\b", re.IGNORECASE)
        self._kb_intent_pattern = re.compile(r"\b(policy|refund|return|shipping|faq|how|can\s+i|what|why|when)\b", re.IGNORECASE)
        self._order_id_recall_pattern = re.compile(r"\b(what(?:'s|\s+is)?\s+my\s+(?:order\s+id|order\s+number)|my\s+(?:order\s+id|order\s+number)\??)\b", re.IGNORECASE)
        self._escalation_intent_pattern = re.compile(r"\b(escalate|escalation|complaint|supervisor|manager|raise\s+(?:a\s+)?ticket)\b", re.IGNORECASE)
        self._non_receipt_pattern = re.compile(r"\b(not\s+rec[ie]{2}ved|didn['’]?t\s+rec[ie]{2}ve|not\s+delivered|missing)\b", re.IGNORECASE)
        self._verified_pattern = re.compile(r"\b(verified|checked|looked|everyone|neighbor| neighbors)\b", re.IGNORECASE)

        # RAG setup
        self.retriever = setup_rag()

        # build a knowledge-base tool bound to this agent (needs access to self.retriever)
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

        # prompt function used by the agent executor
        def dynamic_prompt(state) -> str:
            messages = state.get("messages", [])
            feedback_str = self.feedback_manager.get_feedback_string()
            latest_user_text = self._latest_human_text(messages)
            active_order_id = self._extract_active_order_id(messages, latest_user_text)
            is_kb_query = bool(self._kb_intent_pattern.search(latest_user_text)) or "?" in latest_user_text
            active_order_line = active_order_id if active_order_id else "None"
            return f"""
You are a customer support agent for AI-OPS STORE. 
Your main task is to help users with their orders and policy questions.

GUIDELINES:
1. KB_QUERY_FLAG={is_kb_query}: If this flag is True, you MUST call 'search_knowledge_base' immediately. Do not ask for more info.
2. For any question about policies, returns, shipping, or refunds, you MUST use the 'search_knowledge_base' tool.
3. For any question about order status or tracking, you MUST use the 'get_order_status' tool if an order ID is available.
4. Do not attempt to answer policy or status questions from your own knowledge.
5. If the user provides an order ID ({active_order_line}), use it when relevant.
6. Summarize tool results clearly and professionally for the user.

Current Context:
- Active Order ID: {active_order_line}
- User Question Detected as Policy Query: {is_kb_query}
""".strip()

        self.llm_with_tools = self.llm.bind_tools(self.tools)
        self.agent_executor = create_react_agent(
            self.llm_with_tools,
            self.tools,
            checkpointer=self.memory,
            prompt=dynamic_prompt,
        )
        logging.info("SupportAgent initialized successfully.")

    # --- small helpers ---
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
        current_match = self._order_id_pattern.search(latest_user_text)
        if current_match:
            return current_match.group(0)

        for message in reversed(messages):
            text = self._to_text(getattr(message, "content", ""))
            history_match = self._order_id_pattern.search(text)
            if history_match:
                return history_match.group(0)
        return None

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
        match = self._order_id_pattern.search(query_text)
        if match:
            try:
                return match.group(1)
            except IndexError:
                return match.group(0)
        return None

    def _is_order_id_recall_query(self, query_text: str) -> bool:
        return bool(self._order_id_recall_pattern.search(query_text))

    def _safe_single_pass_response(self, query: str, thread_id: str) -> str:
        query_text = str(query or "")
        feedback_str = self.feedback_manager.get_feedback_string()

        current_id_match = self._order_id_pattern.search(query_text)
        if current_id_match:
            self._thread_order_ids[thread_id] = current_id_match.group(0)

        active_order_id = self._thread_order_ids.get(thread_id)
        is_status_query = bool(self._status_intent_pattern.search(query_text))
        is_kb_query = bool(self._kb_intent_pattern.search(query_text)) or "?" in query_text

        if is_status_query:
            if not active_order_id:
                return "Please share your order id or order number (10 characters or fewer), and I will check the status for you."

            tool_result = get_order_status.invoke({"order_id": active_order_id})
            return f"Order {active_order_id} status: {tool_result}"

        if is_kb_query:
            if not getattr(self, "retriever", None):
                return "Knowledge base is currently unavailable. Please try again shortly."

            docs = self.retriever.invoke(query_text)
            kb_context = "\n\n".join(doc.page_content for doc in docs) if docs else ""
            if not kb_context.strip():
                return "I could not find a relevant policy entry. Please rephrase your question."

            synthesis_prompt = f"""
You are a customer support agent. Answer only from the provided knowledge base context.
If the answer is not present, clearly say you cannot find it in the KB.

User question: {query_text}

Knowledge base context:
{kb_context}

{feedback_str}
""".strip()
            llm_result = self.llm.invoke(synthesis_prompt)
            return self._content_to_text(llm_result.content)

        if active_order_id:
            return f"I can help with your request. I still have Order {active_order_id} in context if you want me to check its status."
        return "How can I help you today? If you have an order issue, share your order id or order number (10 characters or fewer)."

    def ask(self, query: str, thread_id: str = "default_thread"):
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 10}
        inputs = {"messages": [("user", query)]}

        query_text = str(query or "")
        extracted_id = self._extract_order_id_from_query(query_text)
        if extracted_id:
            self._thread_order_ids[thread_id] = extracted_id

        remembered_id = self._thread_order_ids.get(thread_id)
        is_recall_query = self._is_order_id_recall_query(query_text)

        if is_recall_query:
            if remembered_id:
                return f"Your current order id or order number is {remembered_id}."
            return "I do not have your order id or order number yet. Please share it (10 characters or fewer)."

        is_escalation_query = bool(self._escalation_intent_pattern.search(query_text))
        mentions_non_receipt = bool(self._non_receipt_pattern.search(query_text))

        if is_escalation_query or mentions_non_receipt:
            active_order_id = extracted_id or remembered_id
            if not active_order_id:
                return "Yes, I can help escalate this. Please share your order id or order number (10 characters or fewer)."

            latest_status = get_order_status.invoke({"order_id": active_order_id})
            latest_status_lower = str(latest_status).lower()

            if "delivered" in latest_status_lower:
                is_verified = bool(self._verified_pattern.search(query_text))
                if is_verified:
                    return (
                        f"Thank you for confirming. I have now initiated a formal escalation and carrier investigation for Order {active_order_id}. "
                        "Our logistics team will contact the carrier and provide a resolution within 6 hours. "
                        "A support ticket has been raised (ID: UBA-" + str(active_order_id) + ")."
                    )
                return (
                    f"Yes — I can escalate this for Order {active_order_id}. "
                    "Since it is marked Delivered but not received, please verify your delivery location and neighbors, "
                    "then I will open a carrier investigation immediately. "
                    "Priority SLA: initial response within 6 hours."
                )

            return (
                f"Yes — I can escalate this for Order {active_order_id}. "
                f"Current status is: {latest_status}. "
                "I will raise a support ticket for investigation and share an update within 24 hours."
            )

        is_status_query = bool(self._status_intent_pattern.search(query_text))
        is_order_question = bool(re.search(r"\b(order|package)\b", query_text, re.IGNORECASE)) and "?" in query_text
        is_order_status_like_query = is_status_query or is_order_question

        is_kb_query = bool(self._kb_intent_pattern.search(query_text)) or "?" in query_text

        if extracted_id and not is_order_status_like_query and not is_kb_query:
            return f"Thanks — I have saved order id or order number {extracted_id}. Ask me to check its status anytime."

        if is_order_status_like_query:
            active_order_id = extracted_id or remembered_id
            if not active_order_id:
                return "Please share your order id or order number (10 characters or fewer), and I will check the status for you."

            tool_result = get_order_status.invoke({"order_id": active_order_id})
            return f"Order {active_order_id} status: {tool_result}"

        if is_kb_query:
            logging.info(f"Directly processing KB query: {query_text}")
            return self._safe_single_pass_response(query=query_text, thread_id=thread_id)

        start_time = time.time()
        try:
            response = self.agent_executor.invoke(inputs, config=config)
            latency = time.time() - start_time
            logging.info(f"Query processed. Thread: {thread_id}, Latency: {latency:.2f}s")

            last_message = response["messages"][-1]
            final_text = self._content_to_text(last_message.content)
            if "need more steps" in final_text.lower():
                logging.warning(f"Agent returned 'need more steps'. Using single-pass fallback. Thread: {thread_id}")
                return self._safe_single_pass_response(query=query, thread_id=thread_id)
            return final_text
        except Exception as e:
            latency = time.time() - start_time
            logging.error(f"Error processing query. Thread: {thread_id}, Error: {str(e)}, Latency: {latency:.2f}s")
            if "recursion" in str(e).lower() and "limit" in str(e).lower():
                logging.warning(f"Recursion limit reached. Using single-pass fallback. Thread: {thread_id}")
                return self._safe_single_pass_response(query=query, thread_id=thread_id)
            return "I apologize, but I am currently experiencing technical difficulties. Please try again later."
