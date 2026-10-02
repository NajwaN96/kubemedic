"""Locks the TaskFlow bilingual copy without adding a browser test runner."""

from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src"


def test_taskflow_locales_cover_both_directions():
    source = (FRONTEND / "i18n.ts").read_text(encoding="utf-8")
    app = (FRONTEND / "App.tsx").read_text(encoding="utf-8")
    assert 'dir: "rtl"' in source
    assert 'dir: "ltr"' in source
    assert "لا توجد مهام حالياً" in source
    assert "No tasks yet" in source
    assert "إضافة مهمة" in source
    assert "Add Task" in source
    assert "taskflow.lang" in source
    assert "documentElement.dir" in app
    assert "locale === \"ar\"" not in app
    assert "task.title" in app
