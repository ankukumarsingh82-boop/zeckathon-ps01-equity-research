from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_streamlit_app_runs_offline_without_exceptions(monkeypatch):
    testing = pytest.importorskip("streamlit.testing.v1")
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    at = testing.AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Winner" in m.label for m in at.metric)
    # move a slider (bear preset) and re-run interactively
    at.sidebar.selectbox[0].set_value("bear").run()
    assert any("Winner" in m.label for m in at.metric)
    assert not at.exception


def test_app_has_review_tabs():
    testing = pytest.importorskip("streamlit.testing.v1")
    at = testing.AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.run()
    labels = [t.label for t in at.tabs]
    assert "Industry & F&O curbs" in labels and "Ke cross-check" in labels
    assert not at.exception
