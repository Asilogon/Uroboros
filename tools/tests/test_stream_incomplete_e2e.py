"""End-to-end test: incomplete stream -> SSE error to client, no 'успешно' fabrication."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from deepseek_gui import app as app_module
from deepseek_gui.app import app as flask_app


class FakeClient:
    """Emits partial text then incomplete. Mimics a network drop."""

    def __init__(self):
        self._session_last_msg_ids = {}

    def load_session(self, path=None):
        return True

    def create_chat(self, agent="chat"):
        return "fake-new-chat-id"

    def send_message(self, chat_session_id, prompt, stream=True, thinking_enabled=False,
                     ref_file_ids=None, parent_message_id=None):
        def gen():
            yield {"type": "text", "content": "Начинаю выполнять задачу..."}
            yield {"type": "incomplete", "reason": "network_error: ChunkedEncodingError"}
        return gen()


class FakeProjectsManager:
    def __init__(self):
        self.messages = []
        self._project = {
            "id": "test",
            "name": "TestProj",
            "mode": "solo",
            "root_path": str(ROOT),
            "lead_agent": {"name": "Lead", "chat_session_id": "fake-chat-id"},
            "subagents": [],
            "lead_history": [],
        }

    def get_project(self, project_id):
        return dict(self._project)

    def load_all(self):
        return [dict(self._project)]

    def save_all(self, projects):
        pass

    def append_lead_message(self, *a, **kw):
        self.messages.append((a, kw))

    def append_subagent_message(self, *a, **kw):
        self.messages.append((a, kw))

    def update_agent_task(self, *a, **kw):
        pass

    def add_subagent(self, *a, **kw):
        return None

    def find_subagent_by_name(self, *a, **kw):
        return None


# Install fakes BEFORE Flask routes access them
app_module.active_client = FakeClient()
app_module.projects_manager = FakeProjectsManager()

client = flask_app.test_client()
print('[test] Sending POST to /api/projects/test/lead/message ...')
resp = client.post('/api/projects/test/lead/message', json={
    'prompt': 'Test the incomplete handling',
    'thinking_enabled': False,
})
print('[test] status:', resp.status_code)

body = resp.data.decode('utf-8', 'replace')
print('[test] SSE body (first 1500 chars):')
print(body[:1500])
print('...')

# Assertions
errors = []
if resp.status_code != 200:
    errors.append(f'HTTP status is {resp.status_code}, expected 200')
if 'connection_lost' not in body:
    errors.append('NO connection_lost in SSE body')
if '"type": "error"' not in body and '"type":"error"' not in body:
    errors.append('NO error event in SSE body')
# Ensure no fabricated success message when incomplete
for token in ('Все задачи успешно выполнены', 'успешно выполнена командой'):
    if token in body:
        errors.append(f'Fabricated success text found: {token!r}')

if errors:
    print()
    print('FAIL:')
    for e in errors:
        print(' -', e)
    sys.exit(1)

print()
print('OK: incomplete stream is reported to the client as an error, not success.')
