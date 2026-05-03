import os
from dotenv import load_dotenv
from agent import SupportAgent

load_dotenv()

def test_escalation():
    agent = SupportAgent()
    print("\n--- Testing Escalation Flow ---")
    
    # Step 1: Set active order
    print("\nQuery: can you check the status of 128")
    print(f"Agent response: {agent.ask('can you check the status of 128')}")
    
    # Step 2: Request escalation
    print("\nQuery: can i escalate ?")
    print(f"Agent response: {agent.ask('can i escalate ?')}")
    
    # Step 3: Confirm verification (with typo)
    print("\nQuery: yes i verified with everyone , but not recieved")
    print(f"Agent response: {agent.ask('yes i verified with everyone , but not recieved')}")

if __name__ == "__main__":
    test_escalation()
