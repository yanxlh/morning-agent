# 早晨日程规划 Agent 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个每天早上 7:00 自动触发的 Agent，读取日程 Markdown 文件，通过 GLM-4-Flash 生成排期建议，并同时推送到 Gmail（自发自收）和 Server酱（微信）。

**Architecture:** FastAPI 进程常驻，APScheduler 内嵌定时触发 `morning_review_job`；LangChain Agent（LangGraph `create_react_agent`）持有两个工具（读日程、建明日模板），每次调用完整走一轮 ReAct 循环；通知发送使用 `asyncio.gather` 并发，互不阻塞。

**Tech Stack:** Python 3.11+, FastAPI, APScheduler, LangChain, LangGraph, langchain-zhipuai (GLM-4-Flash), aiosmtplib, httpx, python-dotenv, pytest, pytest-asyncio

---

## 文件结构

| 路径 | 职责 |
|---|---|
| `requirements.txt` | 依赖声明 |
| `.env.example` | 环境变量模板（含注册说明） |
| `.gitignore` | 排除 `.env`、`schedule/`、`__pycache__` |
| `tools.py` | 两个 LangChain Tool：读今日日程、创建明日模板 |
| `notify.py` | Gmail SMTP 推送 + Server酱 HTTP 推送 |
| `agent.py` | LangGraph Agent 定义（GLM-4-Flash + system prompt） |
| `main.py` | FastAPI app + APScheduler + `morning_review_job` |
| `tests/test_tools.py` | tools.py 单元测试 |
| `tests/test_notify.py` | notify.py 单元测试（mock 外部服务） |
| `tests/test_main.py` | main.py 集成测试（mock agent + notify） |
| `schedule/` | 日程 Markdown 文件目录（运行时自动创建） |

---

## Task 1: 项目骨架与依赖

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `pytest.ini`

- [ ] **Step 1: 进入项目目录并初始化 git**

```bash
cd /Users/yxlh/Documents/morning-agent
git init
```

Expected: `Initialized empty Git repository in .../morning-agent/.git/`

- [ ] **Step 2: 创建 `requirements.txt`**

```
langchain>=0.3.0
langchain-core>=0.3.0
langchain-zhipuai>=0.2.0
langgraph>=0.2.0
apscheduler>=3.10.0
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
aiosmtplib>=3.0.0
httpx>=0.27.0
python-dotenv>=1.0.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

- [ ] **Step 3: 创建 `.env.example`**

```bash
# 智谱 AI API Key（GLM-4-Flash 永久免费）
# 注册地址：https://open.bigmodel.cn → 登录 → 右上角「API Keys」→ 新建密钥
ZHIPUAI_API_KEY=your_zhipuai_api_key_here

# Gmail 地址（发件人和收件人均为此地址，自发自收）
GMAIL_ADDRESS=your_gmail@gmail.com

# Gmail 应用专用密码（注意：不是登录密码）
# 获取方式：Google 账号 → 安全性 → 两步验证（需先开启）→ 应用专用密码 → 选择「邮件」→ 生成
SMTP_PASSWORD=your_gmail_app_password_here

# Server酱 SendKey（免费，扫码登录即可）
# 注册地址：https://sct.ftqq.com → 微信扫码登录 → 复制 SendKey
SERVERCHAN_KEY=your_serverchan_sendkey_here
```

- [ ] **Step 4: 创建 `.gitignore`**

```
.env
__pycache__/
*.pyc
.pytest_cache/
schedule/
```

- [ ] **Step 5: 创建 `pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 6: 安装依赖**

```bash
pip install -r requirements.txt
```

Expected: 所有包安装成功，无报错

- [ ] **Step 7: 初始提交**

```bash
git add requirements.txt .env.example .gitignore pytest.ini
git commit -m "chore: project scaffold"
```

---

## Task 2: tools.py — 日程文件操作

**Files:**
- Create: `tools.py`
- Create: `tests/__init__.py`
- Create: `tests/test_tools.py`

- [ ] **Step 1: 写失败测试（今日文件存在时返回内容）**

创建 `tests/__init__.py`（空文件），然后创建 `tests/test_tools.py`：

```python
import pytest
from datetime import date, timedelta
from pathlib import Path


def test_get_today_schedule_returns_file_content(tmp_path, monkeypatch):
    import tools
    monkeypatch.setattr(tools, "SCHEDULE_DIR", tmp_path)

    today_file = tmp_path / f"{date.today().isoformat()}.md"
    today_file.write_text("# 测试日程\n## 固定日程\n- 09:00-10:00 会议", encoding="utf-8")

    result = tools.get_today_schedule.invoke({})
    assert "测试日程" in result
    assert "09:00-10:00 会议" in result


def test_get_today_schedule_missing_returns_guidance(tmp_path, monkeypatch):
    import tools
    monkeypatch.setattr(tools, "SCHEDULE_DIR", tmp_path)

    result = tools.get_today_schedule.invoke({})
    assert date.today().isoformat() in result
    assert "schedule/" in result
    assert "固定日程" in result
    assert "灵活待办" in result
    # 应包含星期提示
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    assert any(w in result for w in weekday_names)


def test_create_tomorrow_template_creates_file(tmp_path, monkeypatch):
    import tools
    monkeypatch.setattr(tools, "SCHEDULE_DIR", tmp_path)

    tomorrow = date.today() + timedelta(days=1)
    result = tools.create_tomorrow_template.invoke({})

    assert tomorrow.isoformat() in result
    assert (tmp_path / f"{tomorrow.isoformat()}.md").exists()
    content = (tmp_path / f"{tomorrow.isoformat()}.md").read_text(encoding="utf-8")
    assert "固定日程" in content
    assert "灵活待办" in content


def test_create_tomorrow_template_no_overwrite(tmp_path, monkeypatch):
    import tools
    monkeypatch.setattr(tools, "SCHEDULE_DIR", tmp_path)

    tomorrow = date.today() + timedelta(days=1)
    existing = tmp_path / f"{tomorrow.isoformat()}.md"
    existing.write_text("已有内容", encoding="utf-8")

    result = tools.create_tomorrow_template.invoke({})
    assert "已经存在" in result
    assert existing.read_text(encoding="utf-8") == "已有内容"
```

- [ ] **Step 2: 运行测试，确认全部失败**

```bash
cd /Users/yxlh/Documents/morning-agent
pytest tests/test_tools.py -v
```

Expected: `ImportError: No module named 'tools'`（或类似报错）

- [ ] **Step 3: 实现 `tools.py`**

```python
from pathlib import Path
from datetime import date, timedelta
from langchain_core.tools import tool

SCHEDULE_DIR = Path("schedule")
SCHEDULE_DIR.mkdir(exist_ok=True)

_WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


@tool
def get_today_schedule() -> str:
    """读取今天的日程表文件，包含固定日程和灵活待办事项。文件不存在时返回填写引导。"""
    today = date.today()
    today_file = SCHEDULE_DIR / f"{today.isoformat()}.md"

    if not today_file.exists():
        weekday = _WEEKDAY_NAMES[today.weekday()]
        return (
            f"今天（{today.isoformat()}，{weekday}）还没有日程文件。\n"
            f"请在 schedule/{today.isoformat()}.md 中按以下格式添加：\n\n"
            f"# {today.isoformat()} 日程表\n\n"
            f"## 固定日程\n- HH:MM-HH:MM 事项名称\n\n"
            f"## 灵活待办\n- 任务描述（预计X小时，优先级高/中/低）\n\n"
            f"提示：今天是{weekday}，想想是否有例会、固定课程或其他常规安排？"
        )

    return today_file.read_text(encoding="utf-8")


@tool
def create_tomorrow_template() -> str:
    """生成明天的日程文件模板，文件已存在则不覆盖。"""
    tomorrow = date.today() + timedelta(days=1)
    tomorrow_file = SCHEDULE_DIR / f"{tomorrow.isoformat()}.md"

    if tomorrow_file.exists():
        return f"{tomorrow.isoformat()} 的日程文件已经存在，未覆盖。"

    template = (
        f"# {tomorrow.isoformat()} 日程表\n\n"
        f"## 固定日程\n-\n\n"
        f"## 灵活待办\n-\n"
    )
    tomorrow_file.write_text(template, encoding="utf-8")
    return f"已创建 {tomorrow.isoformat()} 的日程模板，晚上直接填空即可。"
```

- [ ] **Step 4: 运行测试，确认全部通过**

```bash
pytest tests/test_tools.py -v
```

Expected:
```
PASSED tests/test_tools.py::test_get_today_schedule_returns_file_content
PASSED tests/test_tools.py::test_get_today_schedule_missing_returns_guidance
PASSED tests/test_tools.py::test_create_tomorrow_template_creates_file
PASSED tests/test_tools.py::test_create_tomorrow_template_no_overwrite
```

- [ ] **Step 5: 提交**

```bash
git add tools.py tests/__init__.py tests/test_tools.py
git commit -m "feat: add schedule file tools with tests"
```

---

## Task 3: notify.py — 推送通知

**Files:**
- Create: `notify.py`
- Create: `tests/test_notify.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_send_email_calls_smtp(monkeypatch):
    monkeypatch.setenv("GMAIL_ADDRESS", "test@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "test_password")

    with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        from notify import send_email
        await send_email("今天排期建议")

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        # 验证连接参数
        assert call_kwargs.kwargs["hostname"] == "smtp.gmail.com"
        assert call_kwargs.kwargs["port"] == 587
        assert call_kwargs.kwargs["username"] == "test@gmail.com"
        assert call_kwargs.kwargs["password"] == "test_password"
        assert call_kwargs.kwargs["start_tls"] is True
        # 验证邮件内容
        msg = call_kwargs.args[0]
        assert msg["Subject"] == "今日计划提醒"
        assert msg["From"] == "test@gmail.com"
        assert msg["To"] == "test@gmail.com"


@pytest.mark.asyncio
async def test_send_wechat_message_calls_serverchan(monkeypatch):
    monkeypatch.setenv("SERVERCHAN_KEY", "test_key_123")

    mock_response = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        from notify import send_wechat_message
        await send_wechat_message("今天排期建议")

        mock_client.post.assert_called_once_with(
            "https://sctapi.ftqq.com/test_key_123.send",
            data={"title": "今日计划提醒", "desp": "今天排期建议"},
        )
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_notify.py -v
```

Expected: `ImportError: No module named 'notify'`

- [ ] **Step 3: 实现 `notify.py`**

```python
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
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_notify.py -v
```

Expected:
```
PASSED tests/test_notify.py::test_send_email_calls_smtp
PASSED tests/test_notify.py::test_send_wechat_message_calls_serverchan
```

- [ ] **Step 5: 提交**

```bash
git add notify.py tests/test_notify.py
git commit -m "feat: add Gmail and Server酱 push notifications with tests"
```

---

## Task 4: agent.py — LangChain Agent

**Files:**
- Create: `agent.py`
- Create: `tests/test_agent.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_agent_invoke_returns_string(monkeypatch):
    monkeypatch.setenv("ZHIPUAI_API_KEY", "fake_key")

    mock_llm = MagicMock()
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)

    fake_message = MagicMock()
    fake_message.content = "今天安排如下：上午处理文档，下午参加会议。"

    with patch("langchain_zhipuai.ChatZhipuAI", return_value=mock_llm):
        from agent import SYSTEM_PROMPT
        # 验证 system prompt 包含关键约束
        assert "固定日程" in SYSTEM_PROMPT
        assert "250字" in SYSTEM_PROMPT
        assert "Markdown" in SYSTEM_PROMPT


def test_agent_module_exports_agent(monkeypatch):
    monkeypatch.setenv("ZHIPUAI_API_KEY", "fake_key")

    import importlib
    import agent as agent_module
    assert hasattr(agent_module, "agent")
    assert hasattr(agent_module, "SYSTEM_PROMPT")
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_agent.py -v
```

Expected: `ImportError: No module named 'agent'`

- [ ] **Step 3: 实现 `agent.py`**

```python
import os
from dotenv import load_dotenv
from langchain_zhipuai import ChatZhipuAI
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent

from tools import get_today_schedule, create_tomorrow_template

load_dotenv()

SYSTEM_PROMPT = """你是一个早晨日程规划助手。每天早上：

1. 调用工具读取今天的日程表（分"固定日程"和"灵活待办"两部分）
2. "固定日程"是不能改变的时间块，必须严格保留
3. "灵活待办"需要你安排到固定日程之间的空隙里，按优先级和预计耗时合理排序
4. 检查是否有时间冲突或安排过满的情况，如果有要提醒
5. 如果今天没有日程文件，告知用户并引导创建，结合星期几给出思考提示
6. 调用工具生成明天的日程模板文件，方便用户晚上填空
7. 给用户的回复是纯文本，会直接发送到邮件和手机消息，不要用任何Markdown符号（不要用#、**、-列表等），用自然的换行分段
8. 语气直接友好，不要说教，控制在250字以内"""

llm = ChatZhipuAI(
    model="glm-4-flash",
    api_key=os.environ.get("ZHIPUAI_API_KEY", ""),
)

agent = create_react_agent(
    model=llm,
    tools=[get_today_schedule, create_tomorrow_template],
    state_modifier=SystemMessage(content=SYSTEM_PROMPT),
)
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_agent.py -v
```

Expected:
```
PASSED tests/test_agent.py::test_agent_invoke_returns_string
PASSED tests/test_agent.py::test_agent_module_exports_agent
```

- [ ] **Step 5: 提交**

```bash
git add agent.py tests/test_agent.py
git commit -m "feat: add LangChain agent with GLM-4-Flash and system prompt"
```

---

## Task 5: main.py — FastAPI + APScheduler

**Files:**
- Create: `main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_morning_review_job_sends_both_notifications(monkeypatch):
    monkeypatch.setenv("ZHIPUAI_API_KEY", "fake_key")
    monkeypatch.setenv("GMAIL_ADDRESS", "test@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    monkeypatch.setenv("SERVERCHAN_KEY", "key")

    fake_msg = MagicMock()
    fake_msg.content = "今天安排：上午写文档，下午开会。"
    fake_result = {"messages": [fake_msg]}

    # patch main 模块的命名空间（而非原始模块），因为 main.py 用 from ... import 引入
    with patch("main.agent") as mock_agent, \
         patch("main.send_email", new_callable=AsyncMock) as mock_email, \
         patch("main.send_wechat_message", new_callable=AsyncMock) as mock_wx:

        mock_agent.ainvoke = AsyncMock(return_value=fake_result)

        from main import morning_review_job
        await morning_review_job()

        mock_agent.ainvoke.assert_called_once()
        mock_email.assert_called_once_with("今天安排：上午写文档，下午开会。")
        mock_wx.assert_called_once_with("今天安排：上午写文档，下午开会。")


def test_trigger_review_http_endpoint():
    # mock scheduler 避免 APScheduler 在测试中实际启动
    with patch("main.morning_review_job", new_callable=AsyncMock) as mock_job, \
         patch("main.scheduler") as mock_scheduler:

        from main import app
        # with 语句触发 lifespan（startup/shutdown）
        with TestClient(app) as client:
            response = client.post("/trigger-review")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        mock_job.assert_called_once()
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_main.py -v
```

Expected: `ImportError: No module named 'main'`

- [ ] **Step 3: 实现 `main.py`**

```python
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
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_main.py -v
```

Expected:
```
PASSED tests/test_main.py::test_trigger_review_endpoint_returns_ok
PASSED tests/test_main.py::test_trigger_review_http_endpoint
```

- [ ] **Step 5: 运行全部测试确认无回归**

```bash
pytest -v
```

Expected: 所有测试通过，无 FAILED

- [ ] **Step 6: 提交**

```bash
git add main.py tests/test_main.py
git commit -m "feat: add FastAPI app with APScheduler and trigger endpoint"
```

---

## Task 6: 环境配置与冒烟测试

**Files:**
- Create: `.env`（从 `.env.example` 复制后填写真实值）
- Create: `schedule/YYYY-MM-DD.md`（今日日程示例）

- [ ] **Step 1: 从模板创建 `.env` 并填写真实值**

```bash
cp .env.example .env
```

打开 `.env`，按文件内注释说明填写：
- `ZHIPUAI_API_KEY`：前往 https://open.bigmodel.cn 注册后在「API Keys」页面创建
- `GMAIL_ADDRESS`：你的 Gmail 地址
- `SMTP_PASSWORD`：Google 账号 → 安全性 → 两步验证 → 应用专用密码 → 生成
- `SERVERCHAN_KEY`：前往 https://sct.ftqq.com 微信扫码登录后复制 SendKey

- [ ] **Step 2: 创建今日日程示例文件**

将下面内容保存为 `schedule/今日日期.md`（文件名替换为实际日期，如 `schedule/2026-06-17.md`）：

```markdown
# 2026-06-17 日程表

## 固定日程
- 09:00-10:00 团队晨会
- 14:00-15:30 需求评审
- 19:00-20:00 健身

## 灵活待办
- 完成接口文档（预计2小时，优先级高）
- 回复客户邮件（预计30分钟）
- 阅读论文（预计1小时，不急）
```

- [ ] **Step 3: 启动服务**

```bash
uvicorn main:app --reload
```

Expected 日志中出现：
```
INFO:     Application startup complete.
```

- [ ] **Step 4: 手动触发验证**

新开一个终端：

```bash
curl -X POST http://localhost:8000/trigger-review
```

Expected: `{"status":"ok"}`

同时检查：
1. Gmail 收件箱收到主题为「今日计划提醒」的邮件
2. 微信收到 Server酱 推送消息
3. 服务终端日志无报错

- [ ] **Step 5: 最终提交**

```bash
git add .
git commit -m "feat: complete morning agent — ready for daily use"
```

---

## 注意事项

**langgraph `state_modifier` 兼容性**：如果启动时报 `TypeError: create_react_agent() got an unexpected keyword argument 'state_modifier'`，将 `agent.py` 中的 `state_modifier=SystemMessage(content=SYSTEM_PROMPT)` 改为 `prompt=SYSTEM_PROMPT`（langgraph >= 0.2.28 使用 `prompt`）。

**Gmail 应用专用密码**：两步验证未开启时，Google 不会显示「应用专用密码」选项，必须先开启两步验证。

**进程持久化**：当前使用 APScheduler 内存 job store，Mac 重启后需手动再次运行 `uvicorn main:app`。如需开机自启，可配置 macOS launchd（不在本期范围）。
