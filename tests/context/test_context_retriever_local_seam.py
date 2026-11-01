"""Public retrieve() behavior around the shared local retrieval seam."""

import pytest
from semantica.context.context_retriever import ContextRetriever
from semantica.utils.exceptions import ValidationError

from tests.context.grounded_helpers import retriever


class RecordingTracker:
    def __init__(self):
        self.calls = []

    def start_tracking(self, **kwargs):
        self.calls.append(("start",))
        return "t1"

    def update_tracking(self, *args, **kwargs):
        pass

    def stop_tracking(self, tracking_id, status=None, message=None):
        self.calls.append(("stop", status))


def rows():
    return [
        {"id": f"r{i}", "content": f"alpha content {i}", "score": 0.9 - i / 10}
        for i in range(3)
    ]


@pytest.mark.parametrize(
    "option",
    [
        {"merge_duplicates": False},
        {"limit_results": False},
        {"candidate_limit": 1},
        {"prepare": None},
        {"options": None},
    ],
)
def test_internal_names_passed_as_options_are_ignored(option):
    local = retriever(rows())
    expected = [r.content for r in local.retrieve("alpha content", max_results=2)]
    got = local.retrieve("alpha content", max_results=2, **option)
    assert [r.content for r in got] == expected
    assert len(got) == 2


def test_invalid_truth_filter_is_recorded_as_a_failed_run():
    local = ContextRetriever(use_graph_expansion=False)
    local.progress_tracker = RecordingTracker()
    with pytest.raises(ValidationError, match="truth_filter"):
        local.retrieve("query", truth_filter=object())
    assert local.progress_tracker.calls == [("start",), ("stop", "failed")]
