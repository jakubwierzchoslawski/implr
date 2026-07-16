# Status Vocabulary

**Machine-readable source of truth:** `status-vocabulary.json` (this directory).

This is the ONLY place implr defines legal states and transitions for its four artefact state
machines — `requirement`, `plan`, `review`, and `cr`. Other files must reference this vocabulary
by name rather than re-deriving it. The one permitted exception is a **schema/template display
comment** (e.g. `status: ready   # ready | in-progress | done | blocked | needs-rework` in
`plan-schema.md`): these mirror the JSON for human readers and are allowed ONLY because
`implr-validate --repo` validates every such comment against the JSON and fails the build on any
divergence. Free prose (README, WORKFLOW, agents, SKILLs) must NOT hardcode a status list.

To read the states and transitions, open `status-vocabulary.json`; each machine lists its
`states`, `initial`, `terminal`, and `transitions` (with the actor that performs each). This
document itself does NOT restate the state values — it is not a validated display surface.
