import pytest
from pathlib import Path
from datetime import date as _date_type


def test_parse_task_times_fixed_schedule(tmp_path):
    from reminder import parse_task_times
    (tmp_path / "2026-06-25.md").write_text(
        "## 固定日程\n- [ ] 14:00-15:30 健身\n## 灵活待办\n- [ ] 学习rust\n",
        encoding="utf-8",
    )
    result = parse_task_times("2026-06-25", schedule_dir=tmp_path)
    assert len(result) == 1
    assert result[0]["start_time"] == "14:00"
    assert result[0]["task_text"] == "健身"
    assert result[0]["section"] == "固定日程"


def test_parse_task_times_flexible_with_time(tmp_path):
    from reminder import parse_task_times
    (tmp_path / "2026-06-25.md").write_text(
        "## 灵活待办\n- [ ] 09:00-10:00 剪视频（预计1h）\n",
        encoding="utf-8",
    )
    result = parse_task_times("2026-06-25", schedule_dir=tmp_path)
    assert len(result) == 1
    assert result[0]["start_time"] == "09:00"
    assert "剪视频" in result[0]["task_text"]


def test_parse_task_times_skips_no_time(tmp_path):
    from reminder import parse_task_times
    (tmp_path / "2026-06-25.md").write_text(
        "## 灵活待办\n- [ ] 学习rust\n- [ ] 14:00-15:00 健身\n",
        encoding="utf-8",
    )
    result = parse_task_times("2026-06-25", schedule_dir=tmp_path)
    assert len(result) == 1
    assert result[0]["task_text"] == "健身"


def test_parse_task_times_no_file(tmp_path):
    from reminder import parse_task_times
    result = parse_task_times("2099-01-01", schedule_dir=tmp_path)
    assert result == []


@pytest.mark.asyncio
async def test_push_reminder_event_delivers_to_client():
    import asyncio
    from reminder import push_reminder_event, _sse_clients

    q: asyncio.Queue = asyncio.Queue()
    _sse_clients.append(q)
    try:
        event = {
            "type": "reminder", "task": "健身", "time": "19:00",
            "early": False, "advance_minutes": 15,
        }
        await push_reminder_event(event)
        received = await asyncio.wait_for(q.get(), timeout=1.0)
        assert received == event
    finally:
        _sse_clients.remove(q)


def test_reschedule_reminders_schedules_future_jobs(tmp_path):
    from unittest.mock import MagicMock
    from reminder import reschedule_reminders

    # 2099 年的时间必然在 now 之后
    (tmp_path / "2099-12-31.md").write_text(
        "## 固定日程\n- [ ] 23:50-23:59 深夜任务\n",
        encoding="utf-8",
    )
    mock_scheduler = MagicMock()
    mock_scheduler.get_jobs.return_value = []

    count = reschedule_reminders("2099-12-31", mock_scheduler, 5, schedule_dir=tmp_path)

    assert count == 2  # early (23:45) + ontime (23:50)
    assert mock_scheduler.add_job.call_count == 2


def test_reschedule_reminders_removes_old_jobs(tmp_path):
    from unittest.mock import MagicMock
    from reminder import reschedule_reminders

    (tmp_path / "2026-06-25.md").write_text("## 固定日程\n", encoding="utf-8")
    old_job = MagicMock()
    old_job.id = "reminder_2026-06-25_0_early"
    unrelated_job = MagicMock()
    unrelated_job.id = "morning_review"
    mock_scheduler = MagicMock()
    mock_scheduler.get_jobs.return_value = [old_job, unrelated_job]

    reschedule_reminders("2026-06-25", mock_scheduler, 15, schedule_dir=tmp_path)

    old_job.remove.assert_called_once()
    unrelated_job.remove.assert_not_called()


def test_reschedule_reminders_skips_past_jobs(tmp_path):
    from unittest.mock import MagicMock
    from reminder import reschedule_reminders

    # 2020 年的时间已经在 now 之前
    (tmp_path / "2020-01-01.md").write_text(
        "## 固定日程\n- [ ] 09:00-10:00 早已过去的任务\n",
        encoding="utf-8",
    )
    mock_scheduler = MagicMock()
    mock_scheduler.get_jobs.return_value = []

    count = reschedule_reminders("2020-01-01", mock_scheduler, 15, schedule_dir=tmp_path)

    assert count == 0
    mock_scheduler.add_job.assert_not_called()
