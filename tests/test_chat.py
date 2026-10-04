import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from atlas.chat import ChatFailed, ChatUnavailable, chat_reply, validate_messages
from atlas.graph import filtered_graph
from atlas.seed import build_dataset
from atlas.server import Application, make_handler

TEST_TMP = Path(__file__).resolve().parents[1] / 'data' / 'test-tmp'
TEST_TMP.mkdir(parents=True, exist_ok=True)
OPENAI = {'ATLAS_AGENT_PROVIDER': 'openai', 'OPENAI_API_KEY': 'test-key'}
QUESTION = [{'role': 'user', 'content': 'Is there a registry both communities use?'}]


class ChatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = filtered_graph(build_dataset(), 'MONDO:0012812')

    def reply(self, **kw):
        return {'answer': 'Both communities are represented in Simons Searchlight.', 'citation_ids': ['stx-registry'], 'follow_up_questions': ['How do I join?'], **kw}

    def test_grounded_answer_is_returned_with_resolved_citations(self):
        with patch.dict(os.environ, OPENAI), patch('atlas.chat.model_call', return_value=self.reply()) as call:
            result = chat_reply(self.graph, QUESTION, 'patient', 'zh-CN')
        self.assertEqual(result['citation_ids'], ['stx-registry'])
        self.assertEqual(result['citations'][0]['id'], 'stx-registry')
        task, previous = call.call_args.args[1], call.call_args.args[2]
        self.assertIn('Explain every necessary technical term', task)   # patient audience
        self.assertIn('Simplified Chinese', task)
        self.assertIn('Never diagnose, prescribe', task)
        self.assertEqual(previous, {'conversation': QUESTION})
        self.assertEqual(call.call_args.kwargs['schema_name'], 'asterisk_chat_reply')

    def test_fabricated_citation_is_rejected(self):
        with patch.dict(os.environ, OPENAI), patch('atlas.chat.model_call', return_value=self.reply(citation_ids=['made-up-paper'])):
            with self.assertRaises(ChatFailed):
                chat_reply(self.graph, QUESTION)

    def test_reflected_secret_is_rejected(self):
        with patch.dict(os.environ, OPENAI), patch('atlas.chat.model_call', return_value=self.reply(answer='key test-key')):
            with self.assertRaises(ChatFailed):
                chat_reply(self.graph, QUESTION)

    def test_without_a_live_provider_chat_is_unavailable(self):
        env = {k: v for k, v in os.environ.items() if k not in ('OPENAI_API_KEY', 'GEMINI_API_KEY', 'ATLAS_AGENT_PROVIDER')}
        with patch.dict(os.environ, env, clear=True), patch('atlas.chat.model_call') as call:
            with self.assertRaises(ChatUnavailable):
                chat_reply(self.graph, QUESTION)
        with patch.dict(os.environ, {**env, 'ATLAS_AGENT_PROVIDER': 'codex_snapshot'}, clear=True), patch('atlas.chat.model_call') as call:
            with self.assertRaises(ChatUnavailable):   # a fixed precomputed review cannot answer new questions
                chat_reply(self.graph, QUESTION)
        call.assert_not_called()

    def test_message_validation(self):
        for bad in ([], [{'role': 'assistant', 'content': 'hi'}], [{'role': 'system', 'content': 'x'}],
                    [{'role': 'user', 'content': 'x' * 1201}], [{'role': 'user', 'content': '   '}], 'hello'):
            with self.assertRaises(ValueError):
                validate_messages(bad)
        self.assertEqual(len(validate_messages(QUESTION * 1)), 1)


class ChatHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=TEST_TMP)
        self.app = Application(Path(self.tmp.name) / 'test.sqlite')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.app))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.app.pool.shutdown(wait=True)
        self.tmp.cleanup()

    def post(self, body):
        request = Request(self.url + '/api/chat', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
        with urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())

    def test_chat_endpoint(self):
        with patch.dict(os.environ, OPENAI), patch('atlas.chat.model_call', return_value={'answer': 'Yes.', 'citation_ids': ['stx-registry'], 'follow_up_questions': []}):
            status, body = self.post({'focus': 'MONDO:0012812', 'messages': QUESTION, 'role': 'expert'})
        self.assertEqual((status, body['answer']), (200, 'Yes.'))
        with patch.dict(os.environ, {'ATLAS_AGENT_PROVIDER': 'codex_snapshot'}):
            with self.assertRaises(HTTPError) as error:
                self.post({'messages': QUESTION})
        self.assertEqual(error.exception.code, 503)
        with self.assertRaises(HTTPError) as error:
            self.post({'messages': [{'role': 'assistant', 'content': 'no question'}]})
        self.assertEqual(error.exception.code, 400)
