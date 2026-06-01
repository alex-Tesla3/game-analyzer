"""Support chatbot keyword and LLM helper tests."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from support import AIChatbot


def test_capability_question_not_default_template():
    bot = AIChatbot()
    bot.load_knowledge_base()
    reply = bot.generate_response("你可以做什么", [])
    assert "数据看板" in reply
    assert "工单系统提交详细信息" not in reply
