import os
import json
from types import SimpleNamespace
from pathlib import Path

from src.support_agent import SupportAgent


def run_tests():
    scratch_dir = Path(__file__).resolve().parent
    store_path = scratch_dir / "escalations_test.json"
    # Ensure clean state
    if store_path.exists():
        store_path.unlink()

    os.environ["ESCALATION_STORE_PATH"] = str(store_path)

    agent = SupportAgent(openai_api_key="dummy")

    # Stub get_order_status
    agent.tools_map['get_order_status'] = SimpleNamespace(invoke=lambda oid: 'Delivered - Left at Front Door')

    thread = 'test_thread'
    agent._thread_order_ids[thread] = '143'

    # Recall should work
    recall = agent.ask('what is my order number', thread_id=thread)
    print('Recall:', recall)
    assert '143' in recall

    # Escalation should create ticket and persist
    resp = agent.ask('please escalate this order, I do not have it', thread_id=thread)
    print('Escalation response:', resp)
    assert 'Ticket' in resp or 'Ticket' in resp

    # Check persisted file
    assert store_path.exists(), 'escalation store not created'
    data = json.loads(store_path.read_text(encoding='utf-8'))
    assert isinstance(data, list) and len(data) >= 1
    record = data[-1]
    assert record.get('order_id') == '143'
    assert record.get('ticket_id')

    # Test address vs order-number confusion: providing address should not set thread order id
    new_thread = 't2'
    agent._thread_order_ids.pop(new_thread, None)
    agent.ask('My address is flat D-505 , ShreeKrishna homes , Hyderbad , State - Telangana PIN CODE 44443', thread_id=new_thread)
    assert agent._thread_order_ids.get(new_thread) is None

    # Now supplying an explicit order mention should set it
    agent.ask('order 505', thread_id=new_thread)
    assert agent._thread_order_ids.get(new_thread) == '505'

    print('All tests passed.')


if __name__ == '__main__':
    run_tests()
