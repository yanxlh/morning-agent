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
