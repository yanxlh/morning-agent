import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.events import EVENT_JOB_ERROR

from agent import agent
from notify import send_email, send_wechat_message

scheduler = AsyncIOScheduler()


async def morning_review_job() -> None:
    try:
        result = await agent.ainvoke({
            "messages": [{"role": "user", "content": "帮我安排一下今天的日程，并生成明天的模板"}]
        })
        advice_text = result["messages"][-1].content

        results = await asyncio.gather(
            send_email(advice_text),
            send_wechat_message(advice_text),
            return_exceptions=True,
        )
        names = ["邮件", "Server酱"]
        for name, res in zip(names, results):
            if isinstance(res, Exception):
                print(f"{name}推送失败: {res}")

    except Exception as e:
        print(f"morning_review_job 执行失败: {e}")


def job_error_listener(event):
    print(f"定时任务异常: {event.exception}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(morning_review_job, "cron", hour=7, minute=0, id="morning_review")
    scheduler.add_listener(job_error_listener, EVENT_JOB_ERROR)
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)


@app.post("/trigger-review")
async def trigger_review_manually():
    """手动触发一次日程规划，方便调试"""
    await morning_review_job()
    return {"status": "ok"}
