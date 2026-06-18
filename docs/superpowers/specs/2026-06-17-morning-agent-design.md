# 早晨日程规划 Agent — 设计文档

**日期：** 2026-06-17  
**项目路径：** `/Users/yxlh/Documents/morning-agent`

---

## 1. 概述

每天早上 7:00 定时触发一个 Agent，读取用户的日程表（Markdown 文件），通过 GLM-4-Flash 分析固定日程和灵活待办，生成合理的排期建议，同时顺手创建明天的日程模板。结果通过 Gmail 自发自收 + Server酱微信推送通知用户。

---

## 2. 技术栈

| 模块 | 选型 |
|---|---|
| Web 框架 | FastAPI |
| 定时任务 | APScheduler（AsyncIOScheduler） |
| Agent 框架 | LangChain（`create_agent`） |
| LLM | 智谱 GLM-4-Flash（永久免费） |
| 邮件推送 | Gmail SMTP（aiosmtplib，自发自收） |
| 微信推送 | Server酱（httpx） |
| 环境变量 | python-dotenv |

---

## 3. 项目结构

```
morning-agent/
├── .env                    # 实际环境变量（不提交 git）
├── .env.example            # 变量模板，含注册获取方式说明
├── main.py                 # FastAPI 入口 + APScheduler 定时任务
├── agent.py                # LangChain Agent 定义
├── tools.py                # 工具：读今日日程、生成明日模板
├── notify.py               # Gmail + Server酱推送
└── schedule/               # 日程 Markdown 文件目录（自动创建）
```

---

## 4. 数据流

```
每天 7:00（或 POST /trigger-review 手动触发）
  │
  ▼
morning_review_job()
  │
  ├─→ agent.ainvoke({"messages": [用户指令]})
  │       │
  │       ├─→ [工具] get_today_schedule()
  │       │       读取 schedule/今日.md
  │       │       文件不存在时返回带格式引导和星期提示的提醒文本
  │       │
  │       ├─→ GLM-4-Flash 分析排期，生成纯文本建议（≤250字）
  │       │
  │       └─→ [工具] create_tomorrow_template()
  │               创建 schedule/明日.md 空白模板（已存在则跳过）
  │
  ├─→ send_email(advice_text)       # Gmail 自发自收
  └─→ send_wechat_message(text)     # Server酱推送到微信
       （两者并发执行，互不影响）
```

---

## 5. 关键设计决策

### 5.1 今日日程文件不存在时的处理

`get_today_schedule()` 返回以下格式的引导文本（而非报错）：

```
今天（YYYY-MM-DD）还没有日程文件。
请在 schedule/YYYY-MM-DD.md 中按以下格式添加：

# YYYY-MM-DD 日程表

## 固定日程
- HH:MM-HH:MM 事项名称

## 灵活待办
- 任务描述（预计X小时，优先级高/中/低）
```

LLM 收到后，推送消息里包含：
1. 告知今日无日程文件
2. 引导按格式创建
3. 结合星期几，提示用户思考常规安排

### 5.2 推送内容格式

Agent system prompt 要求输出纯文本（无 `#`、`**` 等 Markdown 符号），直接适配邮件正文和微信消息显示，字数控制在 250 字以内。

### 5.3 错误处理

- `morning_review_job` 整体 `try/except`，失败打印日志
- 邮件和 Server酱 各自独立 `try/except`，互不干扰
- APScheduler 注册 `EVENT_JOB_ERROR` 监听器

---

## 6. 环境变量

`.env.example`：

```bash
# 智谱 AI API Key（GLM-4-Flash 永久免费）
# 注册：https://open.bigmodel.cn → 登录 → 右上角「API Keys」→ 新建
ZHIPUAI_API_KEY=your_zhipuai_api_key_here

# Gmail 应用专用密码（非登录密码）
# 获取：Google 账号 → 安全性 → 两步验证 → 应用专用密码 → 生成
# 发件人和收件人均为此地址（自发自收）
GMAIL_ADDRESS=your_gmail@gmail.com
SMTP_PASSWORD=your_gmail_app_password_here

# Server酱 SendKey（免费，微信扫码登录）
# 注册：https://sct.ftqq.com → 登录 → SendKey
SERVERCHAN_KEY=your_serverchan_sendkey_here
```

---

## 7. 启动与调试

```bash
# 安装依赖
pip install langchain langchain-zhipuai apscheduler fastapi \
    "uvicorn[standard]" aiosmtplib httpx python-dotenv

# 启动服务
uvicorn main:app --reload

# 手动触发（不用等 7:00）
curl -X POST http://localhost:8000/trigger-review
```

---

## 8. 不在本期范围内

- Google Calendar / Notion API 接入（文档已说明后续可扩展，仅替换 `get_today_schedule` 实现）
- 多实例部署 / SQLAlchemyJobStore 持久化
- 历史复盘对比（连续推迟任务检测）
