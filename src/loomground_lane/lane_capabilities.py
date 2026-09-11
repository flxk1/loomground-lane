# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""The agent-facing projection of ONE lane's boundaries.

A dry run of the host's gate over the candidate ``kind x risk`` space, returned
in a machine shape. Four fences: advisory (flagged ``advisory: true``, changes
no enforcement); one source of truth (verdicts come from the injected
evaluator over a patch compiled from the injected graph, nothing authored
here); fail-closed (an unreadable policy projects zero capabilities, an
unknown verdict clamps to the most restrictive symbol); preview == enforcement
(each cell is the evaluator's own terminal verdict for the same inputs).

Pure projection: no writes, no model calls. Host inputs are ports:

* ``graph`` — the compiled governance graph (dict), or a callable
  ``(folder, log_root=...) -> dict`` invoked inside the fail-closed read.
* ``evaluator`` — :class:`LaneEvaluator`: ``evaluate_log`` and ``guard_holds``.
* ``auto_grade_min`` — the host's auto threshold (a rank or a grade level).
* ``lane_lookup`` — ``(folder, actor, log_root=...) -> GovernanceLane | None``.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Optional, Protocol, Union

from . import _vocabulary as V
from .governance_lane import GovernanceLane, get_lane

__all__ = ["LaneEvaluator", "SCHEMA_KIND", "lane_capabilities", "preview_patch"]

SCHEMA_KIND = "lane_capabilities/v1"

_DEFAULT_DENY = "not granted at any gate (default-deny)"
_ESCALATION_SEVERED = "severed"
_ESCALATION_HOLD = "human-in-the-loop"
_ESCALATION_RESERVED = "designated-approver"

_NOTES = [
    "advisory projection — the gate re-decides every action at run time",
    "collapse rule: a kind whose cell is identical across all risk tiers is "
    "reported once with by_risk omitted and flat verdict fields",
]
_SOURCE = "projection of the enforced .lg policy; not an authored registry"

GraphPort = Union[dict[str, Any], Callable[..., dict[str, Any]]]
LaneLookup = Callable[..., Optional[GovernanceLane]]


class LaneEvaluator(Protocol):
    """The two enforcement calls the projection makes."""

    def evaluate_log(self, patch: dict[str, Any],
                     transport: dict[str, Any]) -> list[dict[str, str]]: ...

    def guard_holds(self, guard: Optional[str], token: dict[str, Any],
                    eff_risk: str) -> bool: ...


def _gates(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Gates by bare id: each use-case node of the compiled graph."""
    return {n["id"].split(":", 1)[1]: n
            for n in graph.get("nodes", []) if n.get("kind") == "use_case"}


def _authority_pairs(graph: dict[str, Any]) -> set[tuple[str, str]]:
    """Bare (actor, gate) pairs holding an authority cord."""
    return {(e["from"].split(":", 1)[1], e["to"].split(":", 1)[1])
            for e in graph.get("edges", []) if e.get("kind") == "authority"}


def preview_patch(
    graph: dict[str, Any], actor: str, kind: str, *, grade_required: int | str,
) -> Optional[dict[str, Any]]:
    """Compile the one-gate patch enforcement gates ``(actor, kind)`` with.

    The kind's use case is the source (and terminal) gate carrying the host's
    auto threshold as its required grade; the actor carries the use case's
    earned contract grade. Prohibitions and reservations come verbatim from
    the graph. ``None`` when the kind is unwired: no gate to enter, the
    step-(2) default-deny. Derived on every call, stored nowhere."""
    uc = _gates(graph).get(kind)
    if uc is None:
        return None
    severed = V.verdict_steps()["severed"]   # the graph flags a severed gate under the verdict's own name
    nodes: list[dict[str, Any]] = [
        {"id": actor, "class": "actor", "grade": uc.get("grade")},
        {"id": kind, "class": "gate",
         "risk_floor": uc.get("risk") or V.risk_levels()[0],
         "grade_required": grade_required},
        {"id": "master", "class": "master"},
    ]
    cords: list[dict[str, Any]] = []
    if (actor, kind) in _authority_pairs(graph):
        cords.append({"from": actor, "to": kind, "type": "authority"})
    cords.append({"from": kind, "to": "master", "type": "egress"})
    return {
        "nodes": nodes,
        "cords": cords,
        "grants": [],
        "prohibitions": ([{"kind": kind, "when": None}]
                         if uc.get(severed) else []),
        "reservations": [{"kind": kind, "when": (r.get("when") or None)}
                         for r in (uc.get("reservations") or [])],
        "obligations": [],
    }


def _eff_risk(candidate: str, floor: str) -> str:
    """The gate's effective risk: max(token risk, gate floor)."""
    rank = V.risk_rank()
    return V.risk_levels()[max(rank.get(candidate, 0), rank.get(floor, 0))]


def _refused_cell() -> dict[str, Any]:
    return {"verdict": V.verdict_steps()["denied"], "grade_required": None,
            "escalation": None, "guard": _DEFAULT_DENY}


def _cell(
    patch: dict[str, Any],
    uc: dict[str, Any],
    kind: str,
    risk: str,
    actor: str,
    tags: list[str],
    evaluator: LaneEvaluator,
    grade_required: int | str,
) -> dict[str, Any]:
    """One projected cell: the evaluator's terminal verdict for a synthesized
    activation token, attributed with grade / escalation / governing guard."""
    verdicts = V.verdicts()
    steps = V.verdict_steps()
    token = {"id": f"preview:{kind}:{risk}", "kind": kind, "risk": risk,
             "party": actor, "provenance": [], "tags": list(tags)}
    log = evaluator.evaluate_log(
        patch, {"activations": [{"source": kind, "actor": actor,
                                 "token": token}]})
    verdict = log[-1]["verdict"] if log else verdicts[-1]
    if verdict not in verdicts:
        verdict = verdicts[-1]

    grade_out: Optional[str] = None
    escalation: Optional[str] = None
    guard: Optional[str] = None
    if verdict == steps["severed"]:
        escalation = _ESCALATION_SEVERED
        guard = f"prohibit {kind}"
    elif verdict == steps["denied"]:
        guard = _DEFAULT_DENY
    elif verdict == steps["escalated"]:
        eff = _eff_risk(risk, uc.get("risk") or V.risk_levels()[0])
        governing = next(
            (r for r in (uc.get("reservations") or [])
             if evaluator.guard_holds(r.get("when") or None, token, eff)), None)
        if governing is not None:
            escalation = governing.get("reserved_to") or _ESCALATION_RESERVED
            guard = f"reserve {kind} by {escalation}"
            if governing.get("when"):
                guard += f" when {governing['when']}"
        else:
            escalation = _ESCALATION_RESERVED
            guard = f"reserve {kind}"
    else:
        grade_out = V.grade_label(grade_required)
        if verdict == steps["hold"]:
            escalation = _ESCALATION_HOLD
    return {"verdict": verdict, "grade_required": grade_out,
            "escalation": escalation, "guard": guard}


def _fail_closed(
    folder: str, actor: str, reason: str, *, readable: bool,
) -> dict[str, Any]:
    return {"ok": False, "kind": SCHEMA_KIND, "folder_context": folder,
            "actor": actor, "advisory": True, "readable": readable,
            "reason": reason, "capabilities": []}


def _compiled(graph: GraphPort, folder: str, log_root: Optional[str]) -> dict[str, Any]:
    if callable(graph):
        return graph(folder, log_root=log_root) or {}
    return graph or {}


def lane_capabilities(
    folder_context: str,
    actor: str,
    *,
    graph: GraphPort,
    evaluator: LaneEvaluator,
    auto_grade_min: int | str,
    kinds: Optional[list[str]] = None,
    risks: Optional[list[str]] = None,
    log_root: Optional[str] = None,
    lane_lookup: LaneLookup = get_lane,
) -> dict[str, Any]:
    """Project ONE agent's lane boundaries. Read-only.

    For every candidate kind (the lane's action_classes and use_cases together
    with the graph's wired kinds) and every risk tier of the vocabulary: the
    verdict the gate would dispose, the grade required for the releasing
    verdict, the escalation point and the governing guard. Stamped with the
    lane's ``policy_fingerprint`` so a stale copy identifies itself."""
    folder = str(Path(folder_context).expanduser().resolve())
    try:
        lane = lane_lookup(folder, actor, log_root=log_root)
        compiled = _compiled(graph, folder, log_root) if lane is not None else {}
    except Exception as exc:  # noqa: BLE001 — any failed read projects nothing
        return _fail_closed(folder, actor,
                            f"policy unreadable: {type(exc).__name__}: {exc}",
                            readable=False)
    if lane is None:
        return _fail_closed(folder, actor, "no active governance lane",
                            readable=True)

    rank = V.risk_rank()
    risk_axis = [r for r in (risks if risks is not None else V.risk_levels())
                 if r in rank]
    if not risk_axis:
        return _fail_closed(folder, actor,
                            "no candidate risk tier is in the risk vocabulary",
                            readable=True)

    gates = _gates(compiled)
    lane_kinds = set(lane.action_classes) | set(lane.use_cases)
    if kinds is not None:
        candidates = list(dict.fromkeys(kinds))
    else:
        candidates = sorted(lane_kinds | set(gates))

    capabilities: list[dict[str, Any]] = []
    for kind in candidates:
        uc = gates.get(kind)
        if uc is None:
            cells = {r: _refused_cell() for r in risk_axis}
        else:
            patch = preview_patch(compiled, actor, kind,
                                  grade_required=auto_grade_min)
            tags = list(uc.get("tags") or [])
            cells = {r: _cell(patch or {}, uc, kind, r, actor, tags,
                              evaluator, auto_grade_min)
                     for r in risk_axis}
        entry: dict[str, Any] = {"kind": kind,
                                 "in_lane": kind in lane_kinds,
                                 "wired": uc is not None}
        first = cells[risk_axis[0]]
        if all(cells[r] == first for r in risk_axis):
            entry.update(first)
        else:
            entry["by_risk"] = cells
        capabilities.append(entry)

    return {
        "ok": True,
        "kind": SCHEMA_KIND,
        "folder_context": folder,
        "actor": actor,
        "advisory": True,
        "readable": True,
        "provenance": {
            "policy_fingerprint": lane.policy_fingerprint,
            "lane_id": lane.lane_id,
            "lane_version": lane.version,
            "language_version": V.language_version(),
            "max_grade": lane.max_grade,
            "derived_at": time.time(),
            "source": _SOURCE,
        },
        "risk_axis": risk_axis,
        "capabilities": capabilities,
        "notes": list(_NOTES),
    }
