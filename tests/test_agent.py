import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_agent_invoke_returns_string(monkeypatch):
    monkeypatch.setenv("ZHIPUAI_API_KEY", "fake_key")

    from agent import SYSTEM_PROMPT
    assert "固定日程" in SYSTEM_PROMPT
    assert "250字" in SYSTEM_PROMPT
    assert "Markdown" in SYSTEM_PROMPT


def test_agent_module_exports_agent(monkeypatch):
    monkeypatch.setenv("ZHIPUAI_API_KEY", "fake_key")

    import agent as agent_module
    assert hasattr(agent_module, "agent")
    assert hasattr(agent_module, "SYSTEM_PROMPT")
