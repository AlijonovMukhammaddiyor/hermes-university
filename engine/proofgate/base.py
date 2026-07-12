"""Proof-gate interface + registry."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class ProofResult(BaseModel):
    passed: bool
    score: float = 0.0  # 0..1 where meaningful; gates may return 1.0/0.0
    source: str  # gate name
    ref: str | None = None  # submission id / url / commit
    detail: str | None = None


class ProofGate(ABC):
    name: str

    @abstractmethod
    def verify(self, evidence: dict) -> ProofResult:
        """Whether the evidence proves the work. Inject network via evidence/fetcher so it stays
        testable and deterministic."""
        ...


_REGISTRY: dict[str, ProofGate] = {}


def register_gate(name: str, gate: ProofGate) -> None:
    gate.name = name
    _REGISTRY[name] = gate


def get_gate(name: str) -> ProofGate:
    if name not in _REGISTRY:
        raise KeyError(f"no proof-gate named {name!r}; have {sorted(_REGISTRY)}")
    return _REGISTRY[name]
