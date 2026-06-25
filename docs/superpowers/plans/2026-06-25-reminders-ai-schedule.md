# 时间提醒 + AI 自动安排灵活任务 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让系统在 7 点运行时用 AI 自动给灵活待办分配时间槽写回文件，并在任务开始前后通过微信和浏览器 Notification API 双渠道推送提醒，提前提醒分钟数可在网页设置。

**Architecture:** 新建 `config.py`（读写 `config.json`）和 `reminder.py`（时间解析 + APScheduler 提醒调度 + SSE 事件队列）；`tools.py` 新增 `assign_flexible_times` LangChain 工具写回时间前缀；`main.py` 在晨间任务结束后调用 `reschedule_reminders` 并暴露 4 个新 API；前端新增设置面板和 SSE 客户端。

**Tech Stack:** FastAPI, APScheduler (AsyncIOScheduler), LangChain `@tool`, Server-Sent Events, Browser Notification API, pytest + pytest-asyncio

## Global Constraints

- Python 文件编码全部 `encoding="utf-8"`
- `schedule_dir: Optional[Path] = None` 可注入，不传时用模块级变量（可测试性）
- 所有 `_sse_clients` 操作发生在同一 asyncio event loop（单进程）
- 灵活待办任务行正则：`^\s*(\d{2}:\d{2})-(\d{2}:\d{2})\s+(.+)`——固定日程和灵活待办共用
- SSE 事件格式：`{"type": "reminder", "task": str, "time": str, "early": bool, "advance_minutes": int}`
- `config.json` 在项目根目录，字段 `advance_minutes`（int），缺省 15
- Job ID 格式：`reminder_{date_str}_{index}_{early|ontime}`（e.g. `reminder_2026-06-25_0_early`）
- `assign_flexible_times` 的 `index` 是"灵活待办" section 中任务的 0-based 序号
- 已有 `HH:MM-HH:MM` 前缀的任务不覆盖
- `reschedule_reminders` 只调度未来的 job（`run_date > datetime.now()`）
- 不修改已有端点和测试（向后兼容）

---

## File Map

| 操作 | 文件 | 内容 |
|------|------|------|
| 新建 | `config.py` | `get_config() -> dict`, `save_config(data: dict)` |
| 新建 | `reminder.py` | `parse_task_times`, `sse_generator`, `push_reminder_event`, `reschedule_reminders`, `_reminder_job` |
| 新建 | `tests/test_config.py` | config 单元测试 |
| 新建 | `tests/test_reminder.py` | reminder 单元测试 |
| 修改 | `tools.py` | 新增 `assign_flexible_times` tool |
| 修改 | `agent.py` | 注册新工具，更新 SYSTEM_PROMPT |
| 修改 | `tests/test_tools.py` | 新增 assign_flexible_times 测试 |
| 修改 | `main.py` | 新增 4 端点，更新 `morning_review_job` |
| 修改 | `tests/test_web.py` | 新增 4 端点测试 |
| 修改 | `static/index.html` | 设置面板 + SSE 客户端 + Notification API |

---

## Task 1: config.py — 读写配置文件

**Files:**
- Create: `config.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `get_config() -> dict` — 返回 `{"advance_minutes": int}`，文件不存在或损坏时返回默认值
  - `save_config(data: dict) -> None` — 合并更新并写入 `config.json`

- [ ] **Step 1: 写失败测试**

新建 `tests/test_config.py`：

```python
import pytest
from pathlib import Path


def test_get_config_returns_defaults_when_no_file(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "_CONFIG_PATH", tmp_path / "config.json")
    assert config.get_config() == {"advance_minutes": 15}


def test_save_and_get_config(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "_CONFIG_PATH", tmp_path / "config.json")
    config.save_config({"advance_minutes": 30})
    assert config.get_config()["advance_minutes"] == 30


def test_get_config_handles_corrupt_file(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "_CONFIG_PATH", tmp_path / "config.json")
    (tmp_path / "config.json").write_text("not json", encoding="utf-8")
    assert config.get_config() == {"advance_minutes": 15}


def test_save_config_merges_with_existing(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "_CONFIG_PATH", tmp_path / "config.json")
    (tmp_path / "config.json").write_text(
        '{"advance_minutes": 5, "other": "val"}', encoding="utf-8"
    )
    config.save_config({"advance_minutes": 20})
    assert config.get_config()["advance_minutes"] == 20
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd /Users/yxlh/Documents/morning-agent
pytest tests/test_config.py -v
```

期望：`ModuleNotFoundError: No module named 'config'`

- [ ] **Step 3: 实现 `config.py`**

新建 `config.py`（项目根目录）：

```python
import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent / "config.json"
_DEFAULTS: dict = {"advance_minutes": 15}


def get_config() -> dict:
    if not _CONFIG_PATH.exists():
        return dict(_DEFAULTS)
    try:
        data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        return {**_DEFAULTS, **data}
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULTS)


def save_config(data: dict) -> None:
    current = get_config()
    current.update(data)
    _CONFIG_PATH.write_text(
        json.dumps(current, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_config.py -v
```

期望：4 个测试全部 PASS

- [ ] **Step 5: 提交**

```bash
git add config.py tests/test_config.py
git commit -m "feat: add config.py for advance_minutes persistence"
```

---

## Task 2: reminder.py — 时间解析 + SSE + 提醒调度

**Files:**
- Create: `reminder.py`
- Create: `tests/test_reminder.py`

**Interfaces:**
- Consumes:
  - `from notify import send_wechat_message` — `async def send_wechat_message(content: str) -> None`
  - `from tools import SCHEDULE_DIR` — `Path` 对象
- Produces:
  - `parse_task_times(date_str: str, schedule_dir: Optional[Path] = None) -> list[dict]`
    — 每项 `{"start_time": "HH:MM", "task_text": str, "section": str}`
  - `sse_generator() -> AsyncGenerator[str, None]`
  - `push_reminder_event(event: dict) -> None` （async）
  - `reschedule_reminders(date_str: str, scheduler: AsyncIOScheduler, advance_minutes: int, schedule_dir: Optional[Path] = None) -> int`

- [ ] **Step 1: 写失败测试**

新建 `tests/test_reminder.py`：

```python
import pytest
from pathlib import Path
from datetime import date as _date_type


def test_parse_task_times_fixed_schedule(tmp_path):
    from reminder import parse_task_times
    (tmp_path / "2026-06-25.md").write_text(
        "## 固定日程\n- [ ] 14:00-15:30 健身\n## 灵活待办\n- [ ] 学习rust\n",
        encoding="utf-8",
    )
    result = parse_task_times("2026-06-25", schedule_dir=tmp_path)
    assert len(result) == 1
    assert result[0]["start_time"] == "14:00"
    assert result[0]["task_text"] == "健身"
    assert result[0]["section"] == "固定日程"


def test_parse_task_times_flexible_with_time(tmp_path):
    from reminder import parse_task_times
    (tmp_path / "2026-06-25.md").write_text(
        "## 灵活待办\n- [ ] 09:00-10:00 剪视频（预计1h）\n",
        encoding="utf-8",
    )
    result = parse_task_times("2026-06-25", schedule_dir=tmp_path)
    assert len(result) == 1
    assert result[0]["start_time"] == "09:00"
    assert "剪视频" in result[0]["task_text"]


def test_parse_task_times_skips_no_time(tmp_path):
    from reminder import parse_task_times
    (tmp_path / "2026-06-25.md").write_text(
        "## 灵活待办\n- [ ] 学习rust\n- [ ] 14:00-15:00 健身\n",
        encoding="utf-8",
    )
    result = parse_task_times("2026-06-25", schedule_dir=tmp_path)
    assert len(result) == 1
    assert result[0]["task_text"] == "健身"


def test_parse_task_times_no_file(tmp_path):
    from reminder import parse_task_times
    result = parse_task_times("2099-01-01", schedule_dir=tmp_path)
    assert result == []


@pytest.mark.asyncio
async def test_push_reminder_event_delivers_to_client():
    import asyncio
    from reminder import push_reminder_event, _sse_clients

    q: asyncio.Queue = asyncio.Queue()
    _sse_clients.append(q)
    try:
        event = {
            "type": "reminder", "task": "健身", "time": "19:00",
            "early": False, "advance_minutes": 15,
        }
        await push_reminder_event(event)
        received = await asyncio.wait_for(q.get(), timeout=1.0)
        assert received == event
    finally:
        _sse_clients.remove(q)


def test_reschedule_reminders_schedules_future_jobs(tmp_path):
    from unittest.mock import MagicMock
    from reminder import reschedule_reminders

    # 2099 年的时间必然在 now 之后
    (tmp_path / "2099-12-31.md").write_text(
        "## 固定日程\n- [ ] 23:50-23:59 深夜任务\n",
        encoding="utf-8",
    )
    mock_scheduler = MagicMock()
    mock_scheduler.get_jobs.return_value = []

    count = reschedule_reminders("2099-12-31", mock_scheduler, 5, schedule_dir=tmp_path)

    assert count == 2  # early (23:45) + ontime (23:50)
    assert mock_scheduler.add_job.call_count == 2


def test_reschedule_reminders_removes_old_jobs(tmp_path):
    from unittest.mock import MagicMock
    from reminder import reschedule_reminders

    (tmp_path / "2026-06-25.md").write_text("## 固定日程\n", encoding="utf-8")
    old_job = MagicMock()
    old_job.id = "reminder_2026-06-25_0_early"
    unrelated_job = MagicMock()
    unrelated_job.id = "morning_review"
    mock_scheduler = MagicMock()
    mock_scheduler.get_jobs.return_value = [old_job, unrelated_job]

    reschedule_reminders("2026-06-25", mock_scheduler, 15, schedule_dir=tmp_path)

    old_job.remove.assert_called_once()
    unrelated_job.remove.assert_not_called()


def test_reschedule_reminders_skips_past_jobs(tmp_path):
    from unittest.mock import MagicMock
    from reminder import reschedule_reminders

    # 2020 年的时间已经在 now 之前
    (tmp_path / "2020-01-01.md").write_text(
        "## 固定日程\n- [ ] 09:00-10:00 早已过去的任务\n",
        encoding="utf-8",
    )
    mock_scheduler = MagicMock()
    mock_scheduler.get_jobs.return_value = []

    count = reschedule_reminders("2020-01-01", mock_scheduler, 15, schedule_dir=tmp_path)

    assert count == 0
    mock_scheduler.add_job.assert_not_called()
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_reminder.py -v
```

期望：`ModuleNotFoundError: No module named 'reminder'`

- [ ] **Step 3: 实现 `reminder.py`**

新建 `reminder.py`（项目根目录）：

```python
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
    """Server-Sent Events 异步生成器，每个连接独立队列。"""
    q: asyncio.Queue = asyncio.Queue()
    _sse_clients.append(q)
    try:
        while True:
            event = await q.get()
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    finally:
        _sse_clients.remove(q)


async def push_reminder_event(event: dict) -> None:
    for q in _sse_clients:
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
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_reminder.py -v
```

期望：8 个测试全部 PASS

- [ ] **Step 5: 提交**

```bash
git add reminder.py tests/test_reminder.py
git commit -m "feat: add reminder.py with time parsing, SSE queue, and reminder scheduling"
```

---

## Task 3: tools.py + agent.py — assign_flexible_times 工具

**Files:**
- Modify: `tools.py` （在文件末尾追加新 tool）
- Modify: `agent.py` （注册工具，更新 SYSTEM_PROMPT）
- Modify: `tests/test_tools.py` （追加测试）

**Interfaces:**
- Consumes: `SCHEDULE_DIR: Path`（来自 `tools.py` 模块级变量，测试用 `monkeypatch.setattr` 注入）
- Produces:
  - `assign_flexible_times` — LangChain tool，签名 `assign_flexible_times(assignments_json: str) -> str`

**注意：** `tests/test_tools.py` 可能已存在，追加测试不删除已有内容。

- [ ] **Step 1: 写失败测试**

在 `tests/test_tools.py` 末尾追加（如文件不存在则新建）：

```python
from datetime import date as _date


def test_assign_flexible_times_adds_time_prefix(tmp_path, monkeypatch):
    import tools
    monkeypatch.setattr(tools, "SCHEDULE_DIR", tmp_path)
    today = _date.today().isoformat()
    (tmp_path / f"{today}.md").write_text(
        "## 固定日程\n- [ ] 14:00-15:00 健身\n\n## 灵活待办\n- [ ] 剪视频\n- [ ] 学习rust\n",
        encoding="utf-8",
    )
    result = tools.assign_flexible_times.invoke(
        {"assignments_json": '[{"index": 0, "start": "09:00", "end": "10:00"}]'}
    )
    content = (tmp_path / f"{today}.md").read_text(encoding="utf-8")
    assert "09:00-10:00 剪视频" in content
    assert "学习rust" in content  # index 1，未分配，不变
    assert "已为 1" in result


def test_assign_flexible_times_skips_existing_time(tmp_path, monkeypatch):
    import tools
    monkeypatch.setattr(tools, "SCHEDULE_DIR", tmp_path)
    today = _date.today().isoformat()
    (tmp_path / f"{today}.md").write_text(
        "## 灵活待办\n- [ ] 09:00-10:00 剪视频\n",
        encoding="utf-8",
    )
    result = tools.assign_flexible_times.invoke(
        {"assignments_json": '[{"index": 0, "start": "11:00", "end": "12:00"}]'}
    )
    content = (tmp_path / f"{today}.md").read_text(encoding="utf-8")
    assert "09:00-10:00 剪视频" in content  # 未被覆盖
    assert "11:00" not in content
    assert "已为 0" in result


def test_assign_flexible_times_invalid_json(tmp_path, monkeypatch):
    import tools
    monkeypatch.setattr(tools, "SCHEDULE_DIR", tmp_path)
    today = _date.today().isoformat()
    (tmp_path / f"{today}.md").write_text("## 灵活待办\n- [ ] 任务\n", encoding="utf-8")
    result = tools.assign_flexible_times.invoke({"assignments_json": "not json"})
    assert "JSON 解析失败" in result


def test_assign_flexible_times_out_of_bounds(tmp_path, monkeypatch):
    import tools
    monkeypatch.setattr(tools, "SCHEDULE_DIR", tmp_path)
    today = _date.today().isoformat()
    (tmp_path / f"{today}.md").write_text("## 灵活待办\n- [ ] 任务\n", encoding="utf-8")
    result = tools.assign_flexible_times.invoke(
        {"assignments_json": '[{"index": 99, "start": "09:00", "end": "10:00"}]'}
    )
    assert "已为 0" in result


def test_assign_flexible_times_no_file(tmp_path, monkeypatch):
    import tools
    monkeypatch.setattr(tools, "SCHEDULE_DIR", tmp_path)
    result = tools.assign_flexible_times.invoke(
        {"assignments_json": '[{"index": 0, "start": "09:00", "end": "10:00"}]'}
    )
    assert "日程文件不存在" in result
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_tools.py::test_assign_flexible_times_adds_time_prefix -v
```

期望：`AttributeError: module 'tools' has no attribute 'assign_flexible_times'`

- [ ] **Step 3: 在 `tools.py` 末尾追加工具**

在 `tools.py` 文件末尾追加：

```python

@tool
def assign_flexible_times(assignments_json: str) -> str:
    """
    为今天灵活待办中的任务分配时间段，写回日程文件。
    assignments_json: JSON 数组，格式为
    '[{"index": 0, "start": "09:00", "end": "10:00"}, ...]'
    index 是灵活待办 section 中任务的序号（从0开始）。
    已有时间前缀（HH:MM-HH:MM）的任务不覆盖。
    返回成功写入的任务数量描述。
    """
    import json as _json
    import re as _re
    from datetime import date as _date

    try:
        assignments = _json.loads(assignments_json)
    except _json.JSONDecodeError as e:
        return f"JSON 解析失败: {e}"

    today = _date.today().isoformat()
    filepath = SCHEDULE_DIR / f"{today}.md"
    if not filepath.exists():
        return f"今日日程文件不存在: {today}"

    lines = filepath.read_text(encoding="utf-8").splitlines(keepends=True)

    in_flex = False
    flex_task_lines: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        stripped = line.rstrip("\n")
        if stripped.startswith("## "):
            if stripped[3:].strip() == "灵活待办":
                in_flex = True
            elif in_flex:
                break
        elif in_flex and line.startswith("- "):
            raw = line[2:].strip()
            if raw.startswith("[ ] ") or raw.startswith("[x] "):
                text = raw[4:]
            elif raw and raw != "-":
                text = raw
            else:
                continue
            flex_task_lines.append((i, text))

    _time_prefix_re = _re.compile(r"^\d{2}:\d{2}-\d{2}:\d{2}\s")
    updated = 0

    for assignment in assignments:
        idx = assignment.get("index", -1)
        start = assignment.get("start", "")
        end = assignment.get("end", "")
        if not (isinstance(idx, int) and start and end):
            continue
        if idx < 0 or idx >= len(flex_task_lines):
            continue
        line_i, text = flex_task_lines[idx]
        if _time_prefix_re.match(text):
            continue
        orig_raw = lines[line_i][2:].strip()
        marker = "[x] " if orig_raw.startswith("[x] ") else "[ ] "
        lines[line_i] = f"- {marker}{start}-{end} {text}\n"
        updated += 1

    filepath.write_text("".join(lines), encoding="utf-8")
    return f"已为 {updated} 个灵活待办任务分配时间"
```

- [ ] **Step 4: 更新 `agent.py`**

将 `agent.py` 完整替换为：

```python
import os
from dotenv import load_dotenv
from langchain_community.chat_models import ChatZhipuAI
from langgraph.prebuilt import create_react_agent

from tools import get_today_schedule, create_tomorrow_template, assign_flexible_times

load_dotenv()

SYSTEM_PROMPT = """你是一个早晨日程规划助手。每天早上：

1. 调用工具读取今天的日程表（分"固定日程"和"灵活待办"两部分）
2. "固定日程"是不能改变的时间块，必须严格保留
3. 分析固定日程之间的空隙时间
4. 调用 assign_flexible_times，把灵活待办塞进固定日程的空隙里，按优先级和预计耗时分配时间段，输出 JSON 数组，格式为 [{"index": 0, "start": "HH:MM", "end": "HH:MM"}, ...]，index 从0开始。已有时间前缀的任务跳过
5. 检查是否有时间冲突或安排过满，如有要提醒
6. 如果今天没有日程文件，告知用户并引导创建
7. 调用工具生成明天的日程模板文件
8. 给用户的回复是纯文本，会直接发送到邮件和手机消息，不要用任何Markdown符号，用自然的换行分段
9. 语气直接友好，不要说教，控制在250字以内"""

llm = ChatZhipuAI(
    model="glm-4-flash",
    api_key=os.environ.get("ZHIPUAI_API_KEY", ""),
)

agent = create_react_agent(
    model=llm,
    tools=[get_today_schedule, create_tomorrow_template, assign_flexible_times],
    prompt=SYSTEM_PROMPT,
)
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
pytest tests/test_tools.py tests/test_agent.py -v
```

期望：所有测试 PASS（test_agent.py 的原有测试：`"固定日程" in SYSTEM_PROMPT`、`"250字" in SYSTEM_PROMPT`、`"Markdown" in SYSTEM_PROMPT` 仍满足）

- [ ] **Step 6: 提交**

```bash
git add tools.py agent.py tests/test_tools.py
git commit -m "feat: add assign_flexible_times tool and update agent system prompt"
```

---

## Task 4: main.py — 新增 4 端点 + 晨间任务接入提醒调度

**Files:**
- Modify: `main.py`
- Modify: `tests/test_web.py` （末尾追加新测试）

**Interfaces:**
- Consumes:
  - `get_config() -> dict`（from `config`）
  - `save_config(data: dict)`（from `config`）
  - `reschedule_reminders(date_str, scheduler, advance_minutes, schedule_dir)` → `int`（from `reminder`）
  - `sse_generator()`（from `reminder`）
- Produces（新端点）:
  - `GET /api/settings` → `{"advance_minutes": int}`
  - `POST /api/settings` body `{"advance_minutes": int}` → `{"advance_minutes": int}`
  - `GET /api/events` → SSE stream
  - `POST /api/reminders/reschedule` → `{"scheduled": int}`

- [ ] **Step 1: 写失败测试**

在 `tests/test_web.py` 末尾追加：

```python
# ── Task 4 新增测试 ──────────────────────────────────────────────

def test_get_settings_api():
    from unittest.mock import patch
    from fastapi.testclient import TestClient

    with patch("main.scheduler"), \
         patch("main.get_config", return_value={"advance_minutes": 15}):
        from main import app
        with TestClient(app) as client:
            resp = client.get("/api/settings")

    assert resp.status_code == 200
    assert resp.json()["advance_minutes"] == 15


def test_post_settings_api():
    from unittest.mock import patch
    from fastapi.testclient import TestClient

    with patch("main.scheduler"), \
         patch("main.save_config") as mock_save, \
         patch("main.reschedule_reminders") as mock_resched, \
         patch("main.get_config", return_value={"advance_minutes": 20}):
        from main import app
        with TestClient(app) as client:
            resp = client.post("/api/settings", json={"advance_minutes": 20})

    assert resp.status_code == 200
    mock_save.assert_called_once_with({"advance_minutes": 20})
    mock_resched.assert_called_once()


def test_post_settings_rejects_negative():
    from unittest.mock import patch
    from fastapi.testclient import TestClient

    with patch("main.scheduler"):
        from main import app
        with TestClient(app) as client:
            resp = client.post("/api/settings", json={"advance_minutes": -1})

    assert resp.status_code == 400


def test_reschedule_api():
    from unittest.mock import patch
    from fastapi.testclient import TestClient

    with patch("main.scheduler"), \
         patch("main.get_config", return_value={"advance_minutes": 15}), \
         patch("main.reschedule_reminders", return_value=4):
        from main import app
        with TestClient(app) as client:
            resp = client.post("/api/reminders/reschedule")

    assert resp.status_code == 200
    assert resp.json()["scheduled"] == 4
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_web.py::test_get_settings_api -v
```

期望：`404 Not Found`（端点还不存在）

- [ ] **Step 3: 更新 `main.py` — 新增 import**

在 `main.py` 顶部的 import 区末尾（`from tools import ...` 之后）追加两行：

```python
from config import get_config, save_config
from reminder import reschedule_reminders, sse_generator
```

- [ ] **Step 4: 更新 `morning_review_job`**

将现有的 `morning_review_job` 函数替换为：

```python
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
```

- [ ] **Step 5: 新增 Pydantic 模型 + 4 个端点**

在 `main.py` 末尾（`@app.delete(...)` 之后）追加：

```python

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
```

- [ ] **Step 6: 运行全量测试，确认通过**

```bash
pytest tests/test_web.py -v
```

期望：所有测试 PASS（原有测试不受影响，新增 4 个测试 PASS）

- [ ] **Step 7: 提交**

```bash
git add main.py tests/test_web.py
git commit -m "feat: add settings and SSE endpoints, wire reschedule_reminders into morning job"
```

---

## Task 5: static/index.html — 设置面板 + SSE + 浏览器通知

**Files:**
- Modify: `static/index.html`

**No automated tests** — 用浏览器手动验证（见 Step 3）。

- [ ] **Step 1: 在 `</style>` 之前追加设置面板 CSS**

找到 `static/index.html` 中 `.btn-create:hover { background: #3a5fd9; }` 这行（约第 205 行），在它之后、`</style>` 之前插入：

```css

    /* ── 设置面板 ── */
    .topbar-right { display: flex; align-items: center; gap: 8px; position: relative; }
    .settings-btn {
      background: none; border: 1px solid #e0e0e0; border-radius: 6px;
      width: 28px; height: 28px; cursor: pointer; font-size: 0.85rem;
      display: flex; align-items: center; justify-content: center; color: #888;
    }
    .settings-btn:hover { background: #f5f5f5; }
    .settings-panel {
      display: none; position: absolute; top: 40px; right: 0;
      background: #fff; border: 1px solid #eee; border-radius: 12px;
      padding: 14px 16px; box-shadow: 0 4px 16px rgba(0,0,0,0.1);
      z-index: 100; min-width: 220px;
    }
    .settings-panel.open { display: block; }
    .settings-title {
      font-size: 0.78rem; color: #aaa; font-weight: 600;
      letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 10px;
    }
    .settings-row { display: flex; align-items: center; gap: 8px; }
    .settings-label { font-size: 0.85rem; color: #555; white-space: nowrap; }
    .settings-input {
      width: 54px; border: 1px solid #e0e0e0; border-radius: 6px;
      padding: 4px 8px; font-size: 0.85rem; text-align: center; outline: none;
    }
    .settings-input:focus { border-color: #4f7cff; }
    .settings-save {
      background: #4f7cff; color: #fff; border: none; border-radius: 6px;
      padding: 5px 12px; font-size: 0.82rem; cursor: pointer;
    }
    .settings-save:hover { background: #3a5fd9; }
    .settings-ok { font-size: 0.78rem; color: #52c47a; margin-top: 8px; display: none; }
```

- [ ] **Step 2: 修改 topbar HTML，添加 ⚙ 按钮和设置面板**

将现有 topbar 片段：

```html
<div class="topbar">
  <span class="topbar-title">我的日程</span>
  <div class="date-nav">
    <button class="nav-btn" onclick="changeDay(-1)">‹</button>
    <span class="date-display">
      <span id="date-label">—</span>
      <input type="date" id="date-picker">
    </span>
    <button class="nav-btn" onclick="changeDay(1)">›</button>
  </div>
</div>
```

替换为：

```html
<div class="topbar">
  <span class="topbar-title">我的日程</span>
  <div class="topbar-right">
    <div class="date-nav">
      <button class="nav-btn" onclick="changeDay(-1)">‹</button>
      <span class="date-display">
        <span id="date-label">—</span>
        <input type="date" id="date-picker">
      </span>
      <button class="nav-btn" onclick="changeDay(1)">›</button>
    </div>
    <button class="settings-btn" onclick="toggleSettings()" title="设置">⚙</button>
    <div class="settings-panel" id="settings-panel">
      <div class="settings-title">设置</div>
      <div class="settings-row">
        <span class="settings-label">提前提醒</span>
        <input type="number" id="advance-input" class="settings-input" min="0" max="120" value="15">
        <span class="settings-label">分钟</span>
        <button class="settings-save" onclick="saveSettings()">保存</button>
      </div>
      <div class="settings-ok" id="settings-ok">已保存 ✓</div>
    </div>
  </div>
</div>
```

- [ ] **Step 3: 在 `// 初始化` 注释之前插入设置面板 + SSE + 通知 JS**

找到 `// 初始化` 这行（约第 474 行），在它之前插入：

```javascript
  // ── 设置面板 ──────────────────────────────────────────────────
  function toggleSettings() {
    const panel = document.getElementById('settings-panel');
    panel.classList.toggle('open');
    if (panel.classList.contains('open')) loadSettings();
  }

  document.addEventListener('click', e => {
    const panel = document.getElementById('settings-panel');
    if (!panel.classList.contains('open')) return;
    if (!panel.contains(e.target) && !e.target.closest('.settings-btn')) {
      panel.classList.remove('open');
    }
  });

  async function loadSettings() {
    const res = await fetch('/api/settings');
    if (!res.ok) return;
    const data = await res.json();
    document.getElementById('advance-input').value = data.advance_minutes;
  }

  async function saveSettings() {
    const minutes = parseInt(document.getElementById('advance-input').value, 10);
    if (isNaN(minutes) || minutes < 0) return;
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ advance_minutes: minutes }),
    });
    if (!res.ok) return;
    const ok = document.getElementById('settings-ok');
    ok.style.display = 'block';
    setTimeout(() => { ok.style.display = 'none'; }, 2000);
  }

  // ── 浏览器通知 ────────────────────────────────────────────────
  if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
  }

  function showNotification(ev) {
    if (!('Notification' in window) || Notification.permission !== 'granted') return;
    const title = ev.early
      ? `⏰ ${ev.task} 还有 ${ev.advance_minutes} 分钟`
      : `🔔 ${ev.task} 开始了`;
    new Notification(title, { body: `安排时间：${ev.time}` });
  }

  // ── SSE 客户端 ────────────────────────────────────────────────
  const _es = new EventSource('/api/events');
  _es.onmessage = e => {
    try {
      const ev = JSON.parse(e.data);
      if (ev.type === 'reminder') showNotification(ev);
    } catch (_) {}
  };

```

- [ ] **Step 4: 手动验证**

启动服务：

```bash
cd /Users/yxlh/Documents/morning-agent
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

打开 `http://127.0.0.1:8000`，验证：
1. 顶部右侧出现 ⚙ 按钮
2. 点击 ⚙ 展开设置面板，显示"提前提醒 [15] 分钟 [保存]"
3. 修改数字为 5，点保存，出现"已保存 ✓"提示
4. 再次打开设置面板，数字为 5（已从后端读取）
5. 点面板以外区域，面板自动收起
6. 浏览器弹出通知权限请求，允许后不再弹

- [ ] **Step 5: 运行全量测试确认无回归**

```bash
pytest -v
```

期望：所有测试 PASS

- [ ] **Step 6: 提交**

```bash
git add static/index.html
git commit -m "feat: add settings panel, SSE client, and browser notification support"
```

---

## Self-Review

**1. Spec coverage:**

| Spec 要求 | 对应任务 |
|-----------|----------|
| 时间提醒：提前 + 准点 | Task 2 `reschedule_reminders` |
| 双渠道：微信 + 浏览器 | Task 2 `_reminder_job` + Task 5 SSE/Notification |
| AI 写回时间槽 | Task 3 `assign_flexible_times` |
| 已有时间前缀不覆盖 | Task 3 tool 实现 + 测试 |
| 提前分钟数网页可设 | Task 4 `/api/settings` + Task 5 设置面板 |
| AI 自动触发（7 点） | Task 4 `morning_review_job` finally 块 |
| SSE 实时推送 | Task 2 `sse_generator` + Task 4 `/api/events` |
| 设置持久化 | Task 1 `config.py` |
| Job ID 格式 `reminder_{date}_{index}_{early\|ontime}` | Task 2 实现 + 测试 |
| `schedule_dir` 可注入 | Task 2 `parse_task_times` + `reschedule_reminders` |

**2. Placeholder scan:** 无 TBD/TODO/占位符。

**3. Type consistency:**
- `reschedule_reminders` 在 Task 2 定义，在 Task 4 `main.py` 调用，签名一致
- `get_config()` / `save_config()` 在 Task 1 定义，Task 4 导入，签名一致
- `sse_generator()` 在 Task 2 定义，Task 4 使用，一致
- `assign_flexible_times` 在 Task 3 定义，`agent.py` 导入，工具名一致
- SSE 事件格式：Task 2 `push_reminder_event` 输出 → Task 5 `showNotification` 消费，字段一致（`type`, `task`, `time`, `early`, `advance_minutes`）
