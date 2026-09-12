<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright 2026 flxk1 -->
# Host seam

`loomground-lane` owns durable governance-lane records and the capability
projection algebra. A host supplies its compiled graph, evaluator, automatic
grade threshold, and optional lane lookup through explicit ports.

## Public surface

- `governance_lane`: `GovernanceLane`, `LaneDecision`, `LaneRequest`,
  `evaluate_lane`, `register_lane`, `get_lane`, `list_lanes`; event kinds
  `governance-lane-approved` and legacy `autonomy-lane-approved`.
- `lane_capabilities`: `SCHEMA_KIND`, `LaneEvaluator`, `lane_capabilities`,
  `preview_patch`.

`LaneRequest` is structural. It reads `agent`, `action_class`,
`autonomy_grade`, `footprint`, and `folder`; any object with those attributes
is accepted. The agent and folder must match the lane, action class and
footprint must remain within it, and the requested grade may not exceed
`max_grade`. Unknown grades rank at the floor and still surface as invalid
input through the vocabulary checks.

## Capability ports

| Port | Shape |
|---|---|
| `graph` | A compiled graph dict, or `(folder, log_root=) -> dict`. Use-case nodes carry `id`, `grade`, `risk`, severing and reservation fields; authority edges connect actors. |
| `evaluator` | `evaluate_log(patch, transport) -> verdict rows` and `guard_holds(when, token, effective_risk) -> bool`. |
| `auto_grade_min` | A grade level or rank used as `grade_required` in preview patches. |
| `lane_lookup` | `(folder, actor, log_root=) -> GovernanceLane | None`; defaults to `get_lane`. |

`RISKS`, `VERDICTS`, `LANGUAGE_VERSION`, and `grade_levels()` come directly
from `loomground_governance`. The projection derives verdict roles from that
vocabulary instead of spelling them in source. A port error or absent graph
returns the documented fail-closed payload.

## Adapter sketch

```python
from loomground_lane import lane_capabilities

result = lane_capabilities(
    folder,
    actor,
    graph=compile_governance_graph,
    evaluator=language_engine,
    auto_grade_min="L2",
    lane_lookup=find_lane,
    log_root=log_root,
)
```

A registered lane is the vocabulary's `human` verdict made durable: an
attributed approver decision on the signed audit chain. Later `auto` runs are
checked against that envelope on every iteration. Tests compare preview cells
with the reference evaluator and, when installed, the Loomground solver.
