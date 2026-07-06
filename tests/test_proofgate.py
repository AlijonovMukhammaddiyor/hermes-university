import pytest

from engine.proofgate import get_gate
from engine.proofgate.base import ProofGate, register_gate
from engine.proofgate.leetcode import LeetCodeGate


def fake(subs):
    return lambda username, session: subs


def test_leetcode_pass_when_ac_after_assignment():
    gate = LeetCodeGate(fetcher=fake([{"titleSlug": "two-sum", "timestamp": 1000}]))
    res = gate.verify({"username": "u", "slug": "two-sum", "since_ts": 500})
    assert res.passed and res.score == 1.0 and res.source == "leetcode"


def test_leetcode_fail_when_ac_before_assignment():
    gate = LeetCodeGate(fetcher=fake([{"titleSlug": "two-sum", "timestamp": 100}]))
    res = gate.verify({"username": "u", "slug": "two-sum", "since_ts": 500})
    assert not res.passed


def test_leetcode_fail_when_wrong_slug():
    gate = LeetCodeGate(fetcher=fake([{"titleSlug": "add-two-numbers", "timestamp": 1000}]))
    assert not gate.verify({"username": "u", "slug": "two-sum", "since_ts": 0}).passed


def test_leetcode_fetch_failure_is_not_passed():
    def boom(u, s):
        raise RuntimeError("network down")
    gate = LeetCodeGate(fetcher=boom)
    res = gate.verify({"username": "u", "slug": "two-sum", "since_ts": 0})
    assert not res.passed and "network down" in (res.detail or "")


def test_registry_has_leetcode_and_rejects_unknown():
    assert get_gate("leetcode").name == "leetcode"
    with pytest.raises(KeyError):
        get_gate("judge0")   # not added yet (RFC D9: later)
