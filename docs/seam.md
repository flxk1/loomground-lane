<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright 2026 flxk1 -->
# Seam: RVND → loomground-lane

Source: RVND commit `bac579b`, `server/src/rvnd/governance_lane.py` and `server/src/rvnd/lane_capabilities.py`. Behaviour, event kinds, output shapes and error texts are preserved except where a host reference had to become a port or a vocabulary read (listed below).

## Module map

| RVND module (bac579b) | Package module | Move |
|---|---|---|
| `rvnd/governance_lane.py` | `loomground_lane/governance_lane.py` | whole |
| `rvnd/lane_capabilities.py` | `loomground_lane/lane_capabilities.py` | projection algebra only |
| — | `loomground_lane/_vocabulary.py` | new: readers over `loomground_governance` |

## Preserved public names

From `seam-surface.json`; importable from the submodule and from `loomground_lane`.

- `governance_lane`: `GovernanceLane`, `LaneDecision`, `evaluate_lane`, `get_lane`, `list_lanes`, `register_lane`. Also: `LaneRequest`, `EVENT_KIND` (`"governance-lane-approved"`), `LEGACY_EVENT_KIND` (`"autonomy-lane-approved"`).
- `lane_capabilities`: `SCHEMA_KIND` (`"lane_capabilities/v1"`), `lane_capabilities`, `preview_patch`. Also: `LaneEvaluator`.

Signatures kept: `evaluate_lane(lane, req, *, use_case_id="", connector_id="", policy_fingerprint="")`, `register_lane(folder, lane, *, log_root=None)`, `get_lane(folder, agent, *, log_root=None)`, `list_lanes(folder, *, log_root=None)`, `lane_capabilities(folder_context, actor, *, kinds=None, risks=None, log_root=None, …ports)`, `preview_patch(graph, actor, kind, *, grade_required)`.

Text changes: `GovernanceLane.__post_init__` reports `max_grade must be one of <levels>` (RVND spelled the two end grades). Violation texts, `LaneDecision` shape, the fail-closed payload, `_NOTES`, `_SOURCE`, `_DEFAULT_DENY` and the escalation strings `severed` / `human-in-the-loop` / `designated-approver` are unchanged.

## `LaneRequest` protocol

`evaluate_lane` reads exactly these attributes of `req`; any object carrying them satisfies the (runtime-checkable) protocol, RVND's `action_gate.ActionRequest` unchanged among them.

| Attribute | Type | Read as |
|---|---|---|
| `agent` | `str` | must equal `lane.agent` |
| `action_class` | `str` | must be in `lane.action_classes` |
| `autonomy_grade` | `str` | rank via `vocabulary("grades")` must be ≤ `lane.max_grade`; an unknown level ranks at the floor |
| `footprint` | `tuple[str, ...]` | must be ⊆ `lane.footprints` |
| `folder` | `str` | must equal `lane.folder` when the lane sets one |

## Injected ports of `lane_capabilities`

| Port | Shape | RVND binding |
|---|---|---|
| `graph` | compiled governance graph `dict` (`nodes` with `kind == "use_case"`, `id == "uc:<kind>"`, `grade`, `risk`, `prohibited`, `reservations[{reserved_to, when}]`, `tags`; `edges` with `kind == "authority"`), or a callable `(folder, log_root=) -> dict` invoked inside the fail-closed read | `lambda folder, log_root: governance_graph(folder, log_root=log_root)` |
| `evaluator` | `LaneEvaluator`: `evaluate_log(patch, transport) -> [{gate, verdict}]`, `guard_holds(when, token, eff_risk) -> bool` | `adapters.solver.loomground.{evaluate_log, _guard_holds}` |
| `auto_grade_min` | a rank into `vocabulary("grades")["levels"]` or a level; carried verbatim into the patch's `grade_required`, reported as the level | `operations.AUTO_GRADE_MIN` |
| `lane_lookup` | `(folder, actor, log_root=) -> GovernanceLane | None`; default `get_lane` | default |

`RISKS`, `VERDICTS`, `LANGUAGE_VERSION`, `grade_levels()` come from `loomground_governance.vocabulary("risk")`, `vocabulary("verdicts")["restrictiveness_order"]`, `language_version()`, `vocabulary("grades")`. The verdict names the projection compares against are derived from the vocabulary's structure (`assignment_priority[:3]` for the three precedence steps, `releases_at_master` for the releasing verdict, the remaining alphabet member for the graded hold), so `src/` spells out none of them. The compiled graph's severed-gate flag is read under the severed verdict's own name (RVND's `prohibited` field).

## What stays in RVND, and why

- `rvnd/action_gate.py` (`ActionRequest`) — the host's gate type; satisfied structurally by `LaneRequest`.
- `rvnd/governance_graph.py` — compiles the host's chain (use cases, parties, contracts, runs, connectors) into the graph; host storage and host concepts. Injected as `graph`.
- `rvnd/operations.py` (`AUTO_GRADE_MIN`) — the host's run-path threshold; a deployer setting, injected as `auto_grade_min`.
- `rvnd/adapters/solver/loomground.py` — the host's binding of the language engine; injected as `evaluator`. Only the vocabulary constants it re-exports are read here, directly from `loomground_governance`.
- `rvnd/adapters/policy_languages.py` (`grade_index`, `grade_levels`) — RVND's readers; the package has its own in `_vocabulary`.
- `mcp_server` verbs (`governance_lane_register`, `governance_lane_list`, `lane_capabilities`), `session_admission.governance_open`, `governance.decide_action` — host surfaces and the chokepoint; their tests stay with RVND, the lane halves are ported under `tests/`.

## How RVND wires it

One adapter, `rvnd/adapters/lane.py`, binds the ports:

```python
from loomground_lane.governance_lane import *   # GovernanceLane, LaneDecision, evaluate_lane, ...
from loomground_lane.lane_capabilities import SCHEMA_KIND
from loomground_lane.lane_capabilities import lane_capabilities as _caps
from loomground_lane.lane_capabilities import preview_patch as _preview

class _Evaluator:
    from .solver.loomground import evaluate_log, _guard_holds as guard_holds

def _graph(folder, *, log_root):
    from ..governance_graph import governance_graph
    return governance_graph(folder, log_root=log_root)

def _auto_grade_min():
    from ..operations import AUTO_GRADE_MIN
    return AUTO_GRADE_MIN

def lane_capabilities(folder_context, actor, *, kinds=None, risks=None, log_root=None):
    return _caps(folder_context, actor, graph=_graph, evaluator=_Evaluator(),
                 auto_grade_min=_auto_grade_min(), kinds=kinds, risks=risks, log_root=log_root)

def preview_patch(graph, actor, kind):
    return _preview(graph, actor, kind, grade_required=_auto_grade_min())
```

`rvnd/governance_lane.py` becomes import-only (`from .adapters.lane import GovernanceLane, LaneDecision, evaluate_lane, register_lane, get_lane, list_lanes`); `rvnd/lane_capabilities.py` becomes the wiring above re-exporting `SCHEMA_KIND, lane_capabilities, preview_patch`. RVND's `test_fail_closed_never_all_allowed` monkeypatches `rvnd.lane_capabilities.get_lane`; the wiring should pass `lane_lookup=get_lane` from its own namespace so that patch keeps working.

## Grounding

A registered lane is the vocabulary's `human` verdict made durable: a named approver's attributed decision on the signed chain, against which an agent's later `auto` dispositions are checked on every iteration. The projection's cells are the injected evaluator's own terminal verdicts; `tests/test_lane_capabilities.py::test_preview_equals_enforcement` holds the fence over a reference evaluator, and `…_against_the_language_engine` holds it over `loomground_solver.loomground` when that engine is importable.
