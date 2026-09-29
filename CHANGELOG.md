<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright 2026 flxk1 -->
# Changelog

## [0.1.1](https://github.com/flxk1/loomground-lane/compare/loomground-lane-v0.1.0...loomground-lane-v0.1.1) (2026-09-27)


### Documentation

* correct stale claims; add How this is made ([103bf74](https://github.com/flxk1/loomground-lane/commit/103bf7424a75ed2949a78618888bd33a46c1ae6b))
* How this is made names no model vendor ([c2898e4](https://github.com/flxk1/loomground-lane/commit/c2898e4c263555702f2b8809f28fd575f68ba9e5))
* install from git; add How this is made; align NOTICE ([36fb33f](https://github.com/flxk1/loomground-lane/commit/36fb33fce05548b89c2f763f1e52e142aa89e9a9))

## 0.1.0

* Published `governance_lane.py` as `loomground_lane.governance_lane`; its capability projection algebra lives in `loomground_lane.lane_capabilities`, with compiled graph, enforcement evaluator, auto-grade threshold, and lane lookup injected as ports. The public host seam is in `docs/seam.md`.
* Decoupled from the host: `ActionRequest` is replaced by the structural `LaneRequest` protocol (the five attributes `evaluate_lane` reads); the grade lattice, the risk levels, the verdict alphabet and the language version are read from `loomground_governance.vocabulary(...)` / `language_version()` and declared nowhere in `src/`.
* Lane versions are appended to the signed chain through `loomground_audit_chain.mutation_log.{MutationLog, LogEvent}`; event kinds `governance-lane-approved` and the legacy `autonomy-lane-approved` are preserved.
* `preview_patch` gains the keyword-only `grade_required`; `lane_capabilities` gains the keyword-only ports `graph`, `evaluator`, `auto_grade_min`, `lane_lookup`.
* Licence: Apache-2.0 (code) and CC-BY-4.0 (README), relicensed by the sole rights holder, flxk1.
