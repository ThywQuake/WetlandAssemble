# M001: Current-State Audit and Recovery Control Plane

## Vision
Establish an authoritative, evidence-graded understanding of what this repository has already done, what route is actually current, which retained paths are misleading, and what the next concrete step should be before further implementation continues.

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | Canonical Surface Inventory | high | — | ✅ | After this: there is one evidence-backed inventory of code, scripts, tests, docs, stash history, results, temp surfaces, TODOs, and branch state, so re-entry no longer starts from blind exploration. |
| S02 | Phase & Module State Matrix | high | — | ✅ | After this: each major phase and module has a status grade with evidence behind it, and local proof is clearly separated from HPC-only proof. |
| S03 | Route Audit & Risk Register | medium | — | ✅ | After this: the project has an explicit list of current recommended routes, stale or misleading routes, and the risks attached to each one. |
| S04 | Next-Step Execution Map | medium | — | ✅ | After this: there is a concrete continuation path showing where to enter next, what to verify first, and which routes to avoid touching initially. |
| S05 | Operator Recovery Pack | low | — | ✅ | After this: a future re-entry can recover control quickly from compact milestone artifacts instead of replaying the entire repository history. |
