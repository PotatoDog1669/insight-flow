from __future__ import annotations

from app.renderers.brief import BriefRenderer
from app.renderers.deep_report import DeepReportRenderer
from app.renderers.daily import DailyRenderer
from app.renderers.weekly import WeeklyRenderer


def test_renderer_class_names_are_semantic() -> None:
    assert BriefRenderer.__name__ == "BriefRenderer"
    assert DailyRenderer.__name__ == "DailyRenderer"
    assert WeeklyRenderer.__name__ == "WeeklyRenderer"
    assert DeepReportRenderer.__name__ == "DeepReportRenderer"
