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


def test_version_numbers_monotonic_after_rollback(tmp_path):
    """After rollback, a new version must not reuse the old number (no dup vNNN)."""
    from agent.storage.prompts import PromptManager
    pm = PromptManager(base_path=tmp_path)
    info = {"trigger": "t"}
    for _ in range(4):  # v1, v2, v3, v4
        pm.create_version("main_agent", "a valid prompt " * 5, [], info)
    assert pm.current_version("main_agent") == 4
    assert pm.rollback("main_agent", 3, "test")
    assert pm.current_version("main_agent") == 3
    n = pm.create_version("main_agent", "another valid prompt " * 5, [], info)
    assert n == 5  # monotonic, not a second v4
    files = sorted(p.name[:4] for p in (tmp_path / "main_agent").glob("v*.yaml")
                   if p.name != "current.yaml")
    assert len(files) == len(set(files))  # no duplicate version numbers


def test_auto_rollback_reads_real_current_file(tmp_path):
    """record_feedback + maybe_auto_rollback must agree on which file holds the
    metrics (copy-mode current.yaml is stale) — degradation protection works."""
    from agent.storage.prompts import PromptManager
    pm = PromptManager(base_path=tmp_path)
    pm.create_version("main_agent", "a valid prompt " * 5, [], {"trigger": "t"})  # v1, parent None
    pm.create_version("main_agent", "another valid prompt " * 5, [], {"trigger": "t"})  # v2, parent v1
    for _ in range(5):
        pm.record_feedback("main_agent", is_positive=False)  # 5 negatives
    rb = pm.maybe_auto_rollback("main_agent")
    assert rb is not None and rb["rolled_back_to"] == 1
