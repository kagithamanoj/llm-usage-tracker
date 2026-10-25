"""Tests for the @tracked decorator."""

import pytest

from llm_usage_tracker import UsageTracker, tracked


def test_tuple_return_records_and_returns_result_only():
    tracker = UsageTracker()

    @tracked("openai", "gpt-4o-mini", tracker=tracker, label="summarizer")
    def summarize(text):
        return "summary", 1200, 300

    assert summarize("some text") == "summary"
    assert tracker.summary()["calls"] == 1
    assert tracker.summary()["total_tokens"] == 1500
    assert tracker.events[0].label == "summarizer"
    assert tracker.events[0].model == "gpt-4o-mini"


def test_dict_return_is_unchanged_and_recorded():
    tracker = UsageTracker()

    @tracked("anthropic", "claude-haiku-4-5", tracker=tracker)
    def call():
        return {"answer": "hi", "prompt_tokens": 10, "completion_tokens": 5}

    result = call()
    assert result == {"answer": "hi", "prompt_tokens": 10, "completion_tokens": 5}
    assert tracker.summary()["total_tokens"] == 15


def test_usage_object_return_is_unchanged_and_recorded():
    class Usage:
        def __init__(self):
            self.prompt_tokens = 40
            self.completion_tokens = 60

    class Response:
        def __init__(self):
            self.text = "done"
            self.usage = Usage()

    tracker = UsageTracker()

    @tracked("google", "gemini-2.5-flash", tracker=tracker)
    def call():
        return Response()

    result = call()
    assert result.text == "done"
    assert tracker.summary()["total_tokens"] == 100


def test_usage_dict_attribute_return_is_recorded():
    class Response:
        def __init__(self):
            self.usage = {"prompt_tokens": 7, "completion_tokens": 3}

    tracker = UsageTracker()

    @tracked("openai", "gpt-4o-mini", tracker=tracker)
    def call():
        return Response()

    call()
    assert tracker.summary()["total_tokens"] == 10


def test_no_tracker_argument_creates_accessible_tracker():
    @tracked("openai", "gpt-4o-mini")
    def call():
        return "ok", 1, 2

    assert call() == "ok"
    assert call.tracker.summary()["calls"] == 1
    assert call.tracker.summary()["total_tokens"] == 3


def test_shared_tracker_accumulates_across_functions():
    tracker = UsageTracker()

    @tracked("openai", "gpt-4o-mini", tracker=tracker)
    def first():
        return "a", 10, 10

    @tracked("openai", "gpt-4o-mini", tracker=tracker)
    def second():
        return "b", 5, 5

    first()
    second()
    assert tracker.summary()["calls"] == 2
    assert tracker.summary()["total_tokens"] == 30


def test_raising_call_records_nothing():
    tracker = UsageTracker()

    @tracked("openai", "gpt-4o-mini", tracker=tracker)
    def boom():
        raise RuntimeError("llm failed")

    with pytest.raises(RuntimeError):
        boom()
    assert tracker.summary()["calls"] == 0


def test_unrecognized_return_shape_raises_and_records_nothing():
    tracker = UsageTracker()

    @tracked("openai", "gpt-4o-mini", tracker=tracker)
    def call():
        return "just a string"

    with pytest.raises(ValueError):
        call()
    assert tracker.summary()["calls"] == 0


def test_negative_tokens_rejected():
    tracker = UsageTracker()

    @tracked("openai", "gpt-4o-mini", tracker=tracker)
    def call():
        return "x", -1, 5

    with pytest.raises(ValueError):
        call()
    assert tracker.summary()["calls"] == 0


def test_wrapper_preserves_name_and_docstring():
    tracker = UsageTracker()

    @tracked("openai", "gpt-4o-mini", tracker=tracker)
    def my_call():
        """Do a call."""
        return "x", 1, 1

    assert my_call.__name__ == "my_call"
    assert my_call.__doc__ == "Do a call."
