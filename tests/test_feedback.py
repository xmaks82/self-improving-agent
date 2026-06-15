"""Phase 4: FeedbackDetector must not treat work commands as self-feedback."""

from agent.core.feedback import FeedbackDetector


def test_work_commands_are_not_feedback():
    d = FeedbackDetector(client=None)
    # These are TASKS for the agent — must NOT trigger prompt improvement.
    assert d.detect("исправь баг в файле auth.py") is None
    assert d.detect("fix this function") is None
    assert d.detect("перепиши метод parse в parser.py") is None
    assert d.detect("измени конфиг в config.yaml") is None


def test_genuine_negative_still_triggers():
    d = FeedbackDetector(client=None)
    fb = d.detect("слишком длинно, можно короче")
    assert fb and fb.type == "negative" and fb.should_trigger_improvement is True

    fb2 = d.detect("your answer is too verbose")
    assert fb2 and fb2.type == "negative"


def test_positive_feedback():
    d = FeedbackDetector(client=None)
    fb = d.detect("спасибо, отлично помогло")
    assert fb and fb.type == "positive" and fb.should_trigger_improvement is False


def test_bare_imperative_recorded_but_no_trigger():
    d = FeedbackDetector(client=None)
    fb = d.detect("переделай")  # no task signal, no LLM client
    assert fb and fb.type == "negative" and fb.should_trigger_improvement is False
