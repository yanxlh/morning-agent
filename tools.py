from pathlib import Path
from datetime import date, timedelta
from typing import Optional
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
