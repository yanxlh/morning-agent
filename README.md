# 早晨日程规划 Agent

每天早上 7:00 自动读取你的日程文件，调用 AI 生成排期建议，通过微信（Server酱）推送到手机。同时提供一个网页，随时查看今日任务和完成进度。

---

## 工作原理

```
每天 7:00 自动触发
  → 读取 schedule/今日.md
  → GLM-4-Flash 分析固定日程 + 灵活待办，生成排期建议
  → 顺手创建明天的日程模板文件
  → 微信推送给你

浏览器打开 http://localhost:8000
  → 展示今日任务列表
  → 勾选完成进度（实时进度条）
  → 完成状态写回日程文件
```

---

## 项目结构

```
morning-agent/
├── .env                # 你的 API Key（不提交 git）
├── .env.example        # 配置模板，含注册说明
├── main.py             # 启动入口，定时任务 + API 路由
├── agent.py            # AI Agent 逻辑
├── tools.py            # 读日程、建明日模板
├── notify.py           # Server酱微信推送
├── static/
│   └── index.html      # 今日进度前端页面
└── schedule/           # 日程文件目录
    ├── 2026-06-18.md   # 今天的日程（早上被读取）
    └── 2026-06-19.md   # Agent 自动生成的明天模板
```

---

## 日程文件格式

文件名：`schedule/YYYY-MM-DD.md`

```markdown
# 2026-06-18 日程表

## 固定日程
- 14:00-15:30 学习
- 19:00-20:00 健身

## 灵活待办
- 学习新知识在 GitHub 找合适的项目（预计2小时，优先级高）
- Boss 直聘找实习（预计30分钟）
- 阅读论文（预计1小时，不急）
```

- **固定日程**：不能改变的时间块，AI 会严格保留
- **灵活待办**：AI 按优先级和预计耗时插空安排，标注"优先级高/中/低"和预计耗时效果最好

---

## 配置说明（.env）

复制 `.env.example` 为 `.env`，填入你的 Key：

```bash
ZHIPUAI_API_KEY=xxx    # 智谱 AI Key，免费：https://open.bigmodel.cn
GMAIL_ADDRESS=xxx      # Gmail 地址（发件人和收件人均为此地址）
SMTP_PASSWORD=xxx      # Gmail 应用专用密码
SERVERCHAN_KEY=xxx     # Server酱 Key，免费：https://sct.ftqq.com
```

**获取 ZHIPUAI_API_KEY：**
1. 前往 https://open.bigmodel.cn 注册
2. 右上角「API Keys」→ 新建密钥
3. GLM-4-Flash 永久免费，无需付费

**获取 SERVERCHAN_KEY：**
1. 前往 https://sct.ftqq.com
2. 微信扫码登录
3. 复制页面上的 SendKey

---

## 安装依赖

```bash
pip3 install -r requirements.txt
```

---

## 启动方式

```bash
cd /path/to/morning-agent
python3 -m uvicorn main:app --reload
```

启动后：
- Agent 每天早上 7:00 自动运行，微信推送排期建议
- 浏览器打开 `http://localhost:8000` 查看今日任务进度

**手动触发 AI 排期（调试用）：**

```bash
curl -X POST http://localhost:8000/trigger-review
```

---

## 前端进度页面

打开 `http://localhost:8000`，页面展示今日所有任务，支持勾选完成：

- 顶部整体进度条（已完成 / 总数）
- 每个分组（固定日程 / 灵活待办）各有一条进度条
- 点击任务勾选，进度条实时更新
- 完成状态写回日程文件（`- [x] 任务名`）
- 刷新页面后状态保持

---

## API 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 前端进度页面 |
| GET | `/api/today` | 获取今日任务 JSON |
| PATCH | `/api/task/{id}` | 更新任务完成状态 |
| POST | `/trigger-review` | 手动触发 AI 排期 |

---

## 日常使用流程

1. **每晚**：打开 `schedule/明日日期.md`（Agent 已自动创建），填写明天的固定日程和灵活待办
2. **每早 7:00**：微信收到今日排期建议
3. **打开浏览器** `http://localhost:8000`：查看任务列表，完成一项勾一项

---

## 注意事项

- Mac 重启后需要重新运行启动命令，进程不会自动恢复
- 如果当天没有日程文件，Agent 会在微信消息里提醒你创建，并给出格式示例
- 灵活待办里写清楚「预计时长」和「优先级」，AI 排期质量会明显更好
- 免费额度按天重置，每天一次调用完全够用

---

## 后续可扩展

- 接入 Google Calendar，自动同步固定日程，无需手动填写
- 增加历史复盘，检测连续多天被推迟的任务并提醒
- 加入天气信息，影响出行安排时自动提示
