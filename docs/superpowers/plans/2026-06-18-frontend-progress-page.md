# Frontend Progress Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 FastAPI 应用上增加三个 API 路由和一个静态 HTML 页面，展示今日任务列表并支持勾选完成，状态以进度条格式展示，完成状态回写 Markdown 文件。

**Architecture:** `main.py` 新增 `parse_today()` 和 `write_task_done()` 两个纯函数处理 Markdown 读写，三个路由分别提供页面、数据查询和任务更新。前端为单文件 `static/index.html`，使用原生 JS + Fetch，无构建依赖。

**Tech Stack:** FastAPI, Python pathlib, pytest + TestClient（已有），原生 HTML/CSS/JS

## Global Constraints

- Python 3.x，所有文件 UTF-8 编码
- 不改动 `tools.py`、`agent.py`、`notify.py` 的现有逻辑
- 测试用 `monkeypatch` 替换 `SCHEDULE_DIR`，不读写真实 `schedule/` 目录
- 任务 ID 格式：`s{section_idx}-t{task_idx}`（如 `s0-t0`、`s1-t2`）

---

## File Map

| 文件 | 操作 | 职责 |
|---|---|---|
| `main.py` | 修改 | 新增 `parse_today()`、`write_task_done()`、三个路由 |
| `static/index.html` | 新建 | 前端页面，完整单文件 |
| `tests/test_web.py` | 新建 | parse/write 函数 + API 路由测试 |

---

## Task 1: parse_today() — 解析今日 Markdown

**Files:**
- Modify: `main.py`
- Test: `tests/test_web.py`

**Interfaces:**
- Produces:
  ```python
  def parse_today(schedule_dir: Path | None = None) -> dict:
      # schedule_dir 默认为 tools.SCHEDULE_DIR，测试时传 tmp_path
      # 返回:
      # {
      #   "date": "2026-06-18",
      #   "sections": [
      #     {"name": "固定日程", "tasks": [{"id": "s0-t0", "text": "14:00-15:30 学习", "done": False}]},
      #     {"name": "灵活待办", "tasks": [{"id": "s1-t0", "text": "找 GitHub 项目", "done": False}]}
      #   ],
      #   "total": 5,
      #   "done_count": 0
      # }
  ```

- [ ] **Step 1: 在 tests/test_web.py 写第一个失败测试**

```python
# tests/test_web.py
import pytest
from pathlib import Path
from datetime import date


def test_parse_today_returns_structure(tmp_path):
    from main import parse_today

    today = date.today().isoformat()
    (tmp_path / f"{today}.md").write_text(
        "# 日程表\n\n## 固定日程\n- 09:00-10:00 会议\n\n## 灵活待办\n- 写报告（1h，高优先）\n",
        encoding="utf-8"
    )

    result = parse_today(schedule_dir=tmp_path)

    assert result["date"] == today
    assert len(result["sections"]) == 2
    assert result["sections"][0]["name"] == "固定日程"
    assert result["sections"][0]["tasks"][0] == {"id": "s0-t0", "text": "09:00-10:00 会议", "done": False}
    assert result["sections"][1]["name"] == "灵活待办"
    assert result["sections"][1]["tasks"][0] == {"id": "s1-t0", "text": "写报告（1h，高优先）", "done": False}
    assert result["total"] == 2
    assert result["done_count"] == 0
```

- [ ] **Step 2: 运行确认失败**

```bash
cd /Users/yxlh/Documents/morning-agent
python -m pytest tests/test_web.py::test_parse_today_returns_structure -v
```

预期：`ImportError` 或 `AttributeError: module 'main' has no attribute 'parse_today'`

- [ ] **Step 3: 在 main.py 顶部新增 import 和 parse_today 实现**

在 `main.py` 文件顶部（`import asyncio` 之后）加入：

```python
from pathlib import Path
from datetime import date as _date
from tools import SCHEDULE_DIR as _DEFAULT_SCHEDULE_DIR


def parse_today(schedule_dir: Path | None = None) -> dict:
    directory = schedule_dir if schedule_dir is not None else _DEFAULT_SCHEDULE_DIR
    today = _date.today().isoformat()
    filepath = directory / f"{today}.md"

    if not filepath.exists():
        return {"date": today, "sections": [], "total": 0, "done_count": 0}

    content = filepath.read_text(encoding="utf-8")
    sections: list[dict] = []
    current_section: dict | None = None

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
```

- [ ] **Step 4: 写三个额外测试场景**

在 `tests/test_web.py` 中追加：

```python
def test_parse_today_no_file(tmp_path):
    from main import parse_today

    result = parse_today(schedule_dir=tmp_path)

    assert result["date"] == _date.today().isoformat()
    assert result["sections"] == []
    assert result["total"] == 0
    assert result["done_count"] == 0


def test_parse_today_with_checked_items(tmp_path):
    from main import parse_today

    today = _date.today().isoformat()
    (tmp_path / f"{today}.md").write_text(
        "## 灵活待办\n- [x] 完成的任务\n- [ ] 未完成的任务\n",
        encoding="utf-8"
    )

    result = parse_today(schedule_dir=tmp_path)

    tasks = result["sections"][0]["tasks"]
    assert tasks[0] == {"id": "s0-t0", "text": "完成的任务", "done": True}
    assert tasks[1] == {"id": "s0-t1", "text": "未完成的任务", "done": False}
    assert result["total"] == 2
    assert result["done_count"] == 1


def test_parse_today_skips_empty_dashes(tmp_path):
    from main import parse_today

    today = _date.today().isoformat()
    (tmp_path / f"{today}.md").write_text(
        "## 固定日程\n-\n- \n- 09:00-10:00 会议\n",
        encoding="utf-8"
    )

    result = parse_today(schedule_dir=tmp_path)

    assert result["total"] == 1
    assert result["sections"][0]["tasks"][0]["text"] == "09:00-10:00 会议"
```

在文件顶部加上缺少的 import（如果还没有）：

```python
from datetime import date as _date
```

- [ ] **Step 5: 运行全部测试确认通过**

```bash
python -m pytest tests/test_web.py -v -k "parse"
```

预期：4 个 PASS

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_web.py
git commit -m "feat: add parse_today() for markdown schedule parsing"
```

---

## Task 2: write_task_done() — 回写完成状态到 Markdown

**Files:**
- Modify: `main.py`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: `parse_today(schedule_dir)` — Task 1 产出
- Produces:
  ```python
  def write_task_done(task_id: str, done: bool, schedule_dir: Path | None = None) -> dict:
      # task_id 格式 "s{si}-t{ti}"，找到对应行改写后返回 parse_today() 结果
  ```

- [ ] **Step 1: 写失败测试**

在 `tests/test_web.py` 追加：

```python
def test_write_task_done_marks_checked(tmp_path):
    from main import write_task_done

    today = _date.today().isoformat()
    (tmp_path / f"{today}.md").write_text(
        "## 灵活待办\n- 找项目（1h）\n- Boss 找实习\n",
        encoding="utf-8"
    )

    result = write_task_done("s0-t1", True, schedule_dir=tmp_path)

    content = (tmp_path / f"{today}.md").read_text(encoding="utf-8")
    assert "- [x] Boss 找实习" in content
    assert "- 找项目（1h）" in content or "- [ ] 找项目（1h）" in content
    assert result["sections"][0]["tasks"][1]["done"] is True
    assert result["done_count"] == 1
```

- [ ] **Step 2: 运行确认失败**

```bash
python -m pytest tests/test_web.py::test_write_task_done_marks_checked -v
```

预期：`AttributeError: module 'main' has no attribute 'write_task_done'`

- [ ] **Step 3: 在 main.py 中实现 write_task_done（接在 parse_today 之后）**

```python
def write_task_done(task_id: str, done: bool, schedule_dir: Path | None = None) -> dict:
    directory = schedule_dir if schedule_dir is not None else _DEFAULT_SCHEDULE_DIR
    today = _date.today().isoformat()
    filepath = directory / f"{today}.md"

    parts = task_id.split("-")
    target_si, target_ti = int(parts[0][1:]), int(parts[1][1:])

    lines = filepath.read_text(encoding="utf-8").splitlines(keepends=True)
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
                if raw.startswith("[x] ") or raw.startswith("[ ] "):
                    text = raw[4:]
                else:
                    text = raw
                marker = "[x]" if done else "[ ]"
                lines[i] = f"- {marker} {text}\n"
                break

    filepath.write_text("".join(lines), encoding="utf-8")
    return parse_today(schedule_dir=directory)
```

- [ ] **Step 4: 写额外测试（取消勾选 + 原本无 checkbox 的行）**

```python
def test_write_task_done_unmarks_checked(tmp_path):
    from main import write_task_done

    today = _date.today().isoformat()
    (tmp_path / f"{today}.md").write_text(
        "## 固定日程\n- [x] 09:00-10:00 会议\n",
        encoding="utf-8"
    )

    result = write_task_done("s0-t0", False, schedule_dir=tmp_path)

    content = (tmp_path / f"{today}.md").read_text(encoding="utf-8")
    assert "- [ ] 09:00-10:00 会议" in content
    assert result["sections"][0]["tasks"][0]["done"] is False


def test_write_task_done_two_sections(tmp_path):
    from main import write_task_done

    today = _date.today().isoformat()
    (tmp_path / f"{today}.md").write_text(
        "## 固定日程\n- 09:00-10:00 会议\n\n## 灵活待办\n- 写报告\n- 阅读论文\n",
        encoding="utf-8"
    )

    result = write_task_done("s1-t1", True, schedule_dir=tmp_path)

    content = (tmp_path / f"{today}.md").read_text(encoding="utf-8")
    assert "- [x] 阅读论文" in content
    assert "- 写报告" in content or "- [ ] 写报告" in content
    assert result["done_count"] == 1
```

- [ ] **Step 5: 运行确认通过**

```bash
python -m pytest tests/test_web.py -v -k "write"
```

预期：3 个 PASS

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_web.py
git commit -m "feat: add write_task_done() for checkbox state persistence"
```

---

## Task 3: API 路由 — GET /、GET /api/today、PATCH /api/task/{task_id}

**Files:**
- Modify: `main.py`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: `parse_today()`, `write_task_done()` — Tasks 1–2 产出
- Produces:
  - `GET /` → `FileResponse("static/index.html")`
  - `GET /api/today` → `parse_today()` 返回的 dict（JSON）
  - `PATCH /api/task/{task_id}` body `{"done": bool}` → `write_task_done()` 返回的 dict（JSON）

- [ ] **Step 1: 创建 static 目录和占位 index.html**

```bash
mkdir -p /Users/yxlh/Documents/morning-agent/static
echo "<html><body>placeholder</body></html>" > /Users/yxlh/Documents/morning-agent/static/index.html
```

- [ ] **Step 2: 写 API 路由的失败测试**

在 `tests/test_web.py` 追加：

```python
def test_get_today_api(tmp_path):
    from unittest.mock import patch
    from fastapi.testclient import TestClient

    today = _date.today().isoformat()
    (tmp_path / f"{today}.md").write_text(
        "## 固定日程\n- 09:00-10:00 会议\n",
        encoding="utf-8"
    )

    with patch("main._DEFAULT_SCHEDULE_DIR", tmp_path), \
         patch("main.scheduler"):
        from main import app
        with TestClient(app) as client:
            resp = client.get("/api/today")

    assert resp.status_code == 200
    data = resp.json()
    assert data["date"] == today
    assert data["total"] == 1
    assert data["sections"][0]["tasks"][0]["id"] == "s0-t0"


def test_patch_task_api(tmp_path):
    from unittest.mock import patch
    from fastapi.testclient import TestClient

    today = _date.today().isoformat()
    (tmp_path / f"{today}.md").write_text(
        "## 灵活待办\n- 找项目\n",
        encoding="utf-8"
    )

    with patch("main._DEFAULT_SCHEDULE_DIR", tmp_path), \
         patch("main.scheduler"):
        from main import app
        with TestClient(app) as client:
            resp = client.patch("/api/task/s0-t0", json={"done": True})

    assert resp.status_code == 200
    data = resp.json()
    assert data["sections"][0]["tasks"][0]["done"] is True
    assert data["done_count"] == 1
```

- [ ] **Step 3: 运行确认失败**

```bash
python -m pytest tests/test_web.py -v -k "api"
```

预期：404 或路由不存在

- [ ] **Step 4: 在 main.py 中新增路由（加在 trigger_review_manually 之后）**

先在顶部 import 区加入：
```python
from fastapi.responses import FileResponse
from pydantic import BaseModel
```

然后加入 `BASE_DIR` 常量和三个路由：

```python
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
async def update_task(task_id: str, body: _TaskUpdate):
    return write_task_done(task_id, body.done)
```

- [ ] **Step 5: 运行测试确认通过**

```bash
python -m pytest tests/test_web.py -v
```

预期：全部 PASS

- [ ] **Step 6: Commit**

```bash
git add main.py static/index.html tests/test_web.py
git commit -m "feat: add /api/today and /api/task routes with progress page scaffold"
```

---

## Task 4: 前端页面 static/index.html

**Files:**
- Modify: `static/index.html`（覆盖 Task 3 的占位内容）

**Interfaces:**
- Consumes:
  - `GET /api/today` → `{"date", "sections": [{"name", "tasks": [{"id", "text", "done"}]}], "total", "done_count"}`
  - `PATCH /api/task/{id}` body `{"done": bool}` → 同上结构

- [ ] **Step 1: 写完整 index.html**

将 `static/index.html` 替换为以下完整内容：

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
    .date-header { margin-bottom: 16px; }
    .date-header h1 { font-size: 1.4rem; color: #222; }
    .date-header p { font-size: 0.85rem; color: #999; margin-top: 2px; }
    .card {
      background: white; border-radius: 12px; padding: 20px;
      margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    .card-header {
      display: flex; justify-content: space-between;
      align-items: center; margin-bottom: 10px;
    }
    .card-title { font-size: 1rem; font-weight: 600; color: #333; }
    .count-label { font-size: 0.85rem; color: #999; }
    .bar-wrap { height: 10px; background: #ebebeb; border-radius: 5px; overflow: hidden; }
    .bar-fill {
      height: 100%; border-radius: 5px;
      background: #5b8def; transition: width 0.3s ease;
    }
    .bar-fill.overall { background: #5b8def; }
    .bar-fill.complete { background: #52c47a; }
    .done-msg {
      text-align: center; padding-top: 8px;
      font-size: 0.9rem; color: #52c47a; font-weight: 500;
    }
    .section-card { background: white; border-radius: 12px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
    .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
    .section-title { font-size: 0.95rem; font-weight: 600; color: #444; }
    .mini-progress { display: flex; align-items: center; gap: 8px; }
    .mini-bar { width: 72px; height: 6px; background: #ebebeb; border-radius: 3px; overflow: hidden; }
    .mini-fill { height: 100%; border-radius: 3px; background: #5b8def; transition: width 0.3s ease; }
    .mini-count { font-size: 0.78rem; color: #bbb; }
    .task-list { list-style: none; }
    .task-item {
      display: flex; align-items: flex-start; gap: 10px;
      padding: 9px 6px; border-radius: 6px; cursor: pointer;
      transition: background 0.1s;
    }
    .task-item:hover { background: #f7f7f7; }
    .task-item + .task-item { border-top: 1px solid #f2f2f2; }
    .checkbox {
      width: 18px; height: 18px; border: 2px solid #ccc; border-radius: 4px;
      flex-shrink: 0; margin-top: 1px; display: flex; align-items: center;
      justify-content: center; transition: all 0.15s; font-size: 11px; color: white;
    }
    .checkbox.checked { background: #52c47a; border-color: #52c47a; }
    .task-text { font-size: 0.9rem; line-height: 1.45; color: #333; }
    .task-text.done { text-decoration: line-through; color: #bbb; }
    .empty { text-align: center; color: #ccc; padding: 48px 20px; font-size: 0.9rem; line-height: 1.7; }
  </style>
</head>
<body>
  <div class="date-header">
    <h1 id="date-title">—</h1>
    <p id="weekday"></p>
  </div>
  <div id="app"><div class="empty">加载中…</div></div>

  <script>
    const WEEKDAYS = ['周日','周一','周二','周三','周四','周五','周六'];
    let _data = null;

    async function load() {
      const res = await fetch('/api/today');
      _data = await res.json();
      render(_data);
    }

    async function toggle(taskId, currentDone) {
      const res = await fetch('/api/task/' + taskId, {
        method: 'PATCH',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({done: !currentDone})
      });
      _data = await res.json();
      render(_data);
    }

    function bar(pct, extraClass) {
      return `<div class="bar-wrap"><div class="bar-fill ${extraClass}" style="width:${pct}%"></div></div>`;
    }

    function render(data) {
      const d = new Date(data.date + 'T12:00:00');
      document.getElementById('date-title').textContent = data.date;
      document.getElementById('weekday').textContent = WEEKDAYS[d.getDay()];

      const app = document.getElementById('app');

      if (!data.sections || data.sections.length === 0) {
        app.innerHTML = `<div class="empty">今天还没有日程文件<br>请在 schedule/${data.date}.md 中填写</div>`;
        return;
      }

      const pct = data.total > 0 ? Math.round(data.done_count / data.total * 100) : 0;
      const allDone = data.total > 0 && data.done_count === data.total;

      let html = `<div class="card">
        <div class="card-header">
          <span class="card-title">今日进度</span>
          <span class="count-label">${data.done_count} / ${data.total} 完成</span>
        </div>
        ${bar(pct, allDone ? 'overall complete' : 'overall')}
        ${allDone ? '<div class="done-msg">今天的事都做完了 🎉</div>' : ''}
      </div>`;

      for (const section of data.sections) {
        const st = section.tasks.length;
        const sd = section.tasks.filter(t => t.done).length;
        const sp = st > 0 ? Math.round(sd / st * 100) : 0;

        html += `<div class="section-card">
          <div class="section-header">
            <span class="section-title">${section.name}</span>
            <div class="mini-progress">
              <div class="mini-bar"><div class="mini-fill" style="width:${sp}%"></div></div>
              <span class="mini-count">${sd}/${st}</span>
            </div>
          </div>
          <ul class="task-list">`;

        for (const task of section.tasks) {
          html += `<li class="task-item" onclick="toggle('${task.id}',${task.done})">
            <div class="checkbox${task.done ? ' checked' : ''}">
              ${task.done ? '✓' : ''}
            </div>
            <span class="task-text${task.done ? ' done' : ''}">${task.text}</span>
          </li>`;
        }

        html += `</ul></div>`;
      }

      app.innerHTML = html;
    }

    load();
  </script>
</body>
</html>
```

- [ ] **Step 2: 手动验证页面**

启动服务：
```bash
cd /Users/yxlh/Documents/morning-agent
python -m uvicorn main:app --reload
```

打开浏览器访问 `http://localhost:8000`，确认：
- 显示今日日期和星期
- 列出 `schedule/2026-06-18.md` 中的任务（2 条固定日程 + 3 条灵活待办）
- 顶部有整体进度条，每个分组有小进度条
- 点击任务可以勾选/取消，进度条实时更新
- 全部完成后显示 🎉 提示

- [ ] **Step 3: 运行完整测试套件确认无回归**

```bash
python -m pytest tests/ -v
```

预期：全部原有测试 + 新增测试均 PASS

- [ ] **Step 4: Commit**

```bash
git add static/index.html
git commit -m "feat: add frontend progress page with task checklist and progress bars"
```

---

## 验收标准

1. `python -m pytest tests/ -v` 全绿
2. 启动服务后 `http://localhost:8000` 能展示今日日程
3. 勾选任务后进度条更新，刷新页面状态保持（已写入 Markdown）
4. `schedule/2026-06-18.md` 勾选后行格式变为 `- [x] text`
