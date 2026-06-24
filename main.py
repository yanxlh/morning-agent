import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import date as _date
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.events import EVENT_JOB_ERROR

from agent import agent
from notify import send_email, send_wechat_message
from tools import (
    SCHEDULE_DIR as _DEFAULT_SCHEDULE_DIR,
    create_schedule,
    append_task,
    delete_task,
    update_task_text,
)


def parse_schedule(date_str: str, schedule_dir: Optional[Path] = None) -> dict:
    directory = schedule_dir if schedule_dir is not None else _DEFAULT_SCHEDULE_DIR
    filepath = directory / f"{date_str}.md"

    if not filepath.exists():
        return {"date": date_str, "sections": [], "total": 0, "done_count": 0}

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
    return {"date": date_str, "sections": sections, "total": total, "done_count": done_count}


def parse_today(schedule_dir: Optional[Path] = None) -> dict:
    return parse_schedule(_date.today().isoformat(), schedule_dir=schedule_dir)


def write_task_done(
    task_id: str,
    done: bool,
    date_str: Optional[str] = None,
    schedule_dir: Optional[Path] = None,
) -> dict:
    directory = schedule_dir if schedule_dir is not None else _DEFAULT_SCHEDULE_DIR
    resolved_date = date_str if date_str is not None else _date.today().isoformat()
    filepath = directory / f"{resolved_date}.md"

    if not filepath.exists():
        return parse_schedule(resolved_date, schedule_dir=directory)

    try:
        parts = task_id.split("-")
        target_si, target_ti = int(parts[0][1:]), int(parts[1][1:])
    except (IndexError, ValueError):
        raise HTTPException(status_code=400, detail="invalid task_id format")

    lines = filepath.read_text(encoding="utf-8").splitlines(keepends=True)
    current_si, current_ti = -1, -1
    found = False

    for i, line in enumerate(lines):
        if line.startswith("## "):
            current_si += 1
            current_ti = -1
        elif line.startswith("- ") and current_si >= 0:
            raw = line[2:].strip()
            if not raw or raw == "-":
                continue
            current_ti += 1
            if current_si == target_si and current_ti == target_ti:
                if raw.startswith("[x] ") or raw.startswith("[ ] "):
                    text = raw[4:]
                else:
                    text = raw
                marker = "[x]" if done else "[ ]"
                lines[i] = f"- {marker} {text}\n"
                found = True
                break

    if not found:
        raise HTTPException(status_code=404, detail="task not found")

    filepath.write_text("".join(lines), encoding="utf-8")
    return parse_schedule(resolved_date, schedule_dir=directory)


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
    asyncio.create_task(morning_review_job())
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)

_BASE_DIR = Path(__file__).parent


@app.get("/")
async def index():
    return FileResponse(_BASE_DIR / "static" / "index.html")


@app.get("/api/today")
async def get_today():
    return parse_today()


class _TaskUpdate(BaseModel):
    done: bool


@app.patch("/api/task/{task_id}")
async def update_task_legacy(task_id: str, body: _TaskUpdate):
    return write_task_done(task_id, body.done)


@app.post("/trigger-review")
async def trigger_review_manually():
    await morning_review_job()
    return {"status": "ok"}


# ── 新增端点 ──────────────────────────────────────────────────────

@app.get("/api/schedule/{date_str}")
async def get_schedule(date_str: str):
    return parse_schedule(date_str, schedule_dir=_DEFAULT_SCHEDULE_DIR)


@app.post("/api/schedule/{date_str}")
async def create_day(date_str: str):
    create_schedule(date_str, schedule_dir=_DEFAULT_SCHEDULE_DIR)
    return parse_schedule(date_str, schedule_dir=_DEFAULT_SCHEDULE_DIR)


class _TaskCreate(BaseModel):
    section: str
    text: str


@app.post("/api/schedule/{date_str}/task")
async def add_task(date_str: str, body: _TaskCreate):
    try:
        append_task(date_str, body.section, body.text, schedule_dir=_DEFAULT_SCHEDULE_DIR)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="schedule file not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return parse_schedule(date_str, schedule_dir=_DEFAULT_SCHEDULE_DIR)


class _TaskEdit(BaseModel):
    done: Optional[bool] = None
    text: Optional[str] = None


@app.patch("/api/schedule/{date_str}/task/{task_id}")
async def update_task(date_str: str, task_id: str, body: _TaskEdit):
    if body.done is not None:
        return write_task_done(task_id, body.done, date_str=date_str, schedule_dir=_DEFAULT_SCHEDULE_DIR)
    if body.text is not None:
        try:
            update_task_text(date_str, task_id, body.text, schedule_dir=_DEFAULT_SCHEDULE_DIR)
        except (FileNotFoundError, LookupError) as e:
            raise HTTPException(status_code=404, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return parse_schedule(date_str, schedule_dir=_DEFAULT_SCHEDULE_DIR)
    raise HTTPException(status_code=400, detail="must provide done or text")


@app.delete("/api/schedule/{date_str}/task/{task_id}")
async def remove_task(date_str: str, task_id: str):
    try:
        delete_task(date_str, task_id, schedule_dir=_DEFAULT_SCHEDULE_DIR)
    except (FileNotFoundError, LookupError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return parse_schedule(date_str, schedule_dir=_DEFAULT_SCHEDULE_DIR)
