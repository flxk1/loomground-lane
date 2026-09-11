# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Readers over the governance vocabulary. Every grade, risk and verdict symbol
this package compares against is read here; nothing is spelled out locally."""
from __future__ import annotations

from functools import lru_cache

from loomground_governance import language_version as _language_version
from loomground_governance import vocabulary as _vocabulary


def _ordered_levels(name: str) -> tuple[str, ...]:
    vocab = _vocabulary(name)
    levels = tuple(str(level) for level in vocab["levels"])
    order = vocab.get("order")
    if order:
        declared = tuple(part.strip() for part in str(order).split("<"))
        if declared != levels:
            raise ValueError(f"vocabulary {name!r}: order and levels disagree")
    return levels


@lru_cache(maxsize=None)
def grade_levels() -> tuple[str, ...]:
    return _ordered_levels("grades")


def grade_index() -> dict[str, int]:
    return {grade: rank for rank, grade in enumerate(grade_levels())}


def grade_label(value: int | str) -> str:
    """A rank or a level to its level; anything outside the lattice raises."""
    levels = grade_levels()
    if isinstance(value, bool):
        raise ValueError(f"grade {value!r} is outside the lattice")
    if isinstance(value, int):
        if 0 <= value < len(levels):
            return levels[value]
        raise ValueError(f"grade rank {value} is outside the lattice")
    if value in levels:
        return value
    raise ValueError(f"grade {value!r} is outside the lattice")


@lru_cache(maxsize=None)
def risk_levels() -> tuple[str, ...]:
    return _ordered_levels("risk")


def risk_rank() -> dict[str, int]:
    return {risk: rank for rank, risk in enumerate(risk_levels())}


@lru_cache(maxsize=None)
def verdicts() -> tuple[str, ...]:
    """The verdict alphabet in restrictiveness order; the last entry is the
    most restrictive and the fail-safe clamp."""
    return tuple(str(v) for v in _vocabulary("verdicts")["restrictiveness_order"])


@lru_cache(maxsize=None)
def verdict_steps() -> dict[str, str]:
    """Verdict names by their place in the vocabulary's assignment procedure:
    the three precedence steps, the one verdict the master releases, and the
    graded hold (the alphabet member left once those four are named)."""
    vocab = _vocabulary("verdicts")
    alphabet = tuple(str(v) for v in vocab["alphabet"])
    steps = [str(s) for s in vocab["assignment_priority"]]
    named = [s for s in steps if s in alphabet]
    if len(named) != 3:
        raise ValueError("verdict vocabulary: expected three named precedence steps")
    releasing = [v for v, released in vocab["releases_at_master"].items() if released]
    if len(releasing) != 1:
        raise ValueError("verdict vocabulary: expected one releasing verdict")
    rest = [v for v in alphabet if v not in named and v != releasing[0]]
    if len(rest) != 1:
        raise ValueError("verdict vocabulary: expected one graded hold verdict")
    return {"severed": named[0], "denied": named[1], "escalated": named[2],
            "releasing": releasing[0], "hold": rest[0]}


def language_version() -> str:
    return _language_version()
