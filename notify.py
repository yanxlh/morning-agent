import os
from email.mime.text import MIMEText
import aiosmtplib
import httpx


async def send_email(content: str) -> None:
    gmail = os.environ["GMAIL_ADDRESS"]
    msg = MIMEText(content, "plain", "utf-8")
    msg["Subject"] = "今日计划提醒"
    msg["From"] = gmail
    msg["To"] = gmail

    await aiosmtplib.send(
        msg,
        hostname="smtp.gmail.com",
        port=587,
        username=gmail,
        password=os.environ["SMTP_PASSWORD"],
        start_tls=True,
    )


async def send_wechat_message(content: str) -> None:
    key = os.environ["SERVERCHAN_KEY"]
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://sctapi.ftqq.com/{key}.send",
            data={"title": "今日计划提醒", "desp": content},
        )
