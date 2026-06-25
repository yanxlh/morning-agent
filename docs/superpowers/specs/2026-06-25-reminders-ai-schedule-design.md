# 时间提醒 + AI 自动安排灵活任务 设计文档

日期：2026-06-25

## 背景

当前系统仅在 7 点推送一次日程建议，之后没有任何时间提醒。用户需要：
1. 到达任务时间时收到提醒（提前 + 准点，双渠道：微信 + 浏览器通知）
2. 灵活待办自动获得时间槽（AI 写回日程文件），而不只是文字建议
3. 提前提醒分钟数可在网页设置

---

## 一、整体架构

### 新增文件

| 文件 | 职责 |
|------|------|
| `config.py` | 读写 `config.json`，提供 `get_config()` / `save_config()` |
| `reminder.py` | 时间解析、APScheduler 提醒调度、SSE 事件队列管理 |

### 修改文件

| 文件 | 改动 |
|------|------|
| `tools.py` | 新增 `assign_flexible_times` LangChain tool |
| `agent.py` | 注册新工具，更新 System Prompt |
| `main.py` | 新增 4 个端点；晨间任务完成后调 `reschedule_reminders` |
| `static/index.html` | SSE 客户端、Notification API、设置面板 |

### 7 点数据流

```
morning_review_job()
  → Agent.ainvoke()
      → [工具] get_today_schedule()          # 读今日文件
      → [工具] assign_flexible_times(json)   # 写回时间槽到 .md
      → GLM-4-Flash 生成文字建议
      → [工具] create_tomorrow_template()    # 建明日模板
  → send_email() + send_wechat_message()     # 推送建议
  → reschedule_reminders(today)              # 重新解析并调度提醒 job
```

### 提醒 job 执行流

```
reminder_job(task_text, time_str, is_early, advance_minutes)
  → send_wechat_message("⏰/🔔 {task_text}...")
  → push_reminder_event({"type":"reminder", "task":..., "time":..., "early":...})
      → 写入所有 _sse_clients 队列
          → 浏览器收到 SSE 事件 → Notification API 弹系统通知
```

---

## 二、数据层

### config.json（项目根目录）

```json
{"advance_minutes": 15}
```

### 时间解析（reminder.py）

所有任务文字（固定日程和灵活待办）用同一正则提取时间：

```
^\s*(\d{2}:\d{2})-(\d{2}:\d{2})\s+(.+)
```

匹配成功则取 `start_time` 调度提醒；不匹配则跳过。

### assign_flexible_times 工具（tools.py）

```python
@tool
def assign_flexible_times(assignments_json: str) -> str:
    """
    为今天灵活待办中的任务分配时间段，写回日程文件。
    assignments_json: JSON 数组，格式为
    '[{"index": 0, "start": "09:00", "end": "10:00"}, ...]'
    index 是灵活待办 section 中任务的序号（从0开始）。
    已有时间前缀（匹配 HH:MM-HH:MM）的任务不覆盖。
    返回成功写入的任务数量描述。
    """
```

实现：读取今日文件，定位"灵活待办" section，按 index 找到对应行，
若该行无时间前缀则在任务文字前插入 `HH:MM-HH:MM `，写回文件。

### AI 操作后的文件格式

```markdown
## 灵活待办
- [ ] 09:00-10:30 剪视频（预计1.5小时，优先级高）
- [ ] 11:00-12:00 学习 rust
```

### Agent System Prompt 新增指令

```
在分析完固定日程后，调用 assign_flexible_times，
把灵活待办塞进固定日程的空隙里，按优先级和预计耗时分配时间段，
输出 JSON 数组。已有时间前缀的任务跳过，index 从0开始。
```

---

## 三、后端 API

### 新增端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/settings` | 返回 `{"advance_minutes": 15}` |
| `POST` | `/api/settings` | body `{"advance_minutes": int}`，写 config.json，重调今日提醒 |
| `GET` | `/api/events` | SSE 长连接，`text/event-stream` |
| `POST` | `/api/reminders/reschedule` | 手动重新解析今日时间并调度（调试用） |

### SSE 事件格式

```json
{"type": "reminder", "task": "健身", "time": "19:00", "early": true, "advance_minutes": 15}
```

- `early: true` 表示提前提醒，`false` 表示准点提醒

### SSE 连接管理（reminder.py）

```python
_sse_clients: list[asyncio.Queue] = []

async def sse_generator():
    q = asyncio.Queue()
    _sse_clients.append(q)
    try:
        while True:
            event = await q.get()
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    finally:
        _sse_clients.remove(q)

async def push_reminder_event(event: dict):
    for q in _sse_clients:
        await q.put(event)
```

### 提醒调度（reminder.py）

```python
def reschedule_reminders(date_str: str, scheduler: AsyncIOScheduler, advance_minutes: int):
    # 1. 移除当天所有旧的提醒 job（id 前缀 "reminder_"）
    # 2. 解析 schedule/{date_str}.md，提取所有含时间的任务
    # 3. 对每个任务：
    #    - 若 start - advance_minutes > now：调度提前提醒 job
    #    - 若 start > now：调度准点提醒 job
```

Job ID 格式：`reminder_{date}_{task_index}_{early/ontime}`

---

## 四、前端

### 设置面板

顶部导航栏右侧新增 ⚙️ 按钮，点击展开下拉面板：

```
提前提醒  [15] 分钟    [保存]
```

- 加载时 `GET /api/settings` 读取当前值
- 保存时 `POST /api/settings`，成功后显示"已保存 ✓"并收起

### SSE 客户端

```javascript
const es = new EventSource('/api/events');
es.onmessage = e => {
  const ev = JSON.parse(e.data);
  if (ev.type === 'reminder') showNotification(ev);
};
// EventSource 断线后自动重连，无需额外处理
```

### 浏览器通知

```javascript
async function showNotification(ev) {
  if (Notification.permission === 'default') {
    await Notification.requestPermission();
  }
  if (Notification.permission !== 'granted') return;
  const title = ev.early
    ? `⏰ ${ev.task} 还有 ${ev.advance_minutes} 分钟`
    : `🔔 ${ev.task} 开始了`;
  new Notification(title, { body: `安排时间：${ev.time}` });
}
```

页面加载时调用一次 `Notification.requestPermission()` 以提前获取权限。

---

## 五、不在本次范围内

- 提醒历史记录（已发过哪些提醒）
- 多天提醒（仅调度当天）
- 自定义每个任务的提醒时间（全局统一 advance_minutes）
- 微信提醒的去重（重启服务可能重复发）
