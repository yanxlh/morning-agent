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


# ── Task 1 新增测试 ──────────────────────────────────────────────

def test_create_schedule_creates_two_sections(tmp_path):
    import tools
    tools.create_schedule("2026-06-24", schedule_dir=tmp_path)
    content = (tmp_path / "2026-06-24.md").read_text(encoding="utf-8")
    assert "## 固定日程" in content
    assert "## 灵活待办" in content


def test_create_schedule_no_overwrite(tmp_path):
    import tools
    (tmp_path / "2026-06-24.md").write_text("原有内容", encoding="utf-8")
    tools.create_schedule("2026-06-24", schedule_dir=tmp_path)
    assert (tmp_path / "2026-06-24.md").read_text(encoding="utf-8") == "原有内容"


def test_append_task_adds_to_section(tmp_path):
    import tools
    (tmp_path / "2026-06-24.md").write_text(
        "## 固定日程\n- [ ] 已有任务\n\n## 灵活待办\n",
        encoding="utf-8",
    )
    tools.append_task("2026-06-24", "固定日程", "新任务", schedule_dir=tmp_path)
    content = (tmp_path / "2026-06-24.md").read_text(encoding="utf-8")
    assert "- [ ] 新任务" in content
    lines = content.splitlines()
    # 新任务应在固定日程 section 内（灵活待办之前）
    new_idx = next(i for i, l in enumerate(lines) if "新任务" in l)
    flex_idx = next(i for i, l in enumerate(lines) if "灵活待办" in l)
    assert new_idx < flex_idx


def test_append_task_to_empty_section(tmp_path):
    import tools
    (tmp_path / "2026-06-24.md").write_text(
        "## 固定日程\n\n## 灵活待办\n",
        encoding="utf-8",
    )
    tools.append_task("2026-06-24", "固定日程", "第一个任务", schedule_dir=tmp_path)
    content = (tmp_path / "2026-06-24.md").read_text(encoding="utf-8")
    assert "- [ ] 第一个任务" in content


def test_append_task_missing_file_raises(tmp_path):
    import tools, pytest
    with pytest.raises(FileNotFoundError):
        tools.append_task("2099-01-01", "固定日程", "任务", schedule_dir=tmp_path)


def test_append_task_missing_section_raises(tmp_path):
    import tools, pytest
    (tmp_path / "2026-06-24.md").write_text("## 固定日程\n", encoding="utf-8")
    with pytest.raises(ValueError):
        tools.append_task("2026-06-24", "不存在的section", "任务", schedule_dir=tmp_path)


def test_delete_task_removes_line(tmp_path):
    import tools
    (tmp_path / "2026-06-24.md").write_text(
        "## 灵活待办\n- [ ] 任务A\n- [x] 任务B\n",
        encoding="utf-8",
    )
    tools.delete_task("2026-06-24", "s0-t0", schedule_dir=tmp_path)
    content = (tmp_path / "2026-06-24.md").read_text(encoding="utf-8")
    assert "任务A" not in content
    assert "任务B" in content


def test_delete_task_not_found_raises(tmp_path):
    import tools, pytest
    (tmp_path / "2026-06-24.md").write_text("## 灵活待办\n- [ ] 只有一个\n", encoding="utf-8")
    with pytest.raises(LookupError):
        tools.delete_task("2026-06-24", "s0-t5", schedule_dir=tmp_path)


def test_update_task_text_changes_text_keeps_done(tmp_path):
    import tools
    (tmp_path / "2026-06-24.md").write_text(
        "## 灵活待办\n- [x] 旧文字\n",
        encoding="utf-8",
    )
    tools.update_task_text("2026-06-24", "s0-t0", "新文字", schedule_dir=tmp_path)
    content = (tmp_path / "2026-06-24.md").read_text(encoding="utf-8")
    assert "- [x] 新文字" in content
    assert "旧文字" not in content


def test_update_task_text_not_found_raises(tmp_path):
    import tools, pytest
    (tmp_path / "2026-06-24.md").write_text("## 灵活待办\n- [ ] 任务\n", encoding="utf-8")
    with pytest.raises(LookupError):
        tools.update_task_text("2026-06-24", "s0-t9", "新文字", schedule_dir=tmp_path)


from datetime import date as _date


def test_assign_flexible_times_adds_time_prefix(tmp_path, monkeypatch):
    import tools
    monkeypatch.setattr(tools, "SCHEDULE_DIR", tmp_path)
    today = _date.today().isoformat()
    (tmp_path / f"{today}.md").write_text(
        "## 固定日程\n- [ ] 14:00-15:00 健身\n\n## 灵活待办\n- [ ] 剪视频\n- [ ] 学习rust\n",
        encoding="utf-8",
    )
    result = tools.assign_flexible_times.invoke(
        {"assignments_json": '[{"index": 0, "start": "09:00", "end": "10:00"}]'}
    )
    content = (tmp_path / f"{today}.md").read_text(encoding="utf-8")
    assert "09:00-10:00 剪视频" in content
    assert "学习rust" in content  # index 1，未分配，不变
    assert "已为 1" in result


def test_assign_flexible_times_skips_existing_time(tmp_path, monkeypatch):
    import tools
    monkeypatch.setattr(tools, "SCHEDULE_DIR", tmp_path)
    today = _date.today().isoformat()
    (tmp_path / f"{today}.md").write_text(
        "## 灵活待办\n- [ ] 09:00-10:00 剪视频\n",
        encoding="utf-8",
    )
    result = tools.assign_flexible_times.invoke(
        {"assignments_json": '[{"index": 0, "start": "11:00", "end": "12:00"}]'}
    )
    content = (tmp_path / f"{today}.md").read_text(encoding="utf-8")
    assert "09:00-10:00 剪视频" in content  # 未被覆盖
    assert "11:00" not in content
    assert "已为 0" in result


def test_assign_flexible_times_invalid_json(tmp_path, monkeypatch):
    import tools
    monkeypatch.setattr(tools, "SCHEDULE_DIR", tmp_path)
    today = _date.today().isoformat()
    (tmp_path / f"{today}.md").write_text("## 灵活待办\n- [ ] 任务\n", encoding="utf-8")
    result = tools.assign_flexible_times.invoke({"assignments_json": "not json"})
    assert "JSON 解析失败" in result


def test_assign_flexible_times_out_of_bounds(tmp_path, monkeypatch):
    import tools
    monkeypatch.setattr(tools, "SCHEDULE_DIR", tmp_path)
    today = _date.today().isoformat()
    (tmp_path / f"{today}.md").write_text("## 灵活待办\n- [ ] 任务\n", encoding="utf-8")
    result = tools.assign_flexible_times.invoke(
        {"assignments_json": '[{"index": 99, "start": "09:00", "end": "10:00"}]'}
    )
    assert "已为 0" in result


def test_assign_flexible_times_no_file(tmp_path, monkeypatch):
    import tools
    monkeypatch.setattr(tools, "SCHEDULE_DIR", tmp_path)
    result = tools.assign_flexible_times.invoke(
        {"assignments_json": '[{"index": 0, "start": "09:00", "end": "10:00"}]'}
    )
    assert "日程文件不存在" in result
