import asyncio
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services import agent_service as service


class AgentContextTests(unittest.TestCase):
    def test_explicit_intent_wins(self):
        for question, expected in [
            ('那短暂呢', 'followup'), ('暂时的呢', 'followup'),
            ('以免呢', 'followup'), ('名词呢', 'followup'),
            ('这个从句修饰谁', 'grammar'), ('短暂的人生怎么翻译', 'translation'),
        ]:
            with self.subTest(question=question):
                self.assertEqual(service.classify_intent(question), expected)
        self.assertEqual(service.classify_intent('这个从句修饰谁', 'transition'), 'grammar')

    def test_topic_and_prompt(self):
        messages = service._build_messages('followup', '那短暂呢', 'sentence', '', '', '', 'transition')
        self.assertIn('<discussion_topic>\ntransition', messages[1].content)
        self.assertIn('候选不必出现在原句中', messages[0].content)
        self.assertIn('没有可信候选就询问', messages[0].content)

    def test_cross_day_history_order_and_isolation(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(service, 'CHAT_HISTORY_DIR', Path(directory)):
            now = datetime.now()
            def record(question, when, user='u', article='a'):
                return dict(question=question, created_at=when.isoformat(), user=user, article_id=article, focus='transition')
            yesterday = now - timedelta(days=1)
            service.write_json(str(Path(directory) / f'{yesterday:%Y-%m-%d}.json'), [record('old', yesterday)])
            service.write_json(str(Path(directory) / f'{now:%Y-%m-%d}.json'), [record('new', now), record('private', now, 'other'), record('unrelated', now, article='b')])
            history = service._load_recent_history('a', 'u', 2)
            self.assertLess(history.index('old'), history.index('new'))
            self.assertNotIn('private', history)
            self.assertNotIn('unrelated', history)
            self.assertNotIn('old', service._load_recent_history('a', 'u', 1))
            self.assertEqual(service._load_recent_history('a', 'u', 0), '')

    def test_history_saved_before_done(self):
        class FakeLLM:
            async def astream(self, messages):
                yield SimpleNamespace(content='你是不是想到 transient？')

        async def run():
            with tempfile.TemporaryDirectory() as directory, patch.object(service, 'CHAT_HISTORY_DIR', Path(directory)), patch.object(service, 'ChatOpenAI', return_value=FakeLLM()), patch.object(service, '_load_article_context', return_value=''):
                async for event in service.stream_agent_response('那短暂呢', 'sentence', 'a', '', 'u', 'transition'):
                    if '[DONE]' in event:
                        records = service.read_json(str(Path(directory) / f'{datetime.now():%Y-%m-%d}.json'), [])
                        self.assertEqual(records[-1]['discussion_topic'], 'transition')
                        self.assertEqual(records[-1]['intent'], 'followup')
                        return
                self.fail('No completion event')
        asyncio.run(run())


if __name__ == '__main__':
    unittest.main()
