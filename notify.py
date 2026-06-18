import os
import httpx


async def send_email(content: str) -> None:
    # Email notification function
    # TODO: Implement email sending logic
    pass


async def send_wechat_message(content: str) -> None:
    key = os.environ["SERVERCHAN_KEY"]
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://sctapi.ftqq.com/{key}.send",
            data={"title": "今日计划提醒", "desp": content},
        )
