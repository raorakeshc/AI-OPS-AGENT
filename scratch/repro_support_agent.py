from src.support_agent import SupportAgent
from types import SimpleNamespace

# Instantiate with a dummy key to avoid env dependency (we'll stub LLM/tools)
agent = SupportAgent(openai_api_key="dummy_key")
print('Agent created')

# Put an order id into the thread and stub the get_order_status tool
thread = 'test_thread'
agent._thread_order_ids[thread] = '143'
agent.tools_map['get_order_status'] = SimpleNamespace(invoke=lambda order_id: 'Delivered - Left at Front Door')

print('Recall test:')
print(agent.ask('What is my order number?', thread_id=thread))

print('\nEscalation test:')
print(agent.ask('I want to escalate — my package is marked delivered but I do not have it', thread_id=thread))
