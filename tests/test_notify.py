import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_send_email_calls_smtp(monkeypatch):
    monkeypatch.setenv("GMAIL_ADDRESS", "test@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "test_password")

    with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        from notify import send_email
        await send_email("今天排期建议")

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        assert call_kwargs.kwargs["hostname"] == "smtp.gmail.com"
        assert call_kwargs.kwargs["port"] == 587
        assert call_kwargs.kwargs["username"] == "test@gmail.com"
        assert call_kwargs.kwargs["password"] == "test_password"
        assert call_kwargs.kwargs["start_tls"] is True
        msg = call_kwargs.args[0]
        assert msg["Subject"] == "今日计划提醒"
        assert msg["From"] == "test@gmail.com"
        assert msg["To"] == "test@gmail.com"


@pytest.mark.asyncio
async def test_send_wechat_message_calls_serverchan(monkeypatch):
    monkeypatch.setenv("SERVERCHAN_KEY", "test_key_123")

    mock_response = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        from notify import send_wechat_message
        await send_wechat_message("今天排期建议")

        mock_client.post.assert_called_once_with(
            "https://sctapi.ftqq.com/test_key_123.send",
            data={"title": "今日计划提醒", "desp": "今天排期建议"},
        )
