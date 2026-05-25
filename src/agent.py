"""A thin CLI runner that imports the modular SupportAgent implementation."""
from dotenv import load_dotenv
import os
import uuid
import logging

try:
    from .support_agent import SupportAgent
except ImportError:
    from support_agent import SupportAgent


load_dotenv()

if not os.path.exists("logs"):
    os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename="logs/agent.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def main():
    agent = SupportAgent()
    current_thread = str(uuid.uuid4())

    print("\n--- Agent Initialized (modular) ---")
    print("Type 'exit' to quit, 'clear' to reset memory, or 'feedback: <message>' to train the agent.\n")

    while True:
        user_in = input("User: ")
        if user_in.lower() in ["exit", "quit"]:
            break
        if user_in.lower() == "clear":
            current_thread = str(uuid.uuid4())
            print("[Memory Cleared. New Conversation Started.]\n")
            continue
        if user_in.lower().startswith("feedback:"):
            feedback_text = user_in[9:].strip()
            agent.feedback_manager.add_feedback(feedback_text)
            logging.info(f"New feedback added: {feedback_text}")
            print(f"[Feedback Saved to data/feedback.json: '{feedback_text}' ]\n")
            continue

        print("\nAgent Thinking & Using Tools...")
        final_response = agent.ask(user_in, thread_id=current_thread)
        print(f"\nAgent: {final_response}\n")
        print("-" * 50)


if __name__ == "__main__":
    main()
