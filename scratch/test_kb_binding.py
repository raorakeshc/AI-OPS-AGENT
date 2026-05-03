import os
from dotenv import load_dotenv
from agent import SupportAgent

load_dotenv()

def test_kb():
    agent = SupportAgent()
    print("\n--- Testing KB Tool Binding ---")
    queries = ["what is the refund policy ?", "what is the shipping policy"]
    
    for query in queries:
        print(f"\nQuery: {query}")
        response = agent.ask(query)
        print(f"Agent response: {response}")

if __name__ == "__main__":
    test_kb()
