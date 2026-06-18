---
name: frontend-progress-page
description: 为 morning-agent 增加前端进度页面，展示今日任务与勾选完成进度
metadata:
  type: project
---

# 前端进度页面设计

**背景**：早晨电脑未开机时 morning-agent 无法自动推送日程，用户需要一个可随时打开的页面查看今天要做什么并手动标记完成进度。

---

## 架构

在现有 FastAPI 应用上新增三个路由和一个静态 HTML 文件，不改动现有逻辑。

```
morning-agent/
├── main.py              ← 新增 3 个路由 + 挂载 static 目录
├── static/
│   └── index.html       ← 前端页面（纯 HTML + 原生 JS）
└── schedule/
    └── YYYY-MM-DD.md    ← 勾选后回写，加 - [x] / - [ ] 格式
```

---

## API 设计

### GET /
返回 `static/index.html`，用 `FileResponse` 直接返回文件。

### GET /api/today
解析当天 Markdown 文件，返回：

```json
{
  "date": "2026-06-18",
  "sections": [
    {
      "name": "固定日程",
      "tasks": [
        {"id": "fixed-0", "text": "14:00-15:30 学习", "done": false},
        {"id": "fixed-1", "text": "19:00-20:00 健身", "done": false}
      ]
    },
    {
      "name": "灵活待办",
      "tasks": [
        {"id": "flex-0", "text": "找 GitHub 项目（2h，高优先）", "done": false},
        {"id": "flex-1", "text": "Boss 找实习（30min）", "done": false},
        {"id": "flex-2", "text": "阅读论文（1h，不急）", "done": false}
      ]
    }
  ],
  "total": 5,
  "done_count": 0
}
```

今日文件不存在时返回空 sections，页面展示提示文案。

### PATCH /api/task/{task_id}
Body: `{"done": true}`

根据 `task_id`（`fixed-0`、`flex-2` 等）定位 Markdown 文件中对应行，将其改写为 `- [x] text` 或 `- [ ] text`，返回更新后的完整数据（同 GET /api/today 格式）。

---

## Markdown 解析规则

- `- [x] text` → done=true
- `- [ ] text` → done=false
- `- text`（无勾选符，当前格式）→ done=false，回写时自动补 `- [ ]`

解析时按 `## 固定日程` 和 `## 灵活待办` 两个 section 分组，忽略其他行（标题行、空行）。

---

## 前端页面

单文件 `static/index.html`，不依赖任何前端框架，内嵌 CSS + JS。

**布局：**
```
┌─────────────────────────────────────┐
│  2026-06-18  今日进度               │
│  ████████░░░░░░  5/8 完成           │
├─────────────────────────────────────┤
│  固定日程          ██████ 2/2       │
│  ☑ 14:00-15:30 学习                │
│  ☑ 19:00-20:00 健身                │
├─────────────────────────────────────┤
│  灵活待办          ███░░░ 3/6       │
│  ☑ 找 GitHub 项目（2h，高优先）     │
│  ☐ Boss 找实习（30min）             │
│  ☐ 阅读论文（1h，不急）             │
└─────────────────────────────────────┘
```

**交互：**
- 勾选复选框 → 立即调用 `PATCH /api/task/{id}` → 用返回数据刷新进度条，无页面刷新
- 页面加载时调用 `GET /api/today` 渲染初始状态
- 全部完成时整体进度条变绿并显示"今天的事都做完了 🎉"

---

## 改动范围

| 文件 | 改动 |
|---|---|
| `main.py` | 新增 `StaticFiles` 挂载 + 3 个路由；新增 `parse_today()` 和 `write_task_done()` 两个工具函数（不放入 tools.py，属于 web 层逻辑） |
| `static/index.html` | 新建 |
| 其余文件 | 不动 |

---

## 不在本次范围内

- AI 排期结果的展示（本次只展示用户写的原始任务列表）
- 历史日期切换
- 移动端适配（基础可用即可）
