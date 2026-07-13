"""Kiểm tra parser Executive Summary."""

from __future__ import annotations

import re

_INSIGHT_SECTION_TITLES = (
    r"Phân tích chi tiết",
    r"Điểm nổi bật",
    r"Xu hướng\s*(?:&|và)\s*biến động",
    r"Phát hiện bất thường",
    r"Rủi ro\s*(?:&|và)\s*giới hạn(?:\s*dữ liệu)?",
    r"Gợi ý theo dõi",
    r"Tóm tắt",
)
_SPLIT = re.compile(
    rf"(?:^|\n)\s*(?:\*\*)?\s*"
    rf"({'|'.join(_INSIGHT_SECTION_TITLES)})"
    r"\s*(?:\*\*)?\s*[:：\-–]+\s*",
    re.IGNORECASE | re.MULTILINE,
)

SAMPLE = """**Tóm tắt:** VCB tăng nhẹ.

**Điểm nổi bật:**
- Giá mở cửa cao nhất

**Xu hướng & biến động:** Giá của SSI không có xu hướng rõ ràng, biến động trung bình thấp.

**Phát hiện bất thường:**
- Chênh lệch lớn
"""


def test_split_finds_four_sections() -> None:
    matches = list(_SPLIT.finditer(SAMPLE))
    assert len(matches) == 4
    bodies = []
    for idx, m in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(SAMPLE)
        bodies.append(SAMPLE[m.end() : end].strip())
    assert "không có xu hướng rõ ràng" in bodies[2]


def test_frontend_parser() -> None:
    import sys
    import types
    from pathlib import Path
    from unittest.mock import MagicMock

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
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))
    sys.modules["streamlit"] = mock_st

    import importlib

    importlib.invalidate_caches()
    import frontend as fe

    sections = fe._parse_insight_sections(SAMPLE)
    labels = [s[0] for s in sections]
    assert labels.count("📈 Xu hướng & biến động") == 1, labels
    assert labels[1] == "⭐ Điểm nổi bật", labels
    trend = next(s[1] for s in sections if "Xu hướng" in s[0])
    assert "không có xu hướng rõ ràng" in trend
    assert "**" not in trend


if __name__ == "__main__":
    test_split_finds_four_sections()
    test_frontend_parser()
    print("ALL PASSED")
