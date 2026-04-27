import os
import uuid
import json
import logging
import time
import re
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
    """Gets the shipping status of an order given its order ID.
    IMPORTANT SAFEGUARD: order_id must be 10 characters or fewer.
    """
    if len(order_id) > 10:
        return "Error: Invalid tool usage. order_id is too long. It must be 10 characters or fewer."
    
    # Mock order database
    orders = {
        "123": "Shipped",
        "456": "In Transit",
        "789": "Delivered"
    }
    return orders.get(order_id, f"Order {order_id} not found.")

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
        
        # Define the Dynamic Prompt Function
        def dynamic_prompt(state) -> str:
            print("\n--- DEBUG: DYNAMIC PROMPT START ---")
            messages = state.get("messages", [])
            feedback_str = self.feedback_manager.get_feedback_string()
            
            import re
            from langchain_core.messages import ToolMessage, HumanMessage

            # 1. FIND THE ID (Priority: Current Message -> Then History)
            found_id = None
            
            # Check the latest user message first
            last_user_msg = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
            current_match = re.search(r'\b\d{3,10}\b', str(last_user_msg))
            
            if current_match:
                found_id = current_match.group()
                print(f"DEBUG: Found NEW ID in latest message: {found_id}")
            else:
                # Fallback: Look through history if the current message is empty of IDs
                for m in reversed(messages[:-1]): # Look at everything EXCEPT the current message
                    history_match = re.search(r'\b\d{3,10}\b', str(m.content))
                    if history_match:
                        found_id = history_match.group()
                        print(f"DEBUG: No new ID found. Using ID from memory: {found_id}")
                        break

            # 2. CHECK TOOL STATUS FOR THIS SPECIFIC TURN
            # We only care if the tool was called RECENTLY (the last 2 messages)
            # This prevents using old "Shipped" status for a brand new ID
            last_status = None
            if len(messages) > 0:
                for m in reversed(messages[-2:]): # Only look at the immediate previous exchange
                    if isinstance(m, ToolMessage) or getattr(m, 'type', None) == 'tool':
                        last_status = m.content
                        break

            is_last_msg_tool = False
            if messages:
                is_last_msg_tool = isinstance(messages[-1], ToolMessage) or getattr(messages[-1], 'type', None) == 'tool'

            # 3. INTENT DETECTION (NEW)
            intent_keywords = ["status", "where", "track", "check", "update", "location"]
            is_status_query = any(word in last_user_msg.lower() for word in intent_keywords)

            # Check if the user is asking a general question (potential KB hit)
            # Questions usually start with these words or end with a '?'
            kb_keywords = ["policy", "how", "what", "can i", "refund", "return", "shipping"]
            is_kb_query = any(word in last_user_msg.lower() for word in kb_keywords) or "?" in last_user_msg

        # 4. THE REVISED DECISION ENGINE
            
            # BRANCH A: Status Request (Force Tool)
            # Only trigger if the user explicitly asked for a status/where/check
            if found_id and is_status_query and not is_last_msg_tool:
                print(f"DEBUG: Branch A -> Executing Tool Call.")
                return f"TOOL_COMMAND: Call get_order_status(order_id='{found_id}')."

            # BRANCH B: Reporting Result (Just after tool call)
            elif is_last_msg_tool:
                print(f"DEBUG: Branch B -> Reporting result.")
                return f"""FINAL ANSWER: The status of order {found_id} is {last_status}.
                STYLE: {feedback_str}
                STOP: Do not call any more tools."""

            # BRANCH C: Chat Mode (What is my ID / General Chat)
            elif is_kb_query:
                print(f"DEBUG: Branch C -> General Question detected. Forcing KB Search.")
                return f"""You are a Support Agent. 
                The user is asking a question: '{last_user_msg}'
                
                CRITICAL: Use the 'search_knowledge_base' tool to find the answer.
                Do not answer from your own memory. Use the tool.
                """

            # BRANCH D: Pure Greeting / ID Request
            else:
                return f"""You are a Support Agent. ID in memory: {found_id}.
                If they want their ID, tell them. Otherwise, ask how you can help.
                STYLE: {feedback_str}
                """

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

    def ask(self, query: str, thread_id: str = "default_thread"):
        # Add recursion_limit to prevent infinite tool loops
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 15}
       # We pass the dynamic prompt as a System Message every time to ensure it's fresh
        inputs = {"messages": [("user", query)]}
        
        start_time = time.time()
        try:
            response = self.agent_executor.invoke(inputs, config=config)
            latency = time.time() - start_time
            logging.info(f"Query processed. Thread: {thread_id}, Latency: {latency:.2f}s")
            
            last_message = response["messages"][-1]
            content = last_message.content
            if isinstance(content, list):
                return "".join([item.get("text", "") for item in content if isinstance(item, dict) and "text" in item])
            return content
        except Exception as e:
            latency = time.time() - start_time
            logging.error(f"Error processing query. Thread: {thread_id}, Error: {str(e)}, Latency: {latency:.2f}s")
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