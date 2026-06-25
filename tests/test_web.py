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


# ── Task 2 新增测试 ──────────────────────────────────────────────

def test_parse_schedule_any_date(tmp_path):
    from main import parse_schedule

    (tmp_path / "2026-01-15.md").write_text(
        "## 固定日程\n- [ ] 开会\n",
        encoding="utf-8",
    )
    result = parse_schedule("2026-01-15", schedule_dir=tmp_path)
    assert result["date"] == "2026-01-15"
    assert result["sections"][0]["tasks"][0]["text"] == "开会"


def test_write_task_done_with_date_str(tmp_path):
    from main import write_task_done

    (tmp_path / "2026-01-15.md").write_text(
        "## 灵活待办\n- 任务A\n",
        encoding="utf-8",
    )
    result = write_task_done("s0-t0", True, date_str="2026-01-15", schedule_dir=tmp_path)
    assert result["sections"][0]["tasks"][0]["done"] is True


def test_get_schedule_api(tmp_path):
    from unittest.mock import patch
    from fastapi.testclient import TestClient

    (tmp_path / "2026-01-15.md").write_text(
        "## 固定日程\n- [ ] 开会\n",
        encoding="utf-8",
    )

    with patch("main._DEFAULT_SCHEDULE_DIR", tmp_path), \
         patch("main.scheduler"):
        from main import app
        with TestClient(app) as client:
            resp = client.get("/api/schedule/2026-01-15")

    assert resp.status_code == 200
    assert resp.json()["date"] == "2026-01-15"
    assert resp.json()["sections"][0]["tasks"][0]["text"] == "开会"


def test_create_day_api(tmp_path):
    from unittest.mock import patch
    from fastapi.testclient import TestClient

    with patch("main._DEFAULT_SCHEDULE_DIR", tmp_path), \
         patch("main.scheduler"):
        from main import app
        with TestClient(app) as client:
            resp = client.post("/api/schedule/2026-01-16")

    assert resp.status_code == 200
    assert (tmp_path / "2026-01-16.md").exists()
    data = resp.json()
    assert data["date"] == "2026-01-16"
    section_names = [s["name"] for s in data["sections"]]
    assert "固定日程" in section_names
    assert "灵活待办" in section_names


def test_add_task_api(tmp_path):
    from unittest.mock import patch
    from fastapi.testclient import TestClient

    (tmp_path / "2026-01-15.md").write_text(
        "## 固定日程\n\n## 灵活待办\n",
        encoding="utf-8",
    )

    with patch("main._DEFAULT_SCHEDULE_DIR", tmp_path), \
         patch("main.scheduler"):
        from main import app
        with TestClient(app) as client:
            resp = client.post(
                "/api/schedule/2026-01-15/task",
                json={"section": "灵活待办", "text": "写测试"},
            )

    assert resp.status_code == 200
    tasks = resp.json()["sections"][1]["tasks"]
    assert tasks[0]["text"] == "写测试"
    assert tasks[0]["done"] is False


def test_patch_task_text_api(tmp_path):
    from unittest.mock import patch
    from fastapi.testclient import TestClient

    (tmp_path / "2026-01-15.md").write_text(
        "## 灵活待办\n- [ ] 旧文字\n",
        encoding="utf-8",
    )

    with patch("main._DEFAULT_SCHEDULE_DIR", tmp_path), \
         patch("main.scheduler"):
        from main import app
        with TestClient(app) as client:
            resp = client.patch(
                "/api/schedule/2026-01-15/task/s0-t0",
                json={"text": "新文字"},
            )

    assert resp.status_code == 200
    assert resp.json()["sections"][0]["tasks"][0]["text"] == "新文字"


def test_patch_task_done_api(tmp_path):
    from unittest.mock import patch
    from fastapi.testclient import TestClient

    (tmp_path / "2026-01-15.md").write_text(
        "## 灵活待办\n- [ ] 某任务\n",
        encoding="utf-8",
    )

    with patch("main._DEFAULT_SCHEDULE_DIR", tmp_path), \
         patch("main.scheduler"):
        from main import app
        with TestClient(app) as client:
            resp = client.patch(
                "/api/schedule/2026-01-15/task/s0-t0",
                json={"done": True},
            )

    assert resp.status_code == 200
    assert resp.json()["sections"][0]["tasks"][0]["done"] is True


def test_delete_task_api(tmp_path):
    from unittest.mock import patch
    from fastapi.testclient import TestClient

    (tmp_path / "2026-01-15.md").write_text(
        "## 灵活待办\n- [ ] 任务A\n- [ ] 任务B\n",
        encoding="utf-8",
    )

    with patch("main._DEFAULT_SCHEDULE_DIR", tmp_path), \
         patch("main.scheduler"):
        from main import app
        with TestClient(app) as client:
            resp = client.delete("/api/schedule/2026-01-15/task/s0-t0")

    assert resp.status_code == 200
    tasks = resp.json()["sections"][0]["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["text"] == "任务B"


def test_startup_triggers_morning_review(monkeypatch):
    import asyncio
    from unittest.mock import patch, AsyncMock, MagicMock

    monkeypatch.setenv("ZHIPUAI_API_KEY", "fake")
    created = []

    def fake_create_task(coro, **kw):
        coro.close()
        created.append(True)
        return MagicMock()

    with patch("main.morning_review_job", new_callable=AsyncMock), \
         patch("main.scheduler"), \
         patch("main.asyncio.create_task", side_effect=fake_create_task):
        from main import app
        from fastapi.testclient import TestClient
        with TestClient(app):
            pass

    assert len(created) == 1


# ── Task 4 新增测试 ──────────────────────────────────────────────

def test_get_settings_api():
    from unittest.mock import patch
    from fastapi.testclient import TestClient

    with patch("main.scheduler"), \
         patch("main.get_config", return_value={"advance_minutes": 15}):
        from main import app
        with TestClient(app) as client:
            resp = client.get("/api/settings")

    assert resp.status_code == 200
    assert resp.json()["advance_minutes"] == 15


def test_post_settings_api():
    from unittest.mock import patch
    from fastapi.testclient import TestClient

    with patch("main.scheduler"), \
         patch("main.save_config") as mock_save, \
         patch("main.reschedule_reminders") as mock_resched, \
         patch("main.get_config", return_value={"advance_minutes": 20}):
        from main import app
        with TestClient(app) as client:
            resp = client.post("/api/settings", json={"advance_minutes": 20})

    assert resp.status_code == 200
    mock_save.assert_called_once_with({"advance_minutes": 20})
    mock_resched.assert_called_once()


def test_post_settings_rejects_negative():
    from unittest.mock import patch
    from fastapi.testclient import TestClient

    with patch("main.scheduler"):
        from main import app
        with TestClient(app) as client:
            resp = client.post("/api/settings", json={"advance_minutes": -1})

    assert resp.status_code == 400


def test_reschedule_api():
    from unittest.mock import patch
    from fastapi.testclient import TestClient

    with patch("main.scheduler"), \
         patch("main.get_config", return_value={"advance_minutes": 15}), \
         patch("main.reschedule_reminders", return_value=4):
        from main import app
        with TestClient(app) as client:
            resp = client.post("/api/reminders/reschedule")

    assert resp.status_code == 200
    assert resp.json()["scheduled"] == 4


def test_sse_endpoint_registered():
    from unittest.mock import patch

    with patch("main.scheduler"):
        from main import app

    routes = {r.path: r for r in app.routes}
    assert "/api/events" in routes
