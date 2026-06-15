"""Phase 4: closed-loop quality control — metrics + auto-rollback on degradation."""

from agent.storage.prompts import PromptManager


def test_auto_rollback_on_degradation(tmp_path):
    pm = PromptManager(base_path=tmp_path)

    v1 = pm.create_version("main_agent", "PROMPT v1", [], {"reason": "base"})
    assert v1 == 1
    v2 = pm.create_version("main_agent", "PROMPT v2 (worse)", [], {"reason": "experiment"})
    assert v2 == 2
    assert pm.current_version("main_agent") == 2

    # v2 underperforms: 3 negative, 1 positive over 4 samples = 75% negative.
    pm.record_feedback("main_agent", is_positive=False)
    pm.record_feedback("main_agent", is_positive=False)
    pm.record_feedback("main_agent", is_positive=True)
    assert pm.maybe_auto_rollback("main_agent") is None  # only 3 samples < MIN

    pm.record_feedback("main_agent", is_positive=False)  # 4th sample → 75% neg
    rb = pm.maybe_auto_rollback("main_agent")
    assert rb and rb["rolled_back_to"] == 1
    assert pm.current_version("main_agent") == 1
    assert pm.get_current("main_agent") == "PROMPT v1"


def test_good_version_not_rolled_back(tmp_path):
    pm = PromptManager(base_path=tmp_path)
    pm.create_version("main_agent", "v1", [], {})
    pm.create_version("main_agent", "v2 good", [], {})

    # mostly positive → stays
    for _ in range(4):
        pm.record_feedback("main_agent", is_positive=True)
    pm.record_feedback("main_agent", is_positive=False)
    assert pm.maybe_auto_rollback("main_agent") is None
    assert pm.current_version("main_agent") == 2
