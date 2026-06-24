# 网页端日程编辑 + 启动即推送 设计文档

日期：2026-06-24

## 背景

当前 morning-agent 的输入方式单一，用户必须手动编辑 `schedule/YYYY-MM-DD.md` 文件才能管理日程。本次迭代增加三个能力：

1. 网页端可编辑任意日期的日程（增删改任务条目）
2. 服务每次启动时立即触发一次完整的早晨推送（与7点定时任务行为相同）
3. 保留每天 7:00 的定时轮询任务不变

---

## 架构变更

### 后端（main.py + tools.py）

**tools.py 新增三个普通函数（非 LangChain tool）：**

- `append_task(date: str, section_name: str, text: str)` — 在指定 section 末尾追加 `- [ ] text`
- `delete_task(date: str, task_id: str)` — 按 `s{i}-t{j}` 定位并删除对应行
- `update_task_text(date: str, task_id: str, text: str)` — 修改任务文字，保留 done 状态

**main.py 改动：**

- `parse_today(schedule_dir)` → `parse_schedule(date: str, schedule_dir)` 加 date 参数；保留 `parse_today()` 作为调用 `parse_schedule(today)` 的包装（向后兼容）
- `write_task_done` 同理加 `date: str` 参数
- `lifespan()` 里 `scheduler.start()` 后加 `asyncio.create_task(morning_review_job())`，实现启动即推送

**新增 API 端点（现有接口不变）：**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/schedule/{date}` | 读取任意日期日程 |
| PATCH | `/api/schedule/{date}/task/{task_id}` | 修改 done 状态或任务文字，body: `{"done": bool}` 或 `{"text": str}` |
| POST | `/api/schedule/{date}/task` | 新增任务，body: `{"section": "灵活待办", "text": "xxx"}` |
| DELETE | `/api/schedule/{date}/task/{task_id}` | 删除任务 |
| POST | `/api/schedule/{date}` | 创建空日程文件（固定日程 + 灵活待办两个空 section） |

### 前端（static/index.html）

**新增顶部日期选择器：**
- `<input type="date">` 默认今天，切换日期时调 `GET /api/schedule/{date}` 重新渲染

**无日程文件时：**
- 显示"创建日程"按钮，调 `POST /api/schedule/{date}` 创建后刷新

**每个 section 卡片内：**
- 右上角"+ 添加"按钮 → 展开输入框，回车或点确认提交 `POST /api/schedule/{date}/task`
- 每条任务悬停时出现"✎"和"×"按钮
- 点"✎"：任务文字变 `<input>`，失焦或回车保存，调 `PATCH` 接口
- 点"×"：调 `DELETE` 接口，局部移除该条目

**交互原则：** 所有操作即时 API 调用，成功后局部刷新，不整页重载。

---

## 数据格式不变

日程文件仍为 Markdown，格式与现在完全一致：

```
# YYYY-MM-DD 日程表

## 固定日程
- [ ] 任务文字

## 灵活待办
- [x] 已完成任务
```

section 名称固定为"固定日程"和"灵活待办"，本次不支持自定义。

---

## 不在本次范围内

- 自定义 section 名称
- 日程模板复制（从某天复制到另一天）
- 历史日程统计

---

## 文件改动范围

| 文件 | 改动类型 |
|------|----------|
| `tools.py` | 新增 3 个函数 |
| `main.py` | 重构 2 个函数签名 + 新增 4 个端点 + lifespan 加启动触发 |
| `static/index.html` | 新增日期选择器 + 编辑控件 |
| `tests/` | 新增对应测试 |
