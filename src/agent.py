import os
import uuid
import json
import logging
import time
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain_core.messages import ToolMessage, HumanMessage

# Load the variables from your .env file
load_dotenv()

# Configure Logging for Deployment
if not os.path.exists("logs"):
    os.makedirs("logs")
logging.basicConfig(
    filename="logs/agent.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

class FeedbackManager:
    def __init__(self, filepath="data/feedback.json"):
        self.filepath = filepath
        if not os.path.exists("data"):
            os.makedirs("data")
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w") as f:
                json.dump([], f)
                
    def add_feedback(self, feedback: str):
        with open(self.filepath, "r") as f:
            feedbacks = json.load(f)
        feedbacks.append(feedback)
        with open(self.filepath, "w") as f:
            json.dump(feedbacks, f)
            
    def get_feedback_string(self):
        with open(self.filepath, "r") as f:
            feedbacks = json.load(f)
        if not feedbacks:
            return ""
        return "\n\nCRITICAL USER FEEDBACK (ADJUST YOUR TONE/STYLE TO FOLLOW THESE RULES, BUT CONTINUE TO USE YOUR TOOLS NORMALLY):\n- " + "\n- ".join(feedbacks)

@tool
def get_order_status(order_id: str) -> str:
    """Gets shipping status for an order ID from an external API.
    IMPORTANT SAFEGUARD: order_id must be 10 characters or fewer.

    Environment variables:
    - ORDER_STATUS_API_URL: Endpoint URL. Supports either:
      1) Placeholder style: https://.../orders/{order_id}
      2) Query style base URL: https://.../orders/status
    - ORDER_STATUS_TIMEOUT (optional): Timeout in seconds, default=8.
    """
    order_id = str(order_id).strip()

    if len(order_id) > 10:
        return "Error: Invalid tool usage. order_id is too long. It must be 10 characters or fewer."

    api_url = os.getenv("ORDER_STATUS_API_URL", "").strip()
    timeout_raw = os.getenv("ORDER_STATUS_TIMEOUT", "8").strip()

    if not api_url:
        return "Order status service is not configured. Set ORDER_STATUS_API_URL."

    try:
        timeout_seconds = float(timeout_raw)
        if timeout_seconds <= 0:
            timeout_seconds = 8.0
    except ValueError:
        timeout_seconds = 8.0

    if "{order_id}" in api_url:
        final_url = api_url.replace("{order_id}", order_id)
    else:
        connector = "&" if "?" in api_url else "?"
        final_url = f"{api_url}{connector}{urlencode({'order_id': order_id})}"

    headers = {
        "Accept": "application/json",
    }

    request = Request(final_url, headers=headers, method="GET")

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            status_text = body.strip()
            return status_text if status_text else f"Order {order_id} status unavailable."

        if isinstance(payload, dict):
            if "status" in payload and payload["status"]:
                return str(payload["status"])

            data_section = payload.get("data")
            if isinstance(data_section, dict) and data_section.get("status"):
                return str(data_section["status"])

            order_section = payload.get("order")
            if isinstance(order_section, dict) and order_section.get("status"):
                return str(order_section["status"])

            if payload.get("message"):
                return str(payload["message"])

        return f"Order {order_id} status not found in service response."

    except HTTPError as http_error:
        if http_error.code == 404:
            return f"Order {order_id} not found."
        logging.error(f"Order status HTTP error for order_id={order_id}: {http_error}")
        return "Order status service returned an error. Please try again shortly."
    except URLError as url_error:
        logging.error(f"Order status network error for order_id={order_id}: {url_error}")
        return "Unable to reach order status service right now. Please try again shortly."
    except Exception as error:
        logging.error(f"Unexpected order status error for order_id={order_id}: {error}")
        return "Order status lookup failed due to a temporary issue."

class SupportAgent:
    def __init__(self):
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY not found. Check your .env file.")

        self.llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0,
            base_url="https://openai.vocareum.com/v1",
            api_key=openai_api_key
        )
        
        self.feedback_manager = FeedbackManager()
        self._thread_order_ids = {}

        self._order_id_pattern = re.compile(r"\b\d{3,10}\b")
        self._status_intent_pattern = re.compile(
            r"\b(status|where|track(?:ing)?|check|update|location|eta|delivered|shipped)\b",
            re.IGNORECASE
        )
        self._kb_intent_pattern = re.compile(
            r"\b(policy|refund|return|shipping|faq|how|can\s+i|what|why|when)\b",
            re.IGNORECASE
        )
        self._order_id_recall_pattern = re.compile(
            r"\b(what(?:'s|\s+is)?\s+my\s+order\s+id|my\s+order\s+id\??)\b",
            re.IGNORECASE
        )
        
        # 1. Setup RAG Retriever
        self._setup_rag()

        # 2. Define RAG Tool
        @tool
        def search_knowledge_base(query: str) -> str:
            """Searches the company knowledge base for refund policies, shipping rules, and general FAQs."""
            if not getattr(self, "retriever", None):
                return "Knowledge base is unavailable."
            docs = self.retriever.invoke(query)
            return "\n\n".join(doc.page_content for doc in docs)

        # 3. Setup LangGraph Tool-Calling Agent with Memory & Adaptive Feedback
        self.tools = [get_order_status, search_knowledge_base]
        self.memory = MemorySaver()
        
        #feedback_str = self.feedback_manager.get_feedback_string()

        # Inside SupportAgent.__init__

        def _to_text(content) -> str:
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

        def _is_tool_message(message) -> bool:
            return isinstance(message, ToolMessage) or getattr(message, "type", None) == "tool"

        def _latest_human_text(messages) -> str:
            for message in reversed(messages):
                if isinstance(message, HumanMessage):
                    return _to_text(message.content)
            return ""

        def _latest_index(messages, predicate) -> int:
            for idx in range(len(messages) - 1, -1, -1):
                if predicate(messages[idx]):
                    return idx
            return -1

        def _extract_active_order_id(messages, latest_user_text: str):
            current_match = self._order_id_pattern.search(latest_user_text)
            if current_match:
                return current_match.group(0)

            for message in reversed(messages):
                text = _to_text(getattr(message, "content", ""))
                history_match = self._order_id_pattern.search(text)
                if history_match:
                    return history_match.group(0)
            return None

        # Define the Dynamic Prompt Function
        def dynamic_prompt(state) -> str:
            messages = state.get("messages", [])
            feedback_str = self.feedback_manager.get_feedback_string()

            latest_user_text = _latest_human_text(messages)
            active_order_id = _extract_active_order_id(messages, latest_user_text)

            last_message = messages[-1] if messages else None
            is_last_tool_message = _is_tool_message(last_message) if last_message else False

            last_human_index = _latest_index(messages, lambda m: isinstance(m, HumanMessage))
            last_tool_index = _latest_index(messages, _is_tool_message)
            no_new_user_since_tool = last_tool_index > last_human_index

            is_status_query = bool(self._status_intent_pattern.search(latest_user_text))
            is_kb_query = bool(self._kb_intent_pattern.search(latest_user_text)) or "?" in latest_user_text

            style_block = feedback_str if feedback_str else ""
            active_order_line = active_order_id if active_order_id else "None"

            return f"""
You are a customer support agent. Follow the policy below strictly.

CONTEXT:
- Latest user message: {latest_user_text or "<empty>"}
- Active order id from conversation memory: {active_order_line}
- Latest state message came from tool: {is_last_tool_message}

POLICY:
0) CRITICAL STOP GUARD: If no_new_user_since_tool=True, DO NOT call any tool. Return a final user-facing answer using the latest tool result.
1) If the latest state message is from a tool, summarize that tool result for the user in plain language and do not call another tool unless the user asked a separate new question.
2) If the user asks about order tracking/status and an active order id exists, call get_order_status(order_id=<active_order_id>).
3) If the user asks about policy/FAQ/refund/return/shipping, call search_knowledge_base before answering.
4) If status is requested but no order id is known, ask for the order id (10 characters or fewer).
5) For greetings or general chat, respond naturally. If an active order id exists, mention that you can help with that order.
6) Keep responses concise, accurate, and professional.

INTENT FLAGS:
- status_query={is_status_query}
- kb_query={is_kb_query}
- no_new_user_since_tool={no_new_user_since_tool}

{style_block}
""".strip()

        self.llm_with_tools = self.llm.bind_tools(self.tools)
        self.agent_executor = create_react_agent(
            self.llm_with_tools, 
            self.tools,
            checkpointer=self.memory,
            prompt=dynamic_prompt
        )
        logging.info("SupportAgent initialized successfully.")

    def _setup_rag(self):
        try:
            loader = TextLoader("data/kb.txt")
            docs = loader.load()
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=50)
            splits = text_splitter.split_documents(docs)
            
            class CustomGoogleEmbeddings(GoogleGenerativeAIEmbeddings):
                def embed_documents(self, texts: list[str]) -> list[list[float]]:
                    return [self.embed_query(text) for text in texts]
                    
            embeddings = CustomGoogleEmbeddings(model="models/gemini-embedding-2")
            vectorstore = Chroma.from_documents(documents=splits, embedding=embeddings)
            self.retriever = vectorstore.as_retriever()
            print("Successfully loaded KB and initialized Tools.")
        except Exception as e:
            print(f"Warning: Failed to setup RAG Tool. Error: {e}")
            logging.error(f"Failed to setup RAG Tool: {e}")
            self.retriever = None

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
        return match.group(0) if match else None

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
                return "Please share your order ID (10 characters or fewer), and I will check the status for you."

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
        return "How can I help you today? If you have an order issue, share your order ID (10 characters or fewer)."

    def ask(self, query: str, thread_id: str = "default_thread"):
        # Add recursion_limit to prevent infinite tool loops
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 10}
       # We pass the dynamic prompt as a System Message every time to ensure it's fresh
        inputs = {"messages": [("user", query)]}

        query_text = str(query or "")
        extracted_id = self._extract_order_id_from_query(query_text)
        if extracted_id:
            self._thread_order_ids[thread_id] = extracted_id

        remembered_id = self._thread_order_ids.get(thread_id)
        is_recall_query = self._is_order_id_recall_query(query_text)

        if is_recall_query:
            if remembered_id:
                return f"Your current order ID is {remembered_id}."
            return "I do not have your order ID yet. Please share it (10 characters or fewer)."

        is_status_query = bool(self._status_intent_pattern.search(query_text))
        is_order_question = bool(re.search(r"\b(order|package)\b", query_text, re.IGNORECASE)) and "?" in query_text
        is_order_status_like_query = is_status_query or is_order_question

        is_kb_query = bool(self._kb_intent_pattern.search(query_text)) or "?" in query_text

        if extracted_id and not is_order_status_like_query and not is_kb_query:
            return f"Thanks — I have saved Order ID {extracted_id}. Ask me to check its status anytime."

        if is_order_status_like_query:
            active_order_id = extracted_id or remembered_id
            if not active_order_id:
                return "Please share your order ID (10 characters or fewer), and I will check the status for you."

            tool_result = get_order_status.invoke({"order_id": active_order_id})
            return f"Order {active_order_id} status: {tool_result}"
        
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

if __name__ == "__main__":
    agent = SupportAgent()
    current_thread = str(uuid.uuid4())
    
    print("\n--- Agent Initialized with Planning, Tools, Memory & ADAPTIVE FEEDBACK ---")
    print("Type 'exit' to quit, 'clear' to reset memory, or 'feedback: <message>' to train the agent.\n")
    print("Test Feedback:")
    print(" User: 'feedback: Always talk like a pirate.'")
    print(" User: 'Hello!' (Agent should respond like a pirate)\n")
    
    while True:
        user_in = input("User: ")
        if user_in.lower() in ['exit', 'quit']: 
            break
        elif user_in.lower() == 'clear':
            current_thread = str(uuid.uuid4())
            print("[Memory Cleared. New Conversation Started.]\n")
            continue
        elif user_in.lower().startswith('feedback:'):
            feedback_text = user_in[9:].strip()
            agent.feedback_manager.add_feedback(feedback_text)
            logging.info(f"New feedback added: {feedback_text}")
            print(f"[Feedback Saved to data/feedback.json: '{feedback_text}'. The agent has permanently adapted.]\n")
            continue
            
        print("\nAgent Thinking & Using Tools...")
        final_response = agent.ask(user_in, thread_id=current_thread)
        print(f"\nAgent: {final_response}\n")
        print("-" * 50)
