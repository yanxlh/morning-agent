import pytest
from pathlib import Path
from datetime import date as _date


def test_parse_today_returns_structure(tmp_path):
    from main import parse_today

    today = _date.today().isoformat()
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
