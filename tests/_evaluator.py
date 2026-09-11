# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""A reference evaluator satisfying the ``LaneEvaluator`` port for the suite:
the specification's assignment procedure (prohibited, refused, reserved, then
the graded auto-or-human split) over the one-gate patch ``preview_patch``
compiles. Hosts inject their own; this one exists so the projection can be
exercised without any host."""
from __future__ import annotations

from typing import Any, Optional

from loomground_governance import vocabulary

RISKS = list(vocabulary("risk")["levels"])
_RISK_RANK = {r: i for i, r in enumerate(RISKS)}
GRADES = list(vocabulary("grades")["levels"])
VERDICTS = list(vocabulary("verdicts")["restrictiveness_order"])


def grade_rank(grade: Any) -> int:
    if isinstance(grade, bool) or grade is None:
        return -1
    if isinstance(grade, int):
        return grade if 0 <= grade < len(GRADES) else -1
    return GRADES.index(grade) if grade in GRADES else -1


def grade_meets(granted: Any, required: Any) -> bool:
    if required is None:
        return True
    rr = grade_rank(required)
    return rr >= 0 and grade_rank(granted) >= rr


def guard_holds(guard: Optional[str], token: dict[str, Any], eff_risk: str) -> bool:
    if not guard:
        return True
    parts = guard.split()
    if len(parts) != 3:
        return False
    field, op, val = parts
    if field in ("kind", "party") and op == "=":
        return token.get(field) == val
    if field == "risk":
        tr, vr = _RISK_RANK.get(eff_risk, -1), _RISK_RANK.get(val, 10**9)
        return tr >= vr if op == ">=" else (tr == vr if op == "=" else False)
    if field == "tags" and op == "contains":
        tags = token.get("tags")
        return isinstance(tags, list) and val in tags
    return False


def evaluate_log(patch: dict[str, Any], transport: dict[str, Any]) -> list[dict[str, str]]:
    by_id = {n["id"]: n for n in patch.get("nodes", [])}
    authority = {(c["from"], c["to"]) for c in patch.get("cords", [])
                 if c.get("type") == "authority"}
    log: list[dict[str, str]] = []
    for act in transport.get("activations", []):
        token, gate_id, actor = act["token"], act["source"], act.get("actor")
        gate = by_id.get(gate_id) or {}
        floor = gate.get("risk_floor") or RISKS[0]
        eff = RISKS[max(_RISK_RANK.get(token.get("risk"), 0), _RISK_RANK.get(floor, 0))]
        kind = token.get("kind")
        if any(p.get("kind") == kind and guard_holds(p.get("when"), token, eff)
               for p in patch.get("prohibitions", [])):
            verdict = "prohibited"
        elif (actor, gate_id) not in authority:
            verdict = "refused"
        elif any(r.get("kind") == kind and guard_holds(r.get("when"), token, eff)
                 for r in patch.get("reservations", [])):
            verdict = "reserved"
        else:
            verdict = "auto"
            required = gate.get("grade_required")
            if required is not None and not grade_meets(
                    (by_id.get(actor) or {}).get("grade"), required):
                verdict = "human"
        log.append({"gate": gate_id, "verdict": verdict})
    return log


class ReferenceEvaluator:
    evaluate_log = staticmethod(evaluate_log)
    guard_holds = staticmethod(guard_holds)
