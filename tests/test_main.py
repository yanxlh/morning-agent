import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_morning_review_job_sends_both_notifications(monkeypatch):
    monkeypatch.setenv("ZHIPUAI_API_KEY", "fake_key")
    fake_msg = MagicMock()
    fake_msg.content = "今天安排：上午写文档，下午开会。"
    fake_result = {"messages": [fake_msg]}

    # patch main 模块命名空间（因为 main.py 用 from ... import 引入）
    with patch("main.agent") as mock_agent, \
         patch("main.send_email", new_callable=AsyncMock) as mock_email, \
         patch("main.send_wechat_message", new_callable=AsyncMock) as mock_wx:

        mock_agent.ainvoke = AsyncMock(return_value=fake_result)

        from main import morning_review_job
        await morning_review_job()

        mock_agent.ainvoke.assert_called_once()
        mock_email.assert_called_once_with("今天安排：上午写文档，下午开会。")
        mock_wx.assert_called_once_with("今天安排：上午写文档，下午开会。")


def test_trigger_review_http_endpoint(monkeypatch):
    monkeypatch.setenv("ZHIPUAI_API_KEY", "fake_key")
    # mock scheduler 避免 APScheduler 在测试中实际启动
    with patch("main.morning_review_job", new_callable=AsyncMock) as mock_job, \
         patch("main.scheduler") as mock_scheduler:

        from main import app
        with TestClient(app) as client:
            response = client.post("/trigger-review")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        mock_job.assert_called_once()
