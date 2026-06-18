# 早晨日程规划 Agent

每天早上 7:00 自动读取你的日程文件，调用 AI 生成排期建议，通过微信（Server酱）推送到手机。

---

## 工作原理

```
每天 7:00 自动触发
  → 读取 schedule/今日.md
  → GLM-4-Flash 分析固定日程 + 灵活待办，生成排期建议
  → 顺手创建明天的日程模板文件
  → 微信推送给你
```

---

## 项目结构

```
morning-agent/
├── .env                # 你的 API Key（不提交 git）
├── .env.example        # 配置模板，含注册说明
├── main.py             # 启动入口，定时任务
├── agent.py            # AI Agent 逻辑
├── tools.py            # 读日程、建明日模板
├── notify.py           # Server酱微信推送
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

```bash
ZHIPUAI_API_KEY=xxx    # 智谱 AI Key，免费：https://open.bigmodel.cn
GMAIL_ADDRESS=xxx      # 预留字段，当前未使用
SMTP_PASSWORD=xxx      # 预留字段，当前未使用
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

## 启动方式

```bash
cd /Users/yxlh/Documents/morning-agent
python3 -m uvicorn main:app --reload
```

启动后 Agent 会在每天早上 7:00 自动运行，进程保持运行即可。

**手动触发（调试用）：**

```bash
curl -X POST http://localhost:8000/trigger-review
```

---

## 日常使用流程

1. **每晚**：打开 `schedule/明日日期.md`（Agent 已自动创建），填写明天的固定日程和灵活待办
2. **每早 7:00**：微信收到今日排期建议
3. **按建议执行**，随时可手动触发调整

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
