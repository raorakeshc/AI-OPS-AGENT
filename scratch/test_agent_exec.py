import traceback
import os
from dotenv import load_dotenv
load_dotenv()

from src.support_agent import SupportAgent

agent = SupportAgent()
print('Running agent.agent_executor.invoke with recursion_limit 10...')
try:
    res = agent.agent_executor.invoke(
        {'messages': [('user', 'where is my order 123')]}, 
        config={'configurable': {'thread_id': 'test_new_10'}, 'recursion_limit': 10}
    )
    for i, m in enumerate(res['messages']):
        print(f"Message {i} ({m.type}): {m.content}")
        if hasattr(m, 'tool_calls'):
            print(f"  Tool calls: {m.tool_calls}")
except Exception as e:
    print('ERROR:', str(e))
    traceback.print_exc()
