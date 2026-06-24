# 网页端日程编辑 + 启动即推送 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在网页端支持任意日期日程的增删改，服务启动时立即触发一次推送，保留 7 点定时任务。

**Architecture:** 三层改动——tools.py 新增文件操作辅助函数；main.py 重构解析函数支持任意日期并新增 5 个 API 端点；index.html 增加日期选择器和内联编辑 UI。

**Tech Stack:** Python 3.x, FastAPI, APScheduler, HTML/CSS/JS (vanilla)

## Global Constraints

- `schedule_dir` 参数必须透传到所有文件操作函数，测试用 `tmp_path` 注入
- 现有接口 `GET /api/today`、`PATCH /api/task/{task_id}` 行为不变（向后兼容）
- section 名称固定为"固定日程"和"灵活待办"，`create_schedule` 硬编码这两个
- 测试使用 `monkeypatch` 或 `patch("main._DEFAULT_SCHEDULE_DIR", tmp_path)` 隔离文件系统
- TDD：先写失败测试，再写实现

---

## 文件改动范围

| 文件 | 类型 | 说明 |
|------|------|------|
| `tools.py` | 修改 | 新增 `_get_filepath`、`create_schedule`、`append_task`、`delete_task`、`update_task_text` |
| `main.py` | 修改 | `parse_today` 重构为 `parse_schedule(date_str, schedule_dir)`，`write_task_done` 加 `date_str` 参数，新增 5 个端点，lifespan 加启动触发 |
| `tests/test_tools.py` | 修改 | 新增对 4 个新函数的测试 |
| `tests/test_web.py` | 修改 | 新增对新端点的测试，更新 `write_task_done` 调用签名的测试 |
| `static/index.html` | 修改 | 日期选择器 + 内联增删改 UI |

---

## Task 1: tools.py 新增文件操作辅助函数

**Files:**
- Modify: `tools.py`
- Test: `tests/test_tools.py`

**Interfaces:**
- Produces:
  - `_get_filepath(date_str: str, schedule_dir: Optional[Path] = None) -> Path`
  - `create_schedule(date_str: str, schedule_dir: Optional[Path] = None) -> None`
  - `append_task(date_str: str, section_name: str, text: str, schedule_dir: Optional[Path] = None) -> None`  raises `FileNotFoundError` / `ValueError`
  - `delete_task(date_str: str, task_id: str, schedule_dir: Optional[Path] = None) -> None`  raises `FileNotFoundError` / `LookupError` / `ValueError`
  - `update_task_text(date_str: str, task_id: str, text: str, schedule_dir: Optional[Path] = None) -> None`  raises `FileNotFoundError` / `LookupError` / `ValueError`

- [ ] **Step 1: 写失败测试**

在 `tests/test_tools.py` 末尾追加：

```python
# ── Task 1 新增测试 ──────────────────────────────────────────────

def test_create_schedule_creates_two_sections(tmp_path):
    import tools
    tools.create_schedule("2026-06-24", schedule_dir=tmp_path)
    content = (tmp_path / "2026-06-24.md").read_text(encoding="utf-8")
    assert "## 固定日程" in content
    assert "## 灵活待办" in content


def test_create_schedule_no_overwrite(tmp_path):
    import tools
    (tmp_path / "2026-06-24.md").write_text("原有内容", encoding="utf-8")
    tools.create_schedule("2026-06-24", schedule_dir=tmp_path)
    assert (tmp_path / "2026-06-24.md").read_text(encoding="utf-8") == "原有内容"


def test_append_task_adds_to_section(tmp_path):
    import tools
    (tmp_path / "2026-06-24.md").write_text(
        "## 固定日程\n- [ ] 已有任务\n\n## 灵活待办\n",
        encoding="utf-8",
    )
    tools.append_task("2026-06-24", "固定日程", "新任务", schedule_dir=tmp_path)
    content = (tmp_path / "2026-06-24.md").read_text(encoding="utf-8")
    assert "- [ ] 新任务" in content
    lines = content.splitlines()
    # 新任务应在固定日程 section 内（灵活待办之前）
    new_idx = next(i for i, l in enumerate(lines) if "新任务" in l)
    flex_idx = next(i for i, l in enumerate(lines) if "灵活待办" in l)
    assert new_idx < flex_idx


def test_append_task_to_empty_section(tmp_path):
    import tools
    (tmp_path / "2026-06-24.md").write_text(
        "## 固定日程\n\n## 灵活待办\n",
        encoding="utf-8",
    )
    tools.append_task("2026-06-24", "固定日程", "第一个任务", schedule_dir=tmp_path)
    content = (tmp_path / "2026-06-24.md").read_text(encoding="utf-8")
    assert "- [ ] 第一个任务" in content


def test_append_task_missing_file_raises(tmp_path):
    import tools, pytest
    with pytest.raises(FileNotFoundError):
        tools.append_task("2099-01-01", "固定日程", "任务", schedule_dir=tmp_path)


def test_append_task_missing_section_raises(tmp_path):
    import tools, pytest
    (tmp_path / "2026-06-24.md").write_text("## 固定日程\n", encoding="utf-8")
    with pytest.raises(ValueError):
        tools.append_task("2026-06-24", "不存在的section", "任务", schedule_dir=tmp_path)


def test_delete_task_removes_line(tmp_path):
    import tools
    (tmp_path / "2026-06-24.md").write_text(
        "## 灵活待办\n- [ ] 任务A\n- [x] 任务B\n",
        encoding="utf-8",
    )
    tools.delete_task("2026-06-24", "s0-t0", schedule_dir=tmp_path)
    content = (tmp_path / "2026-06-24.md").read_text(encoding="utf-8")
    assert "任务A" not in content
    assert "任务B" in content


def test_delete_task_not_found_raises(tmp_path):
    import tools, pytest
    (tmp_path / "2026-06-24.md").write_text("## 灵活待办\n- [ ] 只有一个\n", encoding="utf-8")
    with pytest.raises(LookupError):
        tools.delete_task("2026-06-24", "s0-t5", schedule_dir=tmp_path)


def test_update_task_text_changes_text_keeps_done(tmp_path):
    import tools
    (tmp_path / "2026-06-24.md").write_text(
        "## 灵活待办\n- [x] 旧文字\n",
        encoding="utf-8",
    )
    tools.update_task_text("2026-06-24", "s0-t0", "新文字", schedule_dir=tmp_path)
    content = (tmp_path / "2026-06-24.md").read_text(encoding="utf-8")
    assert "- [x] 新文字" in content
    assert "旧文字" not in content


def test_update_task_text_not_found_raises(tmp_path):
    import tools, pytest
    (tmp_path / "2026-06-24.md").write_text("## 灵活待办\n- [ ] 任务\n", encoding="utf-8")
    with pytest.raises(LookupError):
        tools.update_task_text("2026-06-24", "s0-t9", "新文字", schedule_dir=tmp_path)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/yxlh/Documents/morning-agent
pytest tests/test_tools.py -v -k "create_schedule or append_task or delete_task or update_task_text"
```

预期：全部 FAIL（函数未定义）

- [ ] **Step 3: 在 tools.py 末尾追加实现**

在 `tools.py` 的现有 `create_tomorrow_template` 函数之后追加：

```python
from typing import Optional


def _get_filepath(date_str: str, schedule_dir: Optional[Path] = None) -> Path:
    directory = schedule_dir if schedule_dir is not None else SCHEDULE_DIR
    return directory / f"{date_str}.md"


def create_schedule(date_str: str, schedule_dir: Optional[Path] = None) -> None:
    filepath = _get_filepath(date_str, schedule_dir)
    if filepath.exists():
        return
    template = (
        f"# {date_str} 日程表\n\n"
        f"## 固定日程\n\n"
        f"## 灵活待办\n"
    )
    filepath.write_text(template, encoding="utf-8")


def append_task(date_str: str, section_name: str, text: str, schedule_dir: Optional[Path] = None) -> None:
    filepath = _get_filepath(date_str, schedule_dir)
    if not filepath.exists():
        raise FileNotFoundError(f"No schedule file for {date_str}")

    lines = filepath.read_text(encoding="utf-8").splitlines(keepends=True)

    section_idx = None
    for i, line in enumerate(lines):
        if line.startswith("## ") and line[3:].strip() == section_name:
            section_idx = i
            break

    if section_idx is None:
        raise ValueError(f"Section '{section_name}' not found")

    insert_at = section_idx + 1
    for i in range(section_idx + 1, len(lines)):
        if lines[i].startswith("## "):
            break
        if lines[i].startswith("- "):
            raw = lines[i][2:].strip()
            if raw and raw != "-":
                insert_at = i + 1

    lines.insert(insert_at, f"- [ ] {text}\n")
    filepath.write_text("".join(lines), encoding="utf-8")


def _find_task_line(lines: list, task_id: str) -> int:
    """返回匹配 task_id 的行索引，找不到返回 -1。"""
    try:
        parts = task_id.split("-")
        target_si, target_ti = int(parts[0][1:]), int(parts[1][1:])
    except (IndexError, ValueError):
        raise ValueError(f"Invalid task_id format: {task_id}")

    current_si, current_ti = -1, -1
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
                return i
    return -1


def delete_task(date_str: str, task_id: str, schedule_dir: Optional[Path] = None) -> None:
    filepath = _get_filepath(date_str, schedule_dir)
    if not filepath.exists():
        raise FileNotFoundError(f"No schedule file for {date_str}")

    lines = filepath.read_text(encoding="utf-8").splitlines(keepends=True)
    idx = _find_task_line(lines, task_id)
    if idx == -1:
        raise LookupError(f"Task {task_id} not found")

    del lines[idx]
    filepath.write_text("".join(lines), encoding="utf-8")


def update_task_text(date_str: str, task_id: str, text: str, schedule_dir: Optional[Path] = None) -> None:
    filepath = _get_filepath(date_str, schedule_dir)
    if not filepath.exists():
        raise FileNotFoundError(f"No schedule file for {date_str}")

    lines = filepath.read_text(encoding="utf-8").splitlines(keepends=True)
    idx = _find_task_line(lines, task_id)
    if idx == -1:
        raise LookupError(f"Task {task_id} not found")

    raw = lines[idx][2:].strip()
    marker = raw[:4] if raw.startswith("[x] ") or raw.startswith("[ ] ") else "[ ] "
    lines[idx] = f"- {marker}{text}\n"
    filepath.write_text("".join(lines), encoding="utf-8")
```

注意：`tools.py` 顶部已有 `from pathlib import Path`，只需在文件顶部的 import 区域补充 `from typing import Optional`（如果还没有的话）。

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_tools.py -v
```

预期：全部 PASS（包含新增的 12 个测试）

- [ ] **Step 5: 提交**

```bash
git add tools.py tests/test_tools.py
git commit -m "feat: add file-level task CRUD helpers to tools.py"
```

---

## Task 2: main.py 重构 + 新端点 + 启动触发

**Files:**
- Modify: `main.py:1-162`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes（来自 Task 1）:
  - `create_schedule(date_str, schedule_dir)` from `tools`
  - `append_task(date_str, section_name, text, schedule_dir)` from `tools`
  - `delete_task(date_str, task_id, schedule_dir)` from `tools`
  - `update_task_text(date_str, task_id, text, schedule_dir)` from `tools`
- Produces:
  - `parse_schedule(date_str: str, schedule_dir: Optional[Path] = None) -> dict`
  - `parse_today(schedule_dir)` 保留，内部调 `parse_schedule`
  - `write_task_done(task_id, done, date_str=None, schedule_dir=None) -> dict`
  - `GET /api/schedule/{date_str}` → 返回 `parse_schedule` 结构
  - `POST /api/schedule/{date_str}` → 创建空文件，返回 `parse_schedule` 结构
  - `POST /api/schedule/{date_str}/task` body `{"section": str, "text": str}` → 返回更新后结构
  - `PATCH /api/schedule/{date_str}/task/{task_id}` body `{"done": bool}` 或 `{"text": str}` → 返回更新后结构
  - `DELETE /api/schedule/{date_str}/task/{task_id}` → 返回更新后结构

- [ ] **Step 1: 写失败测试**

在 `tests/test_web.py` 末尾追加：

```python
# ── Task 2 新增测试 ──────────────────────────────────────────────

def test_parse_schedule_any_date(tmp_path):
    from main import parse_schedule

    (tmp_path / "2026-01-15.md").write_text(
        "## 固定日程\n- [ ] 开会\n",
        encoding="utf-8",
    )
    result = parse_schedule("2026-01-15", schedule_dir=tmp_path)
    assert result["date"] == "2026-01-15"
    assert result["sections"][0]["tasks"][0]["text"] == "开会"


def test_write_task_done_with_date_str(tmp_path):
    from main import write_task_done

    (tmp_path / "2026-01-15.md").write_text(
        "## 灵活待办\n- 任务A\n",
        encoding="utf-8",
    )
    result = write_task_done("s0-t0", True, date_str="2026-01-15", schedule_dir=tmp_path)
    assert result["sections"][0]["tasks"][0]["done"] is True


def test_get_schedule_api(tmp_path):
    from unittest.mock import patch
    from fastapi.testclient import TestClient

    (tmp_path / "2026-01-15.md").write_text(
        "## 固定日程\n- [ ] 开会\n",
        encoding="utf-8",
    )

    with patch("main._DEFAULT_SCHEDULE_DIR", tmp_path), \
         patch("main.scheduler"):
        from main import app
        with TestClient(app) as client:
            resp = client.get("/api/schedule/2026-01-15")

    assert resp.status_code == 200
    assert resp.json()["date"] == "2026-01-15"
    assert resp.json()["sections"][0]["tasks"][0]["text"] == "开会"


def test_create_day_api(tmp_path):
    from unittest.mock import patch
    from fastapi.testclient import TestClient

    with patch("main._DEFAULT_SCHEDULE_DIR", tmp_path), \
         patch("main.scheduler"):
        from main import app
        with TestClient(app) as client:
            resp = client.post("/api/schedule/2026-01-16")

    assert resp.status_code == 200
    assert (tmp_path / "2026-01-16.md").exists()
    data = resp.json()
    assert data["date"] == "2026-01-16"
    section_names = [s["name"] for s in data["sections"]]
    assert "固定日程" in section_names
    assert "灵活待办" in section_names


def test_add_task_api(tmp_path):
    from unittest.mock import patch
    from fastapi.testclient import TestClient

    (tmp_path / "2026-01-15.md").write_text(
        "## 固定日程\n\n## 灵活待办\n",
        encoding="utf-8",
    )

    with patch("main._DEFAULT_SCHEDULE_DIR", tmp_path), \
         patch("main.scheduler"):
        from main import app
        with TestClient(app) as client:
            resp = client.post(
                "/api/schedule/2026-01-15/task",
                json={"section": "灵活待办", "text": "写测试"},
            )

    assert resp.status_code == 200
    tasks = resp.json()["sections"][1]["tasks"]
    assert tasks[0]["text"] == "写测试"
    assert tasks[0]["done"] is False


def test_patch_task_text_api(tmp_path):
    from unittest.mock import patch
    from fastapi.testclient import TestClient

    (tmp_path / "2026-01-15.md").write_text(
        "## 灵活待办\n- [ ] 旧文字\n",
        encoding="utf-8",
    )

    with patch("main._DEFAULT_SCHEDULE_DIR", tmp_path), \
         patch("main.scheduler"):
        from main import app
        with TestClient(app) as client:
            resp = client.patch(
                "/api/schedule/2026-01-15/task/s0-t0",
                json={"text": "新文字"},
            )

    assert resp.status_code == 200
    assert resp.json()["sections"][0]["tasks"][0]["text"] == "新文字"


def test_patch_task_done_api(tmp_path):
    from unittest.mock import patch
    from fastapi.testclient import TestClient

    (tmp_path / "2026-01-15.md").write_text(
        "## 灵活待办\n- [ ] 某任务\n",
        encoding="utf-8",
    )

    with patch("main._DEFAULT_SCHEDULE_DIR", tmp_path), \
         patch("main.scheduler"):
        from main import app
        with TestClient(app) as client:
            resp = client.patch(
                "/api/schedule/2026-01-15/task/s0-t0",
                json={"done": True},
            )

    assert resp.status_code == 200
    assert resp.json()["sections"][0]["tasks"][0]["done"] is True


def test_delete_task_api(tmp_path):
    from unittest.mock import patch
    from fastapi.testclient import TestClient

    (tmp_path / "2026-01-15.md").write_text(
        "## 灵活待办\n- [ ] 任务A\n- [ ] 任务B\n",
        encoding="utf-8",
    )

    with patch("main._DEFAULT_SCHEDULE_DIR", tmp_path), \
         patch("main.scheduler"):
        from main import app
        with TestClient(app) as client:
            resp = client.delete("/api/schedule/2026-01-15/task/s0-t0")

    assert resp.status_code == 200
    tasks = resp.json()["sections"][0]["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["text"] == "任务B"


def test_startup_triggers_morning_review(monkeypatch):
    import asyncio
    from unittest.mock import patch, AsyncMock, MagicMock

    monkeypatch.setenv("ZHIPUAI_API_KEY", "fake")
    created = []

    def fake_create_task(coro, **kw):
        coro.close()
        created.append(True)
        return MagicMock()

    with patch("main.morning_review_job", new_callable=AsyncMock), \
         patch("main.scheduler"), \
         patch("asyncio.create_task", side_effect=fake_create_task):
        from main import app
        from fastapi.testclient import TestClient
        with TestClient(app):
            pass

    assert len(created) == 1
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_web.py -v -k "parse_schedule or write_task_done_with_date or get_schedule_api or create_day or add_task_api or patch_task_text or patch_task_done or delete_task_api or startup_triggers"
```

预期：全部 FAIL

- [ ] **Step 3: 修改 main.py**

用以下内容替换 `main.py`：

```python
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
```

- [ ] **Step 4: 运行全部测试确认通过**

```bash
pytest tests/ -v
```

预期：全部 PASS，包含旧测试和新测试

- [ ] **Step 5: 提交**

```bash
git add main.py tests/test_web.py
git commit -m "feat: add date-parameterized schedule API and startup trigger"
```

---

## Task 3: index.html 日期选择器 + 内联编辑 UI

**Files:**
- Modify: `static/index.html`

**Interfaces:**
- Consumes（来自 Task 2）:
  - `GET /api/schedule/{date}` → `{date, sections, total, done_count}`
  - `POST /api/schedule/{date}` → 创建空文件
  - `POST /api/schedule/{date}/task` body `{section, text}`
  - `PATCH /api/schedule/{date}/task/{task_id}` body `{done}` 或 `{text}`
  - `DELETE /api/schedule/{date}/task/{task_id}`

- [ ] **Step 1: 用新内容替换 static/index.html**

```html
<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>今日日程</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f5f5f5; color: #333; padding: 24px;
      max-width: 600px; margin: 0 auto;
    }
    .date-header { margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
    .date-header h1 { font-size: 1.4rem; color: #222; }
    .date-picker {
      padding: 4px 10px; border: 1px solid #ddd; border-radius: 8px;
      font-size: 0.9rem; color: #555; background: white; cursor: pointer;
    }
    .card {
      background: white; border-radius: 12px; padding: 20px;
      margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
    .card-title { font-size: 1rem; font-weight: 600; color: #333; }
    .count-label { font-size: 0.85rem; color: #999; }
    .bar-wrap { height: 10px; background: #ebebeb; border-radius: 5px; overflow: hidden; }
    .bar-fill { height: 100%; border-radius: 5px; background: #5b8def; transition: width 0.3s ease; }
    .bar-fill.complete { background: #52c47a; }
    .done-msg { text-align: center; padding-top: 8px; font-size: 0.9rem; color: #52c47a; font-weight: 500; }
    .section-card { background: white; border-radius: 12px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
    .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
    .section-title { font-size: 0.95rem; font-weight: 600; color: #444; }
    .section-header-right { display: flex; align-items: center; gap: 12px; }
    .mini-progress { display: flex; align-items: center; gap: 8px; }
    .mini-bar { width: 72px; height: 6px; background: #ebebeb; border-radius: 3px; overflow: hidden; }
    .mini-fill { height: 100%; border-radius: 3px; background: #5b8def; transition: width 0.3s ease; }
    .mini-count { font-size: 0.78rem; color: #bbb; }
    .btn-add-task {
      background: none; border: 1px solid #5b8def; color: #5b8def;
      border-radius: 6px; padding: 2px 8px; cursor: pointer; font-size: 0.8rem;
    }
    .btn-add-task:hover { background: #f0f5ff; }
    .task-list { list-style: none; }
    .task-item {
      display: flex; align-items: flex-start; gap: 10px;
      padding: 9px 6px; border-radius: 6px;
      transition: background 0.1s; position: relative;
    }
    .task-item:hover { background: #f7f7f7; }
    .task-item + .task-item { border-top: 1px solid #f2f2f2; }
    .task-item.clickable { cursor: pointer; }
    .checkbox {
      width: 18px; height: 18px; border: 2px solid #ccc; border-radius: 4px;
      flex-shrink: 0; margin-top: 1px; display: flex; align-items: center;
      justify-content: center; transition: all 0.15s; font-size: 11px; color: white;
    }
    .checkbox.checked { background: #52c47a; border-color: #52c47a; }
    .task-text { font-size: 0.9rem; line-height: 1.45; color: #333; flex: 1; }
    .task-text.done { text-decoration: line-through; color: #bbb; }
    .task-actions { display: none; margin-left: auto; gap: 2px; align-items: center; flex-shrink: 0; }
    .task-item:hover .task-actions { display: flex; }
    .task-item.editing .task-actions { display: flex; }
    .btn-icon {
      background: none; border: none; cursor: pointer;
      padding: 3px 5px; border-radius: 4px; font-size: 0.85rem; color: #bbb;
      line-height: 1;
    }
    .btn-icon.edit:hover { color: #5b8def; background: #f0f5ff; }
    .btn-icon.delete:hover { color: #ff4d4f; background: #fff1f0; }
    .btn-icon.save { color: #52c47a; }
    .btn-icon.save:hover { background: #f6ffed; }
    .btn-icon.cancel:hover { color: #999; background: #f5f5f5; }
    .task-edit-input {
      flex: 1; border: 1px solid #5b8def; border-radius: 4px;
      padding: 2px 6px; font-size: 0.9rem; outline: none; min-width: 0;
    }
    .add-form {
      display: flex; gap: 8px; padding: 10px 6px 4px;
      border-top: 1px solid #f2f2f2; align-items: center;
    }
    .add-input {
      flex: 1; border: 1px solid #ddd; border-radius: 6px;
      padding: 6px 10px; font-size: 0.9rem; outline: none; min-width: 0;
    }
    .add-input:focus { border-color: #5b8def; }
    .btn-confirm {
      background: #5b8def; color: white; border: none;
      border-radius: 6px; padding: 6px 12px; cursor: pointer; font-size: 0.85rem; white-space: nowrap;
    }
    .btn-cancel-add {
      background: none; border: 1px solid #ddd; border-radius: 6px;
      padding: 6px 10px; cursor: pointer; font-size: 0.85rem; color: #999; white-space: nowrap;
    }
    .empty { text-align: center; color: #ccc; padding: 48px 20px; font-size: 0.9rem; line-height: 1.7; }
    .create-btn {
      background: #5b8def; color: white; border: none; border-radius: 8px;
      padding: 10px 24px; cursor: pointer; font-size: 0.95rem; margin-top: 16px;
    }
    .create-btn:hover { background: #4a7de0; }
  </style>
</head>
<body>
  <div class="date-header">
    <h1 id="date-title">—</h1>
    <input type="date" id="date-picker" class="date-picker">
  </div>
  <div id="app"><div class="empty">加载中…</div></div>

  <script>
    const WEEKDAYS = ['周日','周一','周二','周三','周四','周五','周六'];
    let _data = null;
    let _currentDate = new Date().toISOString().slice(0, 10);
    let _editing = null;      // {taskId}
    let _addingSection = null; // section name

    // ── 初始化 ──────────────────────────────────────────────────

    const picker = document.getElementById('date-picker');
    picker.value = _currentDate;
    picker.addEventListener('change', e => {
      _currentDate = e.target.value;
      _editing = null;
      _addingSection = null;
      load();
    });

    // ── 数据加载 ─────────────────────────────────────────────────

    async function load() {
      const res = await fetch('/api/schedule/' + _currentDate);
      _data = await res.json();
      render(_data);
    }

    // ── 操作函数 ─────────────────────────────────────────────────

    async function createSchedule() {
      await fetch('/api/schedule/' + _currentDate, { method: 'POST' });
      load();
    }

    async function toggle(taskId, currentDone) {
      const res = await fetch('/api/schedule/' + _currentDate + '/task/' + taskId, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ done: !currentDone }),
      });
      if (!res.ok) return;
      _data = await res.json();
      render(_data);
    }

    function startEdit(taskId) {
      _editing = { taskId };
      _addingSection = null;
      render(_data);
      setTimeout(() => {
        const el = document.getElementById('edit-input-' + taskId);
        if (el) { el.focus(); el.select(); }
      }, 30);
    }

    function cancelEdit() {
      _editing = null;
      render(_data);
    }

    async function saveEdit(taskId) {
      const el = document.getElementById('edit-input-' + taskId);
      const text = el ? el.value.trim() : '';
      if (!text) { cancelEdit(); return; }
      const res = await fetch('/api/schedule/' + _currentDate + '/task/' + taskId, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) return;
      _data = await res.json();
      _editing = null;
      render(_data);
    }

    async function deleteTask(taskId) {
      const res = await fetch('/api/schedule/' + _currentDate + '/task/' + taskId, {
        method: 'DELETE',
      });
      if (!res.ok) return;
      _data = await res.json();
      render(_data);
    }

    function showAddForm(sectionName) {
      _addingSection = sectionName;
      _editing = null;
      render(_data);
      setTimeout(() => {
        const el = document.getElementById('add-input-' + encSec(sectionName));
        if (el) el.focus();
      }, 30);
    }

    function cancelAdd() {
      _addingSection = null;
      render(_data);
    }

    async function confirmAdd(sectionName) {
      const el = document.getElementById('add-input-' + encSec(sectionName));
      const text = el ? el.value.trim() : '';
      if (!text) { cancelAdd(); return; }
      const res = await fetch('/api/schedule/' + _currentDate + '/task', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ section: sectionName, text }),
      });
      if (!res.ok) return;
      _data = await res.json();
      _addingSection = null;
      render(_data);
    }

    function encSec(name) { return name.replace(/\s+/g, '_'); }

    function esc(s) {
      return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
    }

    // ── 渲染 ─────────────────────────────────────────────────────

    function bar(pct, extra) {
      return `<div class="bar-wrap"><div class="bar-fill ${extra}" style="width:${pct}%"></div></div>`;
    }

    function render(data) {
      const d = new Date(data.date + 'T12:00:00');
      document.getElementById('date-title').textContent = data.date + ' ' + WEEKDAYS[d.getDay()];

      const app = document.getElementById('app');

      if (!data.sections || data.sections.length === 0) {
        app.innerHTML = `<div class="empty">这天还没有日程文件<br>
          <button class="create-btn" onclick="createSchedule()">创建日程</button>
        </div>`;
        return;
      }

      const pct = data.total > 0 ? Math.round(data.done_count / data.total * 100) : 0;
      const allDone = data.total > 0 && data.done_count === data.total;

      let html = `<div class="card">
        <div class="card-header">
          <span class="card-title">今日进度</span>
          <span class="count-label">${data.done_count} / ${data.total} 完成</span>
        </div>
        ${bar(pct, allDone ? 'complete' : '')}
        ${allDone ? '<div class="done-msg">今天的事都做完了 🎉</div>' : ''}
      </div>`;

      for (const section of data.sections) {
        const st = section.tasks.length;
        const sd = section.tasks.filter(t => t.done).length;
        const sp = st > 0 ? Math.round(sd / st * 100) : 0;

        html += `<div class="section-card">
          <div class="section-header">
            <span class="section-title">${esc(section.name)}</span>
            <div class="section-header-right">
              <div class="mini-progress">
                <div class="mini-bar"><div class="mini-fill" style="width:${sp}%"></div></div>
                <span class="mini-count">${sd}/${st}</span>
              </div>
              <button class="btn-add-task" onclick="showAddForm('${esc(section.name)}')">+ 添加</button>
            </div>
          </div>
          <ul class="task-list">`;

        for (const task of section.tasks) {
          const isEditing = _editing && _editing.taskId === task.id;

          if (isEditing) {
            html += `<li class="task-item editing">
              <div class="checkbox${task.done ? ' checked' : ''}">${task.done ? '✓' : ''}</div>
              <input id="edit-input-${task.id}" class="task-edit-input" value="${esc(task.text)}"
                onkeydown="if(event.key==='Enter')saveEdit('${task.id}');if(event.key==='Escape')cancelEdit()">
              <div class="task-actions">
                <button class="btn-icon save" onclick="saveEdit('${task.id}')" title="保存">✓</button>
                <button class="btn-icon cancel" onclick="cancelEdit()" title="取消">✕</button>
              </div>
            </li>`;
          } else {
            html += `<li class="task-item clickable" onclick="toggle('${task.id}',${task.done})">
              <div class="checkbox${task.done ? ' checked' : ''}">${task.done ? '✓' : ''}</div>
              <span class="task-text${task.done ? ' done' : ''}">${esc(task.text)}</span>
              <div class="task-actions">
                <button class="btn-icon edit" onclick="event.stopPropagation();startEdit('${task.id}')" title="编辑">✎</button>
                <button class="btn-icon delete" onclick="event.stopPropagation();deleteTask('${task.id}')" title="删除">×</button>
              </div>
            </li>`;
          }
        }

        html += `</ul>`;

        if (_addingSection === section.name) {
          const key = encSec(section.name);
          html += `<div class="add-form">
            <input id="add-input-${key}" class="add-input" placeholder="输入任务内容…"
              onkeydown="if(event.key==='Enter')confirmAdd('${esc(section.name)}');if(event.key==='Escape')cancelAdd()">
            <button class="btn-confirm" onclick="confirmAdd('${esc(section.name)}')">确认</button>
            <button class="btn-cancel-add" onclick="cancelAdd()">取消</button>
          </div>`;
        }

        html += `</div>`;
      }

      app.innerHTML = html;
    }

    load();
  </script>
</body>
</html>
```

- [ ] **Step 2: 启动服务手动验证**

```bash
cd /Users/yxlh/Documents/morning-agent
uvicorn main:app --reload
```

按顺序验证：
1. 打开 http://localhost:8000，确认日期选择器默认显示今天
2. 切换到没有日程的日期（如明天），确认出现"创建日程"按钮
3. 点击"创建日程"，确认页面出现"固定日程"和"灵活待办"两个 section
4. 在"灵活待办"点"+ 添加"，输入任务名，回车，确认任务出现在列表中
5. 悬停任务，出现"✎"和"×"按钮
6. 点"✎"，修改文字，回车保存，确认文字更新
7. 点"×"，确认任务消失
8. 点任务勾选框，确认打勾/取消打勾正常
9. 切回今天，确认今天的数据正常加载

- [ ] **Step 3: 提交**

```bash
git add static/index.html
git commit -m "feat: add date picker and inline task editing to web UI"
```
