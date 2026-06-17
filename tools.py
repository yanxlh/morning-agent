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
