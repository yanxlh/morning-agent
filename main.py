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
from config import get_config, save_config
from reminder import reschedule_reminders, sse_generator


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

    try:
        cfg = get_config()
        reschedule_reminders(
            _date.today().isoformat(),
            scheduler,
            cfg["advance_minutes"],
            schedule_dir=_DEFAULT_SCHEDULE_DIR,
        )
    except Exception as e:
        print(f"提醒调度失败: {e}")


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


# ── 设置与提醒端点 ────────────────────────────────────────────


@app.get("/api/settings")
async def get_settings():
    return get_config()


class _SettingsUpdate(BaseModel):
    advance_minutes: int


@app.post("/api/settings")
async def update_settings(body: _SettingsUpdate):
    if body.advance_minutes < 0:
        raise HTTPException(status_code=400, detail="advance_minutes must be >= 0")
    save_config({"advance_minutes": body.advance_minutes})
    reschedule_reminders(
        _date.today().isoformat(),
        scheduler,
        body.advance_minutes,
        schedule_dir=_DEFAULT_SCHEDULE_DIR,
    )
    return get_config()


@app.get("/api/events")
async def sse_endpoint():
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/reminders/reschedule")
async def reschedule_today():
    cfg = get_config()
    count = reschedule_reminders(
        _date.today().isoformat(),
        scheduler,
        cfg["advance_minutes"],
        schedule_dir=_DEFAULT_SCHEDULE_DIR,
    )
    return {"scheduled": count}


def _direct_assign_flexible_times(date_str: str, schedule_dir=None) -> int:
    """
    Algorithmically assign time slots to untimed flexible tasks.
    Reads fixed-schedule time ranges, finds free gaps, and writes HH:MM-HH:MM
    prefixes back to the file. Returns the number of tasks updated.
    """
    import re as _re

    sched_dir = Path(schedule_dir) if schedule_dir else _DEFAULT_SCHEDULE_DIR
    filepath = sched_dir / f"{date_str}.md"
    if not filepath.exists():
        return 0

    TIME_RE = _re.compile(r"^(\d{2}:\d{2})-(\d{2}:\d{2})\s+")
    lines = filepath.read_text(encoding="utf-8").splitlines(keepends=True)

    # Collect occupied intervals from fixed-schedule tasks that have times
    occupied: list[tuple[int, int]] = []
    in_fixed = False
    for line in lines:
        s = line.rstrip("\n")
        if s.startswith("## "):
            in_fixed = s[3:].strip() == "固定日程"
            continue
        if not in_fixed or not line.startswith("- "):
            continue
        raw = line[2:].strip()
        text = raw[4:] if raw[:4] in ("[ ] ", "[x] ") else raw
        m = TIME_RE.match(text)
        if m:
            sh, sm = map(int, m.group(1).split(":"))
            eh, em = map(int, m.group(2).split(":"))
            occupied.append((sh * 60 + sm, eh * 60 + em))

    occupied.sort()

    # Collect untimed flexible task lines
    flex_lines: list[tuple[int, str, str]] = []   # (line_idx, text, orig_raw)
    in_flex = False
    for i, line in enumerate(lines):
        s = line.rstrip("\n")
        if s.startswith("## "):
            in_flex = s[3:].strip() == "灵活待办"
            continue
        if not in_flex or not line.startswith("- "):
            continue
        raw = line[2:].strip()
        if raw[:4] in ("[ ] ", "[x] "):
            text = raw[4:]
        elif raw and raw != "-":
            text = raw
        else:
            continue
        if not TIME_RE.match(text):
            flex_lines.append((i, text, raw))

    if not flex_lines:
        return 0

    # Build free slots within working hours (09:00–22:00)
    DAY_START, DAY_END, TASK_DUR, GAP = 9 * 60, 22 * 60, 90, 15
    blocked = sorted(
        (max(s, DAY_START), min(e, DAY_END))
        for s, e in occupied if s < DAY_END and e > DAY_START
    )
    free: list[tuple[int, int]] = []
    cursor = DAY_START
    for s, e in blocked:
        if s > cursor:
            free.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < DAY_END:
        free.append((cursor, DAY_END))

    if not free:
        free = [(DAY_START, DAY_END)]

    slot_i, slot_cursor = 0, free[0][0]
    updated = 0

    for line_i, text, orig_raw in flex_lines:
        # Advance to a slot with enough room
        while slot_i < len(free) and free[slot_i][1] - slot_cursor < TASK_DUR:
            slot_i += 1
            if slot_i < len(free):
                slot_cursor = free[slot_i][0]
        if slot_i >= len(free):
            break

        s_str = f"{slot_cursor // 60:02d}:{slot_cursor % 60:02d}"
        e_str = f"{(slot_cursor + TASK_DUR) // 60:02d}:{(slot_cursor + TASK_DUR) % 60:02d}"
        marker = "[x] " if orig_raw.startswith("[x] ") else "[ ] "
        lines[line_i] = f"- {marker}{s_str}-{e_str} {text}\n"
        slot_cursor += TASK_DUR + GAP
        updated += 1

    if updated:
        filepath.write_text("".join(lines), encoding="utf-8")
    return updated


@app.post("/api/schedule/{date_str}/assign-times")
async def assign_schedule_times(date_str: str):
    if date_str != _date.today().isoformat():
        raise HTTPException(status_code=400, detail="Can only assign times for today")
    try:
        count = _direct_assign_flexible_times(date_str, schedule_dir=_DEFAULT_SCHEDULE_DIR)
        print(f"assign_schedule_times: 分配了 {count} 个任务")
    except Exception as e:
        print(f"assign_schedule_times 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    return parse_schedule(date_str, schedule_dir=_DEFAULT_SCHEDULE_DIR)
