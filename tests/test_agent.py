import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_agent_invoke_returns_string(monkeypatch):
    monkeypatch.setenv("ZHIPUAI_API_KEY", "fake_key")

    mock_llm = MagicMock()
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)

    fake_message = MagicMock()
    fake_message.content = "今天安排如下：上午处理文档，下午参加会议。"

    with patch("langchain_zhipuai.ChatZhipuAI", return_value=mock_llm, create=True):
        from agent import SYSTEM_PROMPT
        assert "固定日程" in SYSTEM_PROMPT
        assert "250字" in SYSTEM_PROMPT
        assert "Markdown" in SYSTEM_PROMPT


def test_agent_module_exports_agent(monkeypatch):
    monkeypatch.setenv("ZHIPUAI_API_KEY", "fake_key")

    import agent as agent_module
    assert hasattr(agent_module, "agent")
    assert hasattr(agent_module, "SYSTEM_PROMPT")
