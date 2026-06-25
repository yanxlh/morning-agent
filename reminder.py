import asyncio
import json
import re
from datetime import date as _date_type, datetime, timedelta, time as _time_type
from pathlib import Path
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from notify import send_wechat_message
from tools import SCHEDULE_DIR

_TIME_RE = re.compile(r"^\s*(\d{2}:\d{2})-(\d{2}:\d{2})\s+(.+)")

_sse_clients: list[asyncio.Queue] = []


def parse_task_times(
    date_str: str, schedule_dir: Optional[Path] = None
) -> list[dict]:
    """返回含时间前缀的任务列表，每项 {start_time, task_text, section}。"""
    directory = schedule_dir if schedule_dir is not None else SCHEDULE_DIR
    filepath = directory / f"{date_str}.md"
    if not filepath.exists():
        return []

    results = []
    current_section: Optional[str] = None
    for line in filepath.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current_section = line[3:].strip()
        elif line.startswith("- ") and current_section is not None:
            raw = line[2:].strip()
            if raw.startswith("[ ] ") or raw.startswith("[x] "):
                raw = raw[4:]
            m = _TIME_RE.match(raw)
            if m:
                results.append({
                    "start_time": m.group(1),
                    "task_text": m.group(3).strip(),
                    "section": current_section,
                })
    return results


async def sse_generator():
    """Async generator for Server-Sent Events. Yields formatted SSE data lines."""
    q: asyncio.Queue = asyncio.Queue()
    _sse_clients.append(q)
    try:
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=30)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"
    finally:
        _sse_clients.remove(q)


async def push_reminder_event(event: dict) -> None:
    for q in list(_sse_clients):
        await q.put(event)


def reschedule_reminders(
    date_str: str,
    scheduler: AsyncIOScheduler,
    advance_minutes: int,
    schedule_dir: Optional[Path] = None,
) -> int:
    """取消当天旧提醒 job，按文件重新调度。返回调度 job 数量。"""
    prefix = f"reminder_{date_str}_"
    for job in scheduler.get_jobs():
        if job.id.startswith(prefix):
            job.remove()

    tasks = parse_task_times(date_str, schedule_dir)
    now = datetime.now()
    count = 0

    for i, task in enumerate(tasks):
        h, m = map(int, task["start_time"].split(":"))
        start_dt = datetime.combine(
            _date_type.fromisoformat(date_str),
            _time_type(h, m, 0),
        )
        early_dt = start_dt - timedelta(minutes=advance_minutes)

        if early_dt > now:
            scheduler.add_job(
                _reminder_job,
                "date",
                run_date=early_dt,
                id=f"{prefix}{i}_early",
                args=[task["task_text"], task["start_time"], True, advance_minutes],
                replace_existing=True,
            )
            count += 1

        if start_dt > now:
            scheduler.add_job(
                _reminder_job,
                "date",
                run_date=start_dt,
                id=f"{prefix}{i}_ontime",
                args=[task["task_text"], task["start_time"], False, advance_minutes],
                replace_existing=True,
            )
            count += 1

    return count


async def _reminder_job(
    task_text: str,
    time_str: str,
    is_early: bool,
    advance_minutes: int,
) -> None:
    if is_early:
        msg = f"⏰ 提醒：{task_text} 将于 {time_str} 开始（还有 {advance_minutes} 分钟）"
    else:
        msg = f"🔔 {task_text} 开始了（{time_str}）"
    try:
        await send_wechat_message(msg)
    except Exception as e:
        print(f"提醒微信推送失败: {e}")
    await push_reminder_event({
        "type": "reminder",
        "task": task_text,
        "time": time_str,
        "early": is_early,
        "advance_minutes": advance_minutes,
    })
