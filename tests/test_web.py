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


def test_write_task_done_marks_checked(tmp_path):
    from main import write_task_done

    today = _date.today().isoformat()
    (tmp_path / f"{today}.md").write_text(
        "## 灵活待办\n- 找项目（1h）\n- Boss 找实习\n",
        encoding="utf-8"
    )

    result = write_task_done("s0-t1", True, schedule_dir=tmp_path)

    content = (tmp_path / f"{today}.md").read_text(encoding="utf-8")
    assert "- [x] Boss 找实习" in content
    assert "- 找项目（1h）" in content or "- [ ] 找项目（1h）" in content
    assert result["sections"][0]["tasks"][1]["done"] is True
    assert result["done_count"] == 1


def test_write_task_done_unmarks_checked(tmp_path):
    from main import write_task_done

    today = _date.today().isoformat()
    (tmp_path / f"{today}.md").write_text(
        "## 固定日程\n- [x] 09:00-10:00 会议\n",
        encoding="utf-8"
    )

    result = write_task_done("s0-t0", False, schedule_dir=tmp_path)

    content = (tmp_path / f"{today}.md").read_text(encoding="utf-8")
    assert "- [ ] 09:00-10:00 会议" in content
    assert result["sections"][0]["tasks"][0]["done"] is False


def test_write_task_done_two_sections(tmp_path):
    from main import write_task_done

    today = _date.today().isoformat()
    (tmp_path / f"{today}.md").write_text(
        "## 固定日程\n- 09:00-10:00 会议\n\n## 灵活待办\n- 写报告\n- 阅读论文\n",
        encoding="utf-8"
    )

    result = write_task_done("s1-t1", True, schedule_dir=tmp_path)

    content = (tmp_path / f"{today}.md").read_text(encoding="utf-8")
    assert "- [x] 阅读论文" in content
    assert "- 写报告" in content or "- [ ] 写报告" in content
    assert result["done_count"] == 1


def test_get_today_api(tmp_path):
    from unittest.mock import patch
    from fastapi.testclient import TestClient

    today = _date.today().isoformat()
    (tmp_path / f"{today}.md").write_text(
        "## 固定日程\n- 09:00-10:00 会议\n",
        encoding="utf-8"
    )

    with patch("main._DEFAULT_SCHEDULE_DIR", tmp_path), \
         patch("main.scheduler"):
        from main import app
        with TestClient(app) as client:
            resp = client.get("/api/today")

    assert resp.status_code == 200
    data = resp.json()
    assert data["date"] == today
    assert data["total"] == 1
    assert data["sections"][0]["tasks"][0]["id"] == "s0-t0"


def test_patch_task_api(tmp_path):
    from unittest.mock import patch
    from fastapi.testclient import TestClient

    today = _date.today().isoformat()
    (tmp_path / f"{today}.md").write_text(
        "## 灵活待办\n- 找项目\n",
        encoding="utf-8"
    )

    with patch("main._DEFAULT_SCHEDULE_DIR", tmp_path), \
         patch("main.scheduler"):
        from main import app
        with TestClient(app) as client:
            resp = client.patch("/api/task/s0-t0", json={"done": True})

    assert resp.status_code == 200
    data = resp.json()
    assert data["sections"][0]["tasks"][0]["done"] is True
    assert data["done_count"] == 1
