"""Kiểm tra layout Plotly Power BI — không cần chạy Streamlit UI."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _load_frontend_chart_module():
    class SS(dict):
        def __getattr__(self, key):
            return self.get(key)

        def __setattr__(self, key, value):
            self[key] = value

    mock_st = types.ModuleType("streamlit")
    mock_st.cache_data = lambda **kw: (lambda f: f)
    mock_st.session_state = SS()
    mock_st.column_config = MagicMock()
    mock_st.column_config.NumberColumn = MagicMock
    mock_st.chat_input = MagicMock(return_value=None)
    for attr in (
        "set_page_config", "title", "caption", "sidebar", "markdown", "header",
        "selectbox", "button", "divider", "chat_message", "spinner",
        "container", "columns", "plotly_chart", "dataframe", "metric",
        "download_button", "expander", "code", "warning", "info", "rerun", "subheader",
    ):
        setattr(mock_st, attr, MagicMock())
    mock_st.columns = MagicMock(return_value=[MagicMock(), MagicMock(), MagicMock()])
    mock_st.sidebar.__enter__ = MagicMock(return_value=mock_st.sidebar)
    mock_st.sidebar.__exit__ = MagicMock(return_value=False)
    mock_st.container.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_st.container.return_value.__exit__ = MagicMock(return_value=False)
    mock_st.chat_message.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_st.chat_message.return_value.__exit__ = MagicMock(return_value=False)
    sys.modules["streamlit"] = mock_st

    import importlib

    importlib.invalidate_caches()
    import frontend as fe  # noqa: WPS433

    return fe


def test_bar_money_text_auto_and_layout():
    fe = _load_frontend_chart_module()
    df = pd.DataFrame(
        {"ma_cp": ["VCB", "HPG", "FPT"], "von_hoa": [450_000, 1_200_000, 890_000]}
    ).rename(columns={"ma_cp": "Mã CP", "von_hoa": "Vốn hóa (tỷ)"})

    fig = fe._build_figure(df, "bar", title="test", query="top vốn hóa")
    assert fig is not None
    assert fig.layout.margin.l == 0
    assert fig.layout.margin.t == 40
    assert fig.layout.bargap == 0.2
    assert fig.layout.legend.y == 1.02

    bar = next(t for t in fig.data if t.type == "bar")
    assert bar.textposition == "outside"
    assert ".2s" in str(bar.texttemplate)


def test_line_markers_white_border():
    fe = _load_frontend_chart_module()
    df = pd.DataFrame(
        {
            "ngay_gd": pd.date_range("2024-01-01", periods=6),
            "gia_dong_cua": [85_000, 86_500, 84_200, 88_000, 90_100, 89_500],
        }
    ).rename(columns={"ngay_gd": "Ngày GD", "gia_dong_cua": "Giá đóng cửa"})

    fig = fe._build_figure(df, "line", title="test", query="xu hướng")
    assert fig is not None
    line = next(t for t in fig.data if t.type == "scatter")
    assert "markers" in (line.mode or "")
    assert line.marker.line.width == 2


if __name__ == "__main__":
    test_bar_money_text_auto_and_layout()
    test_line_markers_white_border()
    print("ALL PASSED")
