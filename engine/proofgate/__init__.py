"""Pluggable proof-gates (RFC §7): verify(evidence) -> ProofResult.

The LLM never decides "passed" — a gate adapter does. Register by name so the same interface
serves LeetCode now and Judge0 later without touching callers.
"""

from __future__ import annotations

from .base import ProofGate, ProofResult, get_gate, register_gate
from .leetcode import LeetCodeGate

register_gate("leetcode", LeetCodeGate())

__all__ = ["ProofGate", "ProofResult", "get_gate", "register_gate", "LeetCodeGate"]
