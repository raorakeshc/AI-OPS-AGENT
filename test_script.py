import traceback
from src.agent import SupportAgent

agent = SupportAgent()
print('User: where is my order 123')
try:
    res = agent.agent_executor.invoke(
        {'messages': [('user', 'where is my order 123')]}, 
        config={'configurable': {'thread_id': 'test_new5'}, 'recursion_limit': 5}
    )
    for i, m in enumerate(res['messages']):
        print(f"Message {i} ({m.type}): {m.content}")
        if hasattr(m, 'tool_calls'):
            print(f"  Tool calls: {m.tool_calls}")
except Exception as e:
    print('ERROR:', str(e))
