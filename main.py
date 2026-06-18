import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import date as _date
from typing import Optional

from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.events import EVENT_JOB_ERROR

from agent import agent
from notify import send_email, send_wechat_message
from tools import SCHEDULE_DIR as _DEFAULT_SCHEDULE_DIR


def parse_today(schedule_dir: Optional[Path] = None) -> dict:
    directory = schedule_dir if schedule_dir is not None else _DEFAULT_SCHEDULE_DIR
    today = _date.today().isoformat()
    filepath = directory / f"{today}.md"

    if not filepath.exists():
        return {"date": today, "sections": [], "total": 0, "done_count": 0}

    content = filepath.read_text(encoding="utf-8")
    sections: list = []
    current_section: Optional[dict] = None

    for line in content.splitlines():
        if line.startswith("## "):
            current_section = {"name": line[3:].strip(), "tasks": []}
            sections.append(current_section)
        elif line.startswith("- ") and current_section is not None:
            raw = line[2:].strip()
            if not raw or raw in ("-",):
                continue
            if raw.startswith("[x] "):
                done, text = True, raw[4:]
            elif raw.startswith("[ ] "):
                done, text = False, raw[4:]
            else:
                done, text = False, raw
            si = len(sections) - 1
            ti = len(current_section["tasks"])
            current_section["tasks"].append({"id": f"s{si}-t{ti}", "text": text, "done": done})

    total = sum(len(s["tasks"]) for s in sections)
    done_count = sum(t["done"] for s in sections for t in s["tasks"])
    return {"date": today, "sections": sections, "total": total, "done_count": done_count}

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
