# implr Studio — Plan 3: Orchestrator & Run Persistence

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute a pipeline: schedule eligible nodes, open gates, run steps through the `StepExecutor` contract, surface questions, handle failure/retry/skip/approve, and persist everything to SQLite so a service restart resumes rather than loses a run.

**Architecture:** `store.py` owns SQLite and knows nothing about scheduling. `orchestrator.py` owns the state machine and drives one sequential loop per run (concurrency cap is 1 in Phase 1). Every state transition and log line is written to the store **before** it is observable, so the persisted record is never behind what a client has seen. All tests run against `FakeExecutor` — this plan costs zero tokens to verify.

**Tech Stack:** Python 3.11+, `sqlite3` (stdlib), `asyncio`, pytest, pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-08-25-implr-studio-design.md`

## Global Constraints

- Gate decisions read the **filesystem** via `gates.evaluate_gate`. An `artifact` StepEvent is advisory and must never influence scheduling.
- Concurrency cap is **1** in Phase 1. The scheduler is written to select many eligible nodes, but the driver runs them one at a time.
- Persist before broadcast: write the state change to SQLite, then let it become visible. Never the reverse.
- A node that was `running` when the process died is recovered as `failed`, never as `running` or silently retried. The child process did not survive; reporting otherwise would be false.
- No module in this plan may import from `executors/fake.py`. The fake is a test fixture only.
- Timestamps are UTC ISO-8601 via `datetime.now(timezone.utc).isoformat()`.

---

## File Structure

| File | Responsibility |
|---|---|
| `studio/backend/implr_studio/runstate.py` | Node/run status constants and terminal-set helpers. No logic. |
| `studio/backend/implr_studio/store.py` | SQLite schema and all persistence. No scheduling knowledge. |
| `studio/backend/implr_studio/orchestrator.py` | Eligibility, gate opening, the driver loop, operator actions, recovery. |
| `studio/backend/tests/test_store.py` | Persistence round-trips and the event cursor. |
| `studio/backend/tests/test_orchestrator_scheduling.py` | Eligibility and gate opening, without executing anything. |
| `studio/backend/tests/test_orchestrator_execution.py` | End-to-end runs against `FakeExecutor`, including questions. |
| `studio/backend/tests/test_orchestrator_recovery.py` | Failure, retry, skip, approve, cancel, restart recovery. |

---

### Task 1: Run state vocabulary

**Files:**
- Create: `studio/backend/implr_studio/runstate.py`
- Test: `studio/backend/tests/test_runstate.py`

**Interfaces:**
- Produces:
  - Node statuses: `PENDING`, `BLOCKED`, `RUNNING`, `AWAITING_INPUT`, `AWAITING_APPROVAL`, `SUCCEEDED`, `FAILED`, `SKIPPED`, `CANCELLED` (string constants with the hyphenated wire values).
  - Run statuses: `RUN_RUNNING`, `RUN_PAUSED`, `RUN_SUCCEEDED`, `RUN_FAILED`, `RUN_CANCELLED`.
  - `NODE_TERMINAL: frozenset` = succeeded, failed, skipped, cancelled.
  - `NODE_SATISFIES_DEPENDENCY: frozenset` = succeeded, skipped.
  - `RUN_TERMINAL: frozenset` = succeeded, failed, cancelled.
  - `is_terminal(status) -> bool`, `satisfies_dependency(status) -> bool`.

- [ ] **Step 1: Write the failing test**

Create `studio/backend/tests/test_runstate.py`:

```python
from implr_studio import runstate as rs


def test_wire_values_are_hyphenated():
    assert rs.AWAITING_INPUT == "awaiting-input"
    assert rs.AWAITING_APPROVAL == "awaiting-approval"
    assert rs.PENDING == "pending"


def test_terminal_set():
    assert rs.NODE_TERMINAL == frozenset({"succeeded", "failed", "skipped", "cancelled"})
    assert rs.is_terminal(rs.SUCCEEDED) is True
    assert rs.is_terminal(rs.RUNNING) is False


def test_only_succeeded_and_skipped_satisfy_a_dependency():
    """A failed upstream must never release a downstream node."""
    assert rs.satisfies_dependency(rs.SUCCEEDED) is True
    assert rs.satisfies_dependency(rs.SKIPPED) is True
    assert rs.satisfies_dependency(rs.FAILED) is False
    assert rs.satisfies_dependency(rs.CANCELLED) is False
    assert rs.satisfies_dependency(rs.RUNNING) is False


def test_run_terminal_set():
    assert rs.RUN_TERMINAL == frozenset({"succeeded", "failed", "cancelled"})
    assert rs.RUN_PAUSED not in rs.RUN_TERMINAL
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd studio/backend && python -m pytest tests/test_runstate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'implr_studio.runstate'`

- [ ] **Step 3: Write the implementation**

Create `studio/backend/implr_studio/runstate.py`:

```python
"""Status vocabulary for runs and node runs.

Deliberately separate from implr's artefact state machines in
status-vocabulary.json: those describe requirements and plans on disk, these
describe one execution of a pipeline. Do not conflate them.
"""

PENDING = "pending"
BLOCKED = "blocked"
RUNNING = "running"
AWAITING_INPUT = "awaiting-input"
AWAITING_APPROVAL = "awaiting-approval"
SUCCEEDED = "succeeded"
FAILED = "failed"
SKIPPED = "skipped"
CANCELLED = "cancelled"

NODE_STATUSES = (
    PENDING, BLOCKED, RUNNING, AWAITING_INPUT, AWAITING_APPROVAL,
    SUCCEEDED, FAILED, SKIPPED, CANCELLED,
)

NODE_TERMINAL = frozenset({SUCCEEDED, FAILED, SKIPPED, CANCELLED})

# Only these release a downstream node. A failed or cancelled upstream must not.
NODE_SATISFIES_DEPENDENCY = frozenset({SUCCEEDED, SKIPPED})

RUN_RUNNING = "running"
RUN_PAUSED = "paused"
RUN_SUCCEEDED = "succeeded"
RUN_FAILED = "failed"
RUN_CANCELLED = "cancelled"

RUN_STATUSES = (RUN_RUNNING, RUN_PAUSED, RUN_SUCCEEDED, RUN_FAILED, RUN_CANCELLED)
RUN_TERMINAL = frozenset({RUN_SUCCEEDED, RUN_FAILED, RUN_CANCELLED})


def is_terminal(status: str) -> bool:
    return status in NODE_TERMINAL


def satisfies_dependency(status: str) -> bool:
    return status in NODE_SATISFIES_DEPENDENCY
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd studio/backend && python -m pytest tests/test_runstate.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add studio/backend/implr_studio/runstate.py studio/backend/tests/test_runstate.py
git commit -m "feat(studio): run and node status vocabulary"
```

---

### Task 2: SQLite store

**Files:**
- Create: `studio/backend/implr_studio/store.py`
- Test: `studio/backend/tests/test_store.py`

**Interfaces:**
- Consumes: `runstate` constants from Task 1; `pipeline.pipeline_to_dict` / `pipeline_from_dict` from Plan 1 Task 3.
- Produces:
  - `Store(db_path: Path)` — creates the schema on construction (idempotent).
  - `Store.create_run(run_id: str, pipeline: Pipeline, node_ids: list[str]) -> None` — inserts the run plus one `node_runs` row per node at status `pending`.
  - `Store.get_run(run_id) -> dict | None` — keys `id`, `status`, `pipeline`, `created_at`, `updated_at`.
  - `Store.list_runs() -> list[dict]` — newest first, without the pipeline body.
  - `Store.set_run_status(run_id, status) -> None`
  - `Store.get_node(run_id, node_id) -> dict | None` — keys `node_id`, `status`, `summary`, `error`, `manual_approved`, `started_at`, `finished_at`.
  - `Store.get_nodes(run_id) -> dict[str, dict]`
  - `Store.set_node_status(run_id, node_id, status, summary=None, error=None) -> None` — stamps `started_at` on first entry to `running`, `finished_at` on any terminal status.
  - `Store.set_manual_approved(run_id, node_id) -> None`
  - `Store.append_event(run_id, node_id, kind, payload: dict) -> int` — returns the monotonic `seq`.
  - `Store.events_since(run_id, cursor: int = 0, limit: int = 1000) -> list[dict]` — keys `seq`, `node_id`, `kind`, `payload`, `created_at`.
  - `Store.create_question(question_id, run_id, node_id, prompt_md, options) -> None`
  - `Store.get_question(question_id) -> dict | None`
  - `Store.answer_question(question_id, text) -> None`
  - `Store.pending_question(run_id, node_id) -> dict | None` — the unanswered question, if any.
  - `Store.close() -> None`

- [ ] **Step 1: Write the failing test**

Create `studio/backend/tests/test_store.py`:

```python
from pathlib import Path

import pytest

from implr_studio import runstate as rs
from implr_studio import pipeline
from implr_studio.store import Store

PIPE = {
    "version": 1,
    "nodes": [{"id": "a", "step": "doc-ingest"}, {"id": "b", "step": "arch-gen"}],
    "edges": [{"from": "a", "to": "b"}],
}


@pytest.fixture
def store(tmp_path: Path) -> Store:
    s = Store(tmp_path / "runs.db")
    yield s
    s.close()


def _make_run(store: Store, run_id: str = "r1") -> pipeline.Pipeline:
    p = pipeline.pipeline_from_dict(PIPE)
    store.create_run(run_id, p, [n.id for n in p.nodes])
    return p


def test_schema_is_created_idempotently(tmp_path: Path):
    path = tmp_path / "runs.db"
    Store(path).close()
    Store(path).close()          # must not raise on a second open


def test_create_and_get_run(store: Store):
    p = _make_run(store)

    run = store.get_run("r1")

    assert run["id"] == "r1"
    assert run["status"] == rs.RUN_RUNNING
    assert run["pipeline"] == p


def test_get_missing_run_returns_none(store: Store):
    assert store.get_run("nope") is None


def test_nodes_start_pending(store: Store):
    _make_run(store)

    nodes = store.get_nodes("r1")

    assert set(nodes) == {"a", "b"}
    assert nodes["a"]["status"] == rs.PENDING
    assert nodes["a"]["manual_approved"] == 0


def test_set_node_status_stamps_started_at_on_running(store: Store):
    _make_run(store)

    store.set_node_status("r1", "a", rs.RUNNING)

    node = store.get_node("r1", "a")
    assert node["status"] == rs.RUNNING
    assert node["started_at"] is not None
    assert node["finished_at"] is None


def test_set_node_status_stamps_finished_at_on_terminal(store: Store):
    _make_run(store)
    store.set_node_status("r1", "a", rs.RUNNING)

    store.set_node_status("r1", "a", rs.SUCCEEDED, summary="12 docs")

    node = store.get_node("r1", "a")
    assert node["finished_at"] is not None
    assert node["summary"] == "12 docs"


def test_started_at_is_not_overwritten_on_retry(store: Store):
    """Retrying a node keeps the original start time for run duration reporting."""
    _make_run(store)
    store.set_node_status("r1", "a", rs.RUNNING)
    first = store.get_node("r1", "a")["started_at"]
    store.set_node_status("r1", "a", rs.FAILED, error="boom")

    store.set_node_status("r1", "a", rs.RUNNING)

    assert store.get_node("r1", "a")["started_at"] == first


def test_failed_node_records_error(store: Store):
    _make_run(store)

    store.set_node_status("r1", "a", rs.FAILED, summary="it broke", error="exit 1")

    node = store.get_node("r1", "a")
    assert node["error"] == "exit 1"


def test_manual_approval_is_recorded(store: Store):
    _make_run(store)

    store.set_manual_approved("r1", "b")

    assert store.get_node("r1", "b")["manual_approved"] == 1


def test_events_get_monotonic_sequence_numbers(store: Store):
    _make_run(store)

    s1 = store.append_event("r1", "a", "log", {"text": "one"})
    s2 = store.append_event("r1", "a", "log", {"text": "two"})

    assert s2 > s1


def test_events_since_returns_only_newer_events(store: Store):
    _make_run(store)
    store.append_event("r1", "a", "log", {"text": "one"})
    cursor = store.append_event("r1", "a", "log", {"text": "two"})
    store.append_event("r1", "a", "log", {"text": "three"})

    later = store.events_since("r1", cursor)

    assert [e["payload"]["text"] for e in later] == ["three"]


def test_events_since_zero_returns_everything(store: Store):
    _make_run(store)
    store.append_event("r1", "a", "log", {"text": "one"})
    store.append_event("r1", "b", "log", {"text": "two"})

    assert len(store.events_since("r1", 0)) == 2


def test_events_are_scoped_to_their_run(store: Store):
    _make_run(store, "r1")
    _make_run(store, "r2")
    store.append_event("r1", "a", "log", {"text": "mine"})
    store.append_event("r2", "a", "log", {"text": "theirs"})

    assert [e["payload"]["text"] for e in store.events_since("r1", 0)] == ["mine"]


def test_question_lifecycle(store: Store):
    _make_run(store)
    store.create_question("q1", "r1", "b", "Postgres or MySQL?", None)

    pending = store.pending_question("r1", "b")
    assert pending["id"] == "q1"
    assert pending["prompt_md"] == "Postgres or MySQL?"
    assert pending["answer"] is None

    store.answer_question("q1", "Postgres")

    assert store.pending_question("r1", "b") is None
    assert store.get_question("q1")["answer"] == "Postgres"
    assert store.get_question("q1")["answered_at"] is not None


def test_question_options_round_trip(store: Store):
    _make_run(store)
    store.create_question("q1", "r1", "b", "Pick", ["a", "b"])

    assert store.get_question("q1")["options"] == ["a", "b"]


def test_list_runs_is_newest_first(store: Store):
    _make_run(store, "r1")
    _make_run(store, "r2")

    ids = [r["id"] for r in store.list_runs()]

    assert ids[0] == "r2"


def test_run_survives_reopening_the_database(tmp_path: Path):
    """The whole point of persistence: a restart must recover the run."""
    path = tmp_path / "runs.db"
    s1 = Store(path)
    p = pipeline.pipeline_from_dict(PIPE)
    s1.create_run("r1", p, ["a", "b"])
    s1.set_node_status("r1", "a", rs.SUCCEEDED)
    s1.append_event("r1", "a", "log", {"text": "persisted"})
    s1.close()

    s2 = Store(path)
    try:
        assert s2.get_run("r1")["pipeline"] == p
        assert s2.get_nodes("r1")["a"]["status"] == rs.SUCCEEDED
        assert s2.events_since("r1", 0)[0]["payload"]["text"] == "persisted"
    finally:
        s2.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd studio/backend && python -m pytest tests/test_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'implr_studio.store'`

- [ ] **Step 3: Write the implementation**

Create `studio/backend/implr_studio/store.py`:

```python
"""SQLite persistence for runs, node runs, events, and questions.

This module knows nothing about scheduling or gates. It stores what it is told
and reads it back. The `events.seq` column is the cursor the WebSocket layer
uses to replay history to a reconnecting client.
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import runstate as rs
from .pipeline import Pipeline, pipeline_from_dict, pipeline_to_dict

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id            TEXT PRIMARY KEY,
    status        TEXT NOT NULL,
    pipeline_json TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS node_runs (
    run_id          TEXT NOT NULL,
    node_id         TEXT NOT NULL,
    status          TEXT NOT NULL,
    summary         TEXT,
    error           TEXT,
    manual_approved INTEGER NOT NULL DEFAULT 0,
    started_at      TEXT,
    finished_at     TEXT,
    PRIMARY KEY (run_id, node_id)
);

CREATE TABLE IF NOT EXISTS events (
    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT NOT NULL,
    node_id      TEXT,
    kind         TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_run_seq ON events (run_id, seq);

CREATE TABLE IF NOT EXISTS questions (
    id           TEXT PRIMARY KEY,
    run_id       TEXT NOT NULL,
    node_id      TEXT NOT NULL,
    prompt_md    TEXT NOT NULL,
    options_json TEXT,
    answer       TEXT,
    answered_at  TEXT,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_questions_run_node ON questions (run_id, node_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, db_path: Path) -> None:
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # --- runs ---

    def create_run(self, run_id: str, pipeline: Pipeline, node_ids: list[str]) -> None:
        now = _now()
        with self._conn:
            self._conn.execute(
                "INSERT INTO runs (id, status, pipeline_json, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (run_id, rs.RUN_RUNNING, json.dumps(pipeline_to_dict(pipeline)), now, now),
            )
            self._conn.executemany(
                "INSERT INTO node_runs (run_id, node_id, status) VALUES (?, ?, ?)",
                [(run_id, node_id, rs.PENDING) for node_id in node_ids],
            )

    def get_run(self, run_id: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "status": row["status"],
            "pipeline": pipeline_from_dict(json.loads(row["pipeline_json"])),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_runs(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, status, created_at, updated_at FROM runs"
            " ORDER BY created_at DESC, rowid DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def set_run_status(self, run_id: str, status: str) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE runs SET status = ?, updated_at = ? WHERE id = ?",
                (status, _now(), run_id),
            )

    # --- node runs ---

    def get_node(self, run_id: str, node_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM node_runs WHERE run_id = ? AND node_id = ?", (run_id, node_id)
        ).fetchone()
        return dict(row) if row is not None else None

    def get_nodes(self, run_id: str) -> dict[str, dict]:
        rows = self._conn.execute(
            "SELECT * FROM node_runs WHERE run_id = ?", (run_id,)
        ).fetchall()
        return {r["node_id"]: dict(r) for r in rows}

    def set_node_status(
        self, run_id: str, node_id: str, status: str,
        summary: str | None = None, error: str | None = None,
    ) -> None:
        now = _now()
        sets = ["status = ?"]
        params: list = [status]
        if summary is not None:
            sets.append("summary = ?")
            params.append(summary)
        if error is not None:
            sets.append("error = ?")
            params.append(error)
        if status == rs.RUNNING:
            # COALESCE keeps the original start time across a retry.
            sets.append("started_at = COALESCE(started_at, ?)")
            params.append(now)
            sets.append("finished_at = NULL")
        if status in rs.NODE_TERMINAL:
            sets.append("finished_at = ?")
            params.append(now)
        params.extend([run_id, node_id])
        with self._conn:
            self._conn.execute(
                "UPDATE node_runs SET %s WHERE run_id = ? AND node_id = ?" % ", ".join(sets),
                params,
            )
            self._conn.execute(
                "UPDATE runs SET updated_at = ? WHERE id = ?", (now, run_id)
            )

    def set_manual_approved(self, run_id: str, node_id: str) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE node_runs SET manual_approved = 1 WHERE run_id = ? AND node_id = ?",
                (run_id, node_id),
            )

    # --- events ---

    def append_event(self, run_id: str, node_id: str | None, kind: str, payload: dict) -> int:
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO events (run_id, node_id, kind, payload_json, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (run_id, node_id, kind, json.dumps(payload), _now()),
            )
        return int(cur.lastrowid)

    def events_since(self, run_id: str, cursor: int = 0, limit: int = 1000) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM events WHERE run_id = ? AND seq > ? ORDER BY seq LIMIT ?",
            (run_id, cursor, limit),
        ).fetchall()
        return [
            {
                "seq": r["seq"],
                "node_id": r["node_id"],
                "kind": r["kind"],
                "payload": json.loads(r["payload_json"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    # --- questions ---

    def create_question(
        self, question_id: str, run_id: str, node_id: str,
        prompt_md: str, options: list[str] | None,
    ) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO questions (id, run_id, node_id, prompt_md, options_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    question_id, run_id, node_id, prompt_md,
                    json.dumps(options) if options is not None else None,
                    _now(),
                ),
            )

    def _question_row_to_dict(self, row) -> dict:
        return {
            "id": row["id"],
            "run_id": row["run_id"],
            "node_id": row["node_id"],
            "prompt_md": row["prompt_md"],
            "options": json.loads(row["options_json"]) if row["options_json"] else None,
            "answer": row["answer"],
            "answered_at": row["answered_at"],
            "created_at": row["created_at"],
        }

    def get_question(self, question_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM questions WHERE id = ?", (question_id,)
        ).fetchone()
        return self._question_row_to_dict(row) if row is not None else None

    def pending_question(self, run_id: str, node_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM questions WHERE run_id = ? AND node_id = ? AND answer IS NULL"
            " ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (run_id, node_id),
        ).fetchone()
        return self._question_row_to_dict(row) if row is not None else None

    def answer_question(self, question_id: str, text: str) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE questions SET answer = ?, answered_at = ? WHERE id = ?",
                (text, _now(), question_id),
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd studio/backend && python -m pytest tests/test_store.py -v`
Expected: 17 passed

- [ ] **Step 5: Commit**

```bash
git add studio/backend/implr_studio/store.py studio/backend/tests/test_store.py
git commit -m "feat(studio): SQLite persistence for runs, events, and questions"
```

---

### Task 3: Scheduling — eligibility and gate opening

**Files:**
- Create: `studio/backend/implr_studio/orchestrator.py`
- Test: `studio/backend/tests/test_orchestrator_scheduling.py`

**Interfaces:**
- Consumes: `runstate` (Task 1), `Store` (Task 2), `pipeline.Pipeline`/`Edge` and `gates.evaluate_gate`/`artefact_condition_holds` (Plan 1), `registry.Registry` (Plan 1).
- Produces:
  - `orchestrator.GateState` — frozen dataclass: `open: bool`, `needs_approval: bool`.
  - `orchestrator.edge_gate_state(edge, node_row, workspace, contracts) -> GateState`
  - `orchestrator.node_readiness(node_id, p, nodes, workspace, contracts) -> str` — returns one of `runstate.PENDING`, `runstate.BLOCKED`, `runstate.AWAITING_APPROVAL`, or the sentinel `orchestrator.READY`.
  - `orchestrator.READY = "ready"` — a scheduling sentinel, deliberately **not** a node status; it never appears in the store.

Readiness rules, in order:
1. Any inbound edge whose source node is not `succeeded`/`skipped` → `PENDING` (upstream still working).
2. All upstream satisfied, but some gate's artefact condition is false → `BLOCKED`.
3. All artefact conditions hold, but a manual gate is unapproved → `AWAITING_APPROVAL`.
4. Otherwise → `READY`.

A node with no inbound edges is always `READY`.

- [ ] **Step 1: Write the failing test**

Create `studio/backend/tests/test_orchestrator_scheduling.py`:

```python
from pathlib import Path

import pytest

from implr_studio import implr_bridge, orchestrator, pipeline
from implr_studio import runstate as rs


@pytest.fixture
def contracts():
    root = implr_bridge.repo_root()
    return implr_bridge.load_contracts(str(implr_bridge.resolve_schema_dir(root)))


def _write_req(workspace: Path, req_id: str, status: str) -> None:
    d = workspace / "docs" / "implr" / "requirements" / "functional"
    d.mkdir(parents=True, exist_ok=True)
    (d / ("%s.md" % req_id.lower())).write_text(
        "---\nreq_id: %s\nstatus: %s\n---\nb\n" % (req_id, status), encoding="utf-8"
    )


def _pipe(edges) -> pipeline.Pipeline:
    return pipeline.pipeline_from_dict({
        "version": 1,
        "nodes": [{"id": "a", "step": "doc-ingest"}, {"id": "b", "step": "arch-gen"}],
        "edges": edges,
    })


def _nodes(**statuses) -> dict[str, dict]:
    return {
        node_id: {"node_id": node_id, "status": status, "manual_approved": 0}
        for node_id, status in statuses.items()
    }


def test_root_node_is_ready(tmp_path, contracts):
    p = _pipe([{"from": "a", "to": "b"}])
    nodes = _nodes(a=rs.PENDING, b=rs.PENDING)

    assert orchestrator.node_readiness("a", p, nodes, tmp_path, contracts) == orchestrator.READY


def test_downstream_pending_while_upstream_runs(tmp_path, contracts):
    p = _pipe([{"from": "a", "to": "b"}])
    nodes = _nodes(a=rs.RUNNING, b=rs.PENDING)

    assert orchestrator.node_readiness("b", p, nodes, tmp_path, contracts) == rs.PENDING


def test_downstream_ready_when_upstream_succeeded_and_gate_is_none(tmp_path, contracts):
    p = _pipe([{"from": "a", "to": "b"}])
    nodes = _nodes(a=rs.SUCCEEDED, b=rs.PENDING)

    assert orchestrator.node_readiness("b", p, nodes, tmp_path, contracts) == orchestrator.READY


def test_skipped_upstream_also_releases_downstream(tmp_path, contracts):
    p = _pipe([{"from": "a", "to": "b"}])
    nodes = _nodes(a=rs.SKIPPED, b=rs.PENDING)

    assert orchestrator.node_readiness("b", p, nodes, tmp_path, contracts) == orchestrator.READY


def test_failed_upstream_leaves_downstream_pending(tmp_path, contracts):
    """A failed upstream must never release its dependents."""
    p = _pipe([{"from": "a", "to": "b"}])
    nodes = _nodes(a=rs.FAILED, b=rs.PENDING)

    assert orchestrator.node_readiness("b", p, nodes, tmp_path, contracts) == rs.PENDING


def test_artifact_gate_blocks_until_frontmatter_satisfies_it(tmp_path, contracts):
    p = _pipe([{
        "from": "a", "to": "b",
        "gate": {"type": "artifact", "artefact": "requirement",
                 "quantifier": "all", "require": {"status": "approved"}},
    }])
    nodes = _nodes(a=rs.SUCCEEDED, b=rs.PENDING)

    _write_req(tmp_path, "REQ-F-001", "draft")
    assert orchestrator.node_readiness("b", p, nodes, tmp_path, contracts) == rs.BLOCKED

    _write_req(tmp_path, "REQ-F-001", "approved")
    assert orchestrator.node_readiness("b", p, nodes, tmp_path, contracts) == orchestrator.READY


def test_manual_gate_awaits_approval(tmp_path, contracts):
    p = _pipe([{"from": "a", "to": "b", "gate": {"type": "manual"}}])
    nodes = _nodes(a=rs.SUCCEEDED, b=rs.PENDING)

    assert orchestrator.node_readiness("b", p, nodes, tmp_path, contracts) == rs.AWAITING_APPROVAL


def test_manual_gate_ready_once_approved(tmp_path, contracts):
    p = _pipe([{"from": "a", "to": "b", "gate": {"type": "manual"}}])
    nodes = _nodes(a=rs.SUCCEEDED, b=rs.PENDING)
    nodes["b"]["manual_approved"] = 1

    assert orchestrator.node_readiness("b", p, nodes, tmp_path, contracts) == orchestrator.READY


def test_combined_gate_reports_blocked_before_approval_when_artefacts_fail(tmp_path, contracts):
    """Blocked outranks awaiting-approval: there is nothing to approve yet."""
    p = _pipe([{
        "from": "a", "to": "b",
        "gate": {"type": "artifact+manual", "artefact": "requirement",
                 "quantifier": "all", "require": {"status": "approved"}},
    }])
    nodes = _nodes(a=rs.SUCCEEDED, b=rs.PENDING)
    _write_req(tmp_path, "REQ-F-001", "draft")

    assert orchestrator.node_readiness("b", p, nodes, tmp_path, contracts) == rs.BLOCKED


def test_combined_gate_awaits_approval_once_artefacts_hold(tmp_path, contracts):
    p = _pipe([{
        "from": "a", "to": "b",
        "gate": {"type": "artifact+manual", "artefact": "requirement",
                 "quantifier": "all", "require": {"status": "approved"}},
    }])
    nodes = _nodes(a=rs.SUCCEEDED, b=rs.PENDING)
    _write_req(tmp_path, "REQ-F-001", "approved")

    assert orchestrator.node_readiness("b", p, nodes, tmp_path, contracts) == rs.AWAITING_APPROVAL

    nodes["b"]["manual_approved"] = 1
    assert orchestrator.node_readiness("b", p, nodes, tmp_path, contracts) == orchestrator.READY


def test_node_with_two_upstreams_waits_for_both(tmp_path, contracts):
    p = pipeline.pipeline_from_dict({
        "version": 1,
        "nodes": [{"id": "a", "step": "doc-ingest"},
                  {"id": "b", "step": "arch-gen"},
                  {"id": "c", "step": "arch-gen"}],
        "edges": [{"from": "a", "to": "c"}, {"from": "b", "to": "c"}],
    })
    nodes = _nodes(a=rs.SUCCEEDED, b=rs.RUNNING, c=rs.PENDING)

    assert orchestrator.node_readiness("c", p, nodes, tmp_path, contracts) == rs.PENDING

    nodes["b"]["status"] = rs.SUCCEEDED
    assert orchestrator.node_readiness("c", p, nodes, tmp_path, contracts) == orchestrator.READY


def test_ready_sentinel_is_not_a_node_status(tmp_path, contracts):
    """READY is a scheduling answer, never something written to the store."""
    assert orchestrator.READY not in rs.NODE_STATUSES
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd studio/backend && python -m pytest tests/test_orchestrator_scheduling.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'implr_studio.orchestrator'`

- [ ] **Step 3: Write the scheduling half of `orchestrator.py`**

Create `studio/backend/implr_studio/orchestrator.py`:

```python
"""Pipeline execution: eligibility, gate opening, the driver loop, operator actions.

Gate decisions read the filesystem via `gates`. An `artifact` StepEvent is
advisory and never influences scheduling.
"""
from dataclasses import dataclass
from pathlib import Path

from . import gates
from . import runstate as rs
from .pipeline import Edge, Pipeline

# A scheduling answer, deliberately not a member of runstate.NODE_STATUSES:
# it describes what the scheduler should do, not a state ever persisted.
READY = "ready"


@dataclass(frozen=True)
class GateState:
    open: bool
    needs_approval: bool


def edge_gate_state(edge: Edge, node_row: dict, workspace: Path, contracts) -> GateState:
    """Evaluate one inbound edge for the node it points at."""
    gate = edge.gate
    approved = bool(node_row.get("manual_approved", 0))

    if gate.type == "none":
        return GateState(open=True, needs_approval=False)

    if gate.type == "manual":
        return GateState(open=approved, needs_approval=not approved)

    artefacts_hold = gates.artefact_condition_holds(gate, workspace, contracts)

    if gate.type == "artifact":
        return GateState(open=artefacts_hold, needs_approval=False)

    # artifact+manual
    if not artefacts_hold:
        return GateState(open=False, needs_approval=False)
    return GateState(open=approved, needs_approval=not approved)


def node_readiness(
    node_id: str, p: Pipeline, nodes: dict[str, dict], workspace: Path, contracts
) -> str:
    """Return READY, or the node status that explains why it cannot run yet."""
    inbound = [e for e in p.edges if e.target == node_id]
    if not inbound:
        return READY

    for edge in inbound:
        upstream = nodes.get(edge.source, {})
        if not rs.satisfies_dependency(upstream.get("status", rs.PENDING)):
            return rs.PENDING

    node_row = nodes.get(node_id, {})
    states = [edge_gate_state(e, node_row, workspace, contracts) for e in inbound]

    # Blocked outranks awaiting-approval: if the artefacts do not hold there is
    # nothing meaningful for the operator to approve yet.
    if any(not s.open and not s.needs_approval for s in states):
        return rs.BLOCKED
    if any(s.needs_approval for s in states):
        return rs.AWAITING_APPROVAL
    return READY
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd studio/backend && python -m pytest tests/test_orchestrator_scheduling.py -v`
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add studio/backend/implr_studio/orchestrator.py studio/backend/tests/test_orchestrator_scheduling.py
git commit -m "feat(studio): node eligibility and gate opening"
```

---

### Task 4: The driver loop — executing a run

**Files:**
- Modify: `studio/backend/implr_studio/orchestrator.py` (append the `Orchestrator` class)
- Test: `studio/backend/tests/test_orchestrator_execution.py`

**Interfaces:**
- Consumes: everything from Task 3; `StepExecutor`, `StepRequest`, `StepEvent`, `OUTCOME_SUCCESS` from Plan 2; `Registry` from Plan 1.
- Produces:
  - `Orchestrator(workspace: Path, registry, contracts, executor, store, concurrency: int = 1)`
  - `await Orchestrator.start_run(p: Pipeline, run_id: str | None = None) -> str` — persists the run and starts the driver in the background.
  - `await Orchestrator.wait_quiescent(run_id: str) -> None` — returns when no node is `running`. Tests use this instead of sleeping.
  - `await Orchestrator.answer(run_id: str, question_id: str, text: str) -> None`
  - `Orchestrator.run_status(run_id) -> str`, `Orchestrator.node_statuses(run_id) -> dict[str, str]`
  - `Orchestrator.UnavailableStepError` — raised at run start if a node references a registered-but-unimplemented step.

Driver contract: the loop repeatedly picks the first `READY` node (in pipeline node order), runs it to a terminal state, and repeats. It exits when nothing is `READY`, then writes the final run status: `succeeded` if every node is `succeeded`/`skipped`; `paused` if any node is `failed`, `blocked`, or `awaiting-approval`; `failed` only when the run is explicitly abandoned.

- [ ] **Step 1: Write the failing test**

Create `studio/backend/tests/test_orchestrator_execution.py`:

```python
import json
from pathlib import Path

import pytest

from implr_studio import implr_bridge, orchestrator, pipeline, registry
from implr_studio import runstate as rs
from implr_studio.executors import base
from implr_studio.executors.fake import FakeExecutor
from implr_studio.store import Store

pytestmark = pytest.mark.asyncio


@pytest.fixture
def contracts():
    root = implr_bridge.repo_root()
    return implr_bridge.load_contracts(str(implr_bridge.resolve_schema_dir(root)))


@pytest.fixture
def reg(tmp_path: Path) -> registry.Registry:
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    schema_dir.mkdir(parents=True)
    steps = [
        {"id": s, "label": s, "phase": "discovery", "skill": s,
         "args_allowed": ["--all"], "args_default": [],
         "interactive": False, "produces": [], "description": ""}
        for s in ("doc-ingest", "arch-gen", "missing-skill")
    ]
    (schema_dir / "step-registry.json").write_text(json.dumps({"steps": steps}), encoding="utf-8")
    for skill in ("doc-ingest", "arch-gen"):        # missing-skill intentionally absent
        (skills_dir / skill).mkdir(parents=True)
        (skills_dir / skill / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
    return registry.load_registry(schema_dir, skills_dir)


@pytest.fixture
def store(tmp_path: Path) -> Store:
    s = Store(tmp_path / "runs.db")
    yield s
    s.close()


def _orch(tmp_path, reg, contracts, store, executor) -> orchestrator.Orchestrator:
    workspace = tmp_path / "ws"
    workspace.mkdir(exist_ok=True)
    return orchestrator.Orchestrator(workspace, reg, contracts, executor, store)


def _two_step_pipeline(gate=None) -> pipeline.Pipeline:
    edge = {"from": "a", "to": "b"}
    if gate is not None:
        edge["gate"] = gate
    return pipeline.pipeline_from_dict({
        "version": 1,
        "nodes": [{"id": "a", "step": "doc-ingest"}, {"id": "b", "step": "arch-gen"}],
        "edges": [edge],
    })


async def test_runs_both_nodes_in_dependency_order(tmp_path, reg, contracts, store):
    ex = FakeExecutor(default=[base.StepEvent.done(base.OUTCOME_SUCCESS, "ok")])
    orch = _orch(tmp_path, reg, contracts, store, ex)

    run_id = await orch.start_run(_two_step_pipeline())
    await orch.wait_quiescent(run_id)

    assert [r.skill for r in ex.started] == ["doc-ingest", "arch-gen"]
    assert orch.node_statuses(run_id) == {"a": rs.SUCCEEDED, "b": rs.SUCCEEDED}
    assert orch.run_status(run_id) == rs.RUN_SUCCEEDED


async def test_node_args_reach_the_executor(tmp_path, reg, contracts, store):
    ex = FakeExecutor(default=[base.StepEvent.done(base.OUTCOME_SUCCESS, "ok")])
    orch = _orch(tmp_path, reg, contracts, store, ex)
    p = pipeline.pipeline_from_dict({
        "version": 1,
        "nodes": [{"id": "a", "step": "doc-ingest", "args": ["--all"]}],
        "edges": [],
    })

    run_id = await orch.start_run(p)
    await orch.wait_quiescent(run_id)

    assert ex.started[0].args == ("--all",)
    assert ex.started[0].workspace == tmp_path / "ws"


async def test_log_events_are_persisted_with_a_cursor(tmp_path, reg, contracts, store):
    ex = FakeExecutor(default=[
        base.StepEvent.log("line one"),
        base.StepEvent.log("line two"),
        base.StepEvent.done(base.OUTCOME_SUCCESS, "ok"),
    ])
    orch = _orch(tmp_path, reg, contracts, store, ex)

    run_id = await orch.start_run(_two_step_pipeline())
    await orch.wait_quiescent(run_id)

    logs = [e for e in store.events_since(run_id, 0) if e["kind"] == "log"]
    assert [e["payload"]["text"] for e in logs][:2] == ["line one", "line two"]
    assert logs[0]["seq"] < logs[1]["seq"]


async def test_failing_node_pauses_the_run_and_leaves_downstream_pending(tmp_path, reg, contracts, store):
    ex = FakeExecutor({"doc-ingest": [base.StepEvent.done(base.OUTCOME_FAILURE, "broke", error="exit 1")]})
    orch = _orch(tmp_path, reg, contracts, store, ex)

    run_id = await orch.start_run(_two_step_pipeline())
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id) == {"a": rs.FAILED, "b": rs.PENDING}
    assert orch.run_status(run_id) == rs.RUN_PAUSED
    assert store.get_node(run_id, "a")["error"] == "exit 1"
    assert [r.skill for r in ex.started] == ["doc-ingest"]      # b never started


async def test_question_pauses_the_node_and_is_persisted(tmp_path, reg, contracts, store):
    ex = FakeExecutor({"doc-ingest": [
        base.StepEvent.question("q1", "Postgres or MySQL?"),
        base.StepEvent.done(base.OUTCOME_SUCCESS, "ok"),
    ]})
    orch = _orch(tmp_path, reg, contracts, store, ex)

    run_id = await orch.start_run(_two_step_pipeline())
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id)["a"] == rs.AWAITING_INPUT
    pending = store.pending_question(run_id, "a")
    assert pending["prompt_md"] == "Postgres or MySQL?"


async def test_answering_resumes_the_node_and_the_run(tmp_path, reg, contracts, store):
    ex = FakeExecutor({"doc-ingest": [
        base.StepEvent.question("q1", "Which one?"),
        base.StepEvent.log("thanks"),
        base.StepEvent.done(base.OUTCOME_SUCCESS, "ok"),
    ]})
    orch = _orch(tmp_path, reg, contracts, store, ex)
    run_id = await orch.start_run(_two_step_pipeline())
    await orch.wait_quiescent(run_id)

    question_id = store.pending_question(run_id, "a")["id"]
    await orch.answer(run_id, question_id, "Postgres")
    await orch.wait_quiescent(run_id)

    assert ex.answers == [("q1", "Postgres")]
    assert orch.node_statuses(run_id) == {"a": rs.SUCCEEDED, "b": rs.SUCCEEDED}
    assert store.get_question(question_id)["answer"] == "Postgres"


async def test_artifact_gate_holds_the_run_paused(tmp_path, reg, contracts, store):
    ex = FakeExecutor(default=[base.StepEvent.done(base.OUTCOME_SUCCESS, "ok")])
    orch = _orch(tmp_path, reg, contracts, store, ex)
    gate = {"type": "artifact", "artefact": "requirement",
            "quantifier": "all", "require": {"status": "approved"}}

    run_id = await orch.start_run(_two_step_pipeline(gate))
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id) == {"a": rs.SUCCEEDED, "b": rs.BLOCKED}
    assert orch.run_status(run_id) == rs.RUN_PAUSED
    assert [r.skill for r in ex.started] == ["doc-ingest"]


async def test_unavailable_step_is_rejected_at_run_start(tmp_path, reg, contracts, store):
    """Designing ahead is fine; executing a skill that does not exist is not."""
    ex = FakeExecutor()
    orch = _orch(tmp_path, reg, contracts, store, ex)
    p = pipeline.pipeline_from_dict({
        "version": 1,
        "nodes": [{"id": "a", "step": "missing-skill"}],
        "edges": [],
    })

    with pytest.raises(orchestrator.UnavailableStepError, match="missing-skill"):
        await orch.start_run(p)

    assert ex.started == []


async def test_parallel_branches_run_one_at_a_time(tmp_path, reg, contracts, store):
    """Phase 1 caps concurrency at 1: the graph may branch, execution does not."""
    ex = FakeExecutor(default=[base.StepEvent.done(base.OUTCOME_SUCCESS, "ok")])
    orch = _orch(tmp_path, reg, contracts, store, ex)
    p = pipeline.pipeline_from_dict({
        "version": 1,
        "nodes": [{"id": "root", "step": "doc-ingest"},
                  {"id": "left", "step": "arch-gen"},
                  {"id": "right", "step": "arch-gen"}],
        "edges": [{"from": "root", "to": "left"}, {"from": "root", "to": "right"}],
    })

    run_id = await orch.start_run(p)
    await orch.wait_quiescent(run_id)

    assert len(ex.started) == 3
    assert orch.run_status(run_id) == rs.RUN_SUCCEEDED
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd studio/backend && python -m pytest tests/test_orchestrator_execution.py -v`
Expected: FAIL — `AttributeError: module 'implr_studio.orchestrator' has no attribute 'Orchestrator'`

- [ ] **Step 3: Append the `Orchestrator` class to `orchestrator.py`**

Add these imports to the top of `studio/backend/implr_studio/orchestrator.py`:

```python
import asyncio
import uuid

from .executors.base import OUTCOME_SUCCESS, StepEvent, StepRequest
```

Then append:

```python
class UnavailableStepError(Exception):
    """A node references a registered step whose skill is not implemented."""


class Orchestrator:
    """Drives one pipeline run at a time per run_id, serially (concurrency cap 1)."""

    def __init__(self, workspace, registry, contracts, executor, store, concurrency: int = 1) -> None:
        self.workspace = Path(workspace)
        self.registry = registry
        self.contracts = contracts
        self.executor = executor
        self.store = store
        self.concurrency = concurrency
        self._drivers: dict[str, asyncio.Task] = {}

    # --- public API ---

    async def start_run(self, p: Pipeline, run_id: str | None = None) -> str:
        for node in p.nodes:
            step = self.registry.get(node.step)
            if step is None:
                raise UnavailableStepError("node %s: unknown step %r" % (node.id, node.step))
            if not step.available:
                raise UnavailableStepError(
                    "node %s: step %r is registered but its skill is not implemented"
                    % (node.id, node.step)
                )

        run_id = run_id or ("run-%s" % uuid.uuid4().hex[:12])
        self.store.create_run(run_id, p, [n.id for n in p.nodes])
        self._spawn_driver(run_id)
        return run_id

    async def wait_quiescent(self, run_id: str) -> None:
        """Return once the driver has stopped, i.e. no node is running."""
        task = self._drivers.get(run_id)
        while task is not None and not task.done():
            await task
            task = self._drivers.get(run_id)

    async def answer(self, run_id: str, question_id: str, text: str) -> None:
        question = self.store.get_question(question_id)
        if question is None or question["run_id"] != run_id:
            raise KeyError("unknown question: %s" % question_id)
        self.store.answer_question(question_id, text)
        handle = self._handles.get((run_id, question["node_id"]))
        if handle is not None:
            await self.executor.answer(handle, question_id, text)

    def run_status(self, run_id: str) -> str:
        run = self.store.get_run(run_id)
        return run["status"] if run else ""

    def node_statuses(self, run_id: str) -> dict[str, str]:
        return {k: v["status"] for k, v in self.store.get_nodes(run_id).items()}

    # --- driver ---

    _handles: dict = {}

    def _spawn_driver(self, run_id: str) -> None:
        existing = self._drivers.get(run_id)
        if existing is not None and not existing.done():
            return
        self._drivers[run_id] = asyncio.create_task(self._drive(run_id))

    async def _drive(self, run_id: str) -> None:
        try:
            while True:
                node_id = self._next_ready(run_id)
                if node_id is None:
                    break
                await self._run_node(run_id, node_id)
        finally:
            self._refresh_blocked_states(run_id)
            self._finalise_run_status(run_id)

    def _next_ready(self, run_id: str) -> str | None:
        run = self.store.get_run(run_id)
        if run is None or run["status"] == rs.RUN_CANCELLED:
            return None
        p, nodes = run["pipeline"], self.store.get_nodes(run_id)
        for node in p.nodes:
            row = nodes.get(node.id, {})
            if rs.is_terminal(row.get("status", rs.PENDING)):
                continue
            if row.get("status") == rs.AWAITING_INPUT:
                continue
            if node_readiness(node.id, p, nodes, self.workspace, self.contracts) == READY:
                return node.id
        return None

    async def _run_node(self, run_id: str, node_id: str) -> None:
        run = self.store.get_run(run_id)
        node = next(n for n in run["pipeline"].nodes if n.id == node_id)

        self.store.set_node_status(run_id, node_id, rs.RUNNING)
        self.store.append_event(run_id, node_id, "status", {"status": rs.RUNNING})

        request = StepRequest(
            node_id=node_id,
            skill=self.registry.get(node.step).skill,
            args=tuple(node.args),
            workspace=self.workspace,
        )
        handle = await self.executor.start(request)
        self._handles[(run_id, node_id)] = handle

        async for event in self.executor.events(handle):
            self.store.append_event(run_id, node_id, event.kind, dict(event.payload))

            if event.kind == "question":
                self.store.create_question(
                    event.question_id, run_id, node_id, event.prompt_md, event.options
                )
                self.store.set_node_status(run_id, node_id, rs.AWAITING_INPUT)
                self.store.append_event(run_id, node_id, "status", {"status": rs.AWAITING_INPUT})
                return          # the driver stops; answer() restarts it

            if event.is_terminal:
                status = rs.SUCCEEDED if event.outcome == OUTCOME_SUCCESS else rs.FAILED
                self.store.set_node_status(
                    run_id, node_id, status, summary=event.summary, error=event.error
                )
                self.store.append_event(run_id, node_id, "status", {"status": status})
                self._handles.pop((run_id, node_id), None)
                return

    def _refresh_blocked_states(self, run_id: str) -> None:
        """Record why each not-yet-run node cannot proceed, for the UI."""
        run = self.store.get_run(run_id)
        if run is None:
            return
        p, nodes = run["pipeline"], self.store.get_nodes(run_id)
        for node in p.nodes:
            row = nodes.get(node.id, {})
            status = row.get("status", rs.PENDING)
            if status in (rs.PENDING, rs.BLOCKED, rs.AWAITING_APPROVAL):
                readiness = node_readiness(node.id, p, nodes, self.workspace, self.contracts)
                new_status = rs.PENDING if readiness == READY else readiness
                if new_status != status:
                    self.store.set_node_status(run_id, node.id, new_status)

    def _finalise_run_status(self, run_id: str) -> None:
        run = self.store.get_run(run_id)
        if run is None or run["status"] == rs.RUN_CANCELLED:
            return
        statuses = set(self.node_statuses(run_id).values())
        if statuses and statuses <= rs.NODE_SATISFIES_DEPENDENCY:
            self.store.set_run_status(run_id, rs.RUN_SUCCEEDED)
        else:
            self.store.set_run_status(run_id, rs.RUN_PAUSED)
```

Note on `answer()`: after recording the answer it must resume the driver. Add this as the final two lines of `answer()`:

```python
        self.store.set_node_status(run_id, question["node_id"], rs.RUNNING)
        self._spawn_driver(run_id)
```

Wait — the node is mid-`events()` iteration inside a driver that already returned. Because `_run_node` returns on a question, the *previous* driver exited and its `events()` generator was abandoned. Resuming must therefore re-enter the executor's event stream. Implement `_run_node` so that it resumes an existing handle instead of starting a new step:

```python
    async def _run_node(self, run_id: str, node_id: str) -> None:
        handle = self._handles.get((run_id, node_id))
        if handle is None:
            ...   # the start path shown above
        else:
            self.store.set_node_status(run_id, node_id, rs.RUNNING)
        async for event in self._stream(run_id, node_id, handle):
            ...
```

To keep this simple and correct, hold **one live iterator per handle** in `self._streams[(run_id, node_id)]`, created once when the step starts, and resumed on later driver passes. Replace the `_run_node` body with:

```python
    async def _run_node(self, run_id: str, node_id: str) -> None:
        key = (run_id, node_id)
        stream = self._streams.get(key)

        if stream is None:
            run = self.store.get_run(run_id)
            node = next(n for n in run["pipeline"].nodes if n.id == node_id)
            request = StepRequest(
                node_id=node_id,
                skill=self.registry.get(node.step).skill,
                args=tuple(node.args),
                workspace=self.workspace,
            )
            handle = await self.executor.start(request)
            self._handles[key] = handle
            stream = self.executor.events(handle)
            self._streams[key] = stream

        self.store.set_node_status(run_id, node_id, rs.RUNNING)
        self.store.append_event(run_id, node_id, "status", {"status": rs.RUNNING})

        async for event in stream:
            self.store.append_event(run_id, node_id, event.kind, dict(event.payload))

            if event.kind == "question":
                self.store.create_question(
                    event.question_id, run_id, node_id, event.prompt_md, event.options
                )
                self.store.set_node_status(run_id, node_id, rs.AWAITING_INPUT)
                self.store.append_event(run_id, node_id, "status", {"status": rs.AWAITING_INPUT})
                return

            if event.is_terminal:
                status = rs.SUCCEEDED if event.outcome == OUTCOME_SUCCESS else rs.FAILED
                self.store.set_node_status(
                    run_id, node_id, status, summary=event.summary, error=event.error
                )
                self.store.append_event(run_id, node_id, "status", {"status": status})
                self._handles.pop(key, None)
                self._streams.pop(key, None)
                return
```

and declare both dicts as real instance attributes in `__init__` (not class attributes — a class-level dict is shared across every Orchestrator instance and will leak state between tests):

```python
        self._handles: dict[tuple[str, str], object] = {}
        self._streams: dict[tuple[str, str], object] = {}
```

Delete the `_handles: dict = {}` class attribute shown earlier.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd studio/backend && python -m pytest tests/test_orchestrator_execution.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add studio/backend/implr_studio/orchestrator.py studio/backend/tests/test_orchestrator_execution.py
git commit -m "feat(studio): pipeline driver loop with question handling"
```

---

### Task 5: Operator actions and restart recovery

**Files:**
- Modify: `studio/backend/implr_studio/orchestrator.py` (append operator actions and `recover`)
- Test: `studio/backend/tests/test_orchestrator_recovery.py`

**Interfaces:**
- Consumes: everything from Task 4.
- Produces:
  - `await Orchestrator.approve(run_id, node_id) -> None` — sets `manual_approved` and resumes the driver.
  - `await Orchestrator.retry(run_id, node_id) -> None` — resets a `failed` node to `pending`, clears its handle/stream, resumes.
  - `await Orchestrator.skip(run_id, node_id) -> None` — marks a `failed` or `blocked` node `skipped`, resumes.
  - `await Orchestrator.cancel(run_id) -> None` — cancels any live step, marks non-terminal nodes `cancelled`, run `cancelled`.
  - `Orchestrator.recover() -> list[str]` — called at service startup. Every node persisted as `running` or `awaiting-input` whose process did not survive is marked `failed`; returns the affected run ids.
  - `OperatorActionError` — raised when an action does not apply to the node's current status.

- [ ] **Step 1: Write the failing test**

Create `studio/backend/tests/test_orchestrator_recovery.py`:

```python
import json
from pathlib import Path

import pytest

from implr_studio import implr_bridge, orchestrator, pipeline, registry
from implr_studio import runstate as rs
from implr_studio.executors import base
from implr_studio.executors.fake import FakeExecutor
from implr_studio.store import Store

pytestmark = pytest.mark.asyncio


@pytest.fixture
def contracts():
    root = implr_bridge.repo_root()
    return implr_bridge.load_contracts(str(implr_bridge.resolve_schema_dir(root)))


@pytest.fixture
def reg(tmp_path: Path) -> registry.Registry:
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    schema_dir.mkdir(parents=True)
    steps = [
        {"id": s, "label": s, "phase": "discovery", "skill": s,
         "args_allowed": [], "args_default": [],
         "interactive": False, "produces": [], "description": ""}
        for s in ("doc-ingest", "arch-gen")
    ]
    (schema_dir / "step-registry.json").write_text(json.dumps({"steps": steps}), encoding="utf-8")
    for skill in ("doc-ingest", "arch-gen"):
        (skills_dir / skill).mkdir(parents=True)
        (skills_dir / skill / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
    return registry.load_registry(schema_dir, skills_dir)


def _orch(tmp_path, reg, contracts, store, executor):
    workspace = tmp_path / "ws"
    workspace.mkdir(exist_ok=True)
    return orchestrator.Orchestrator(workspace, reg, contracts, executor, store)


def _pipe(gate=None) -> pipeline.Pipeline:
    edge = {"from": "a", "to": "b"}
    if gate is not None:
        edge["gate"] = gate
    return pipeline.pipeline_from_dict({
        "version": 1,
        "nodes": [{"id": "a", "step": "doc-ingest"}, {"id": "b", "step": "arch-gen"}],
        "edges": [edge],
    })


async def test_approve_releases_a_manual_gate(tmp_path, reg, contracts):
    store = Store(tmp_path / "runs.db")
    ex = FakeExecutor(default=[base.StepEvent.done(base.OUTCOME_SUCCESS, "ok")])
    orch = _orch(tmp_path, reg, contracts, store, ex)
    run_id = await orch.start_run(_pipe({"type": "manual"}))
    await orch.wait_quiescent(run_id)
    assert orch.node_statuses(run_id)["b"] == rs.AWAITING_APPROVAL

    await orch.approve(run_id, "b")
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id)["b"] == rs.SUCCEEDED
    assert orch.run_status(run_id) == rs.RUN_SUCCEEDED
    store.close()


async def test_retry_reruns_a_failed_node(tmp_path, reg, contracts):
    store = Store(tmp_path / "runs.db")
    ex = FakeExecutor({"doc-ingest": [base.StepEvent.done(base.OUTCOME_FAILURE, "broke", error="e")]})
    orch = _orch(tmp_path, reg, contracts, store, ex)
    run_id = await orch.start_run(_pipe())
    await orch.wait_quiescent(run_id)
    assert orch.node_statuses(run_id)["a"] == rs.FAILED

    ex.set_script("doc-ingest", [base.StepEvent.done(base.OUTCOME_SUCCESS, "fixed")])
    await orch.retry(run_id, "a")
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id) == {"a": rs.SUCCEEDED, "b": rs.SUCCEEDED}
    assert len(ex.started) == 3          # a (failed), a (retry), b
    store.close()


async def test_skip_marks_node_skipped_and_releases_downstream(tmp_path, reg, contracts):
    store = Store(tmp_path / "runs.db")
    ex = FakeExecutor({"doc-ingest": [base.StepEvent.done(base.OUTCOME_FAILURE, "broke", error="e")]})
    orch = _orch(tmp_path, reg, contracts, store, ex)
    run_id = await orch.start_run(_pipe())
    await orch.wait_quiescent(run_id)

    await orch.skip(run_id, "a")
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id) == {"a": rs.SKIPPED, "b": rs.SUCCEEDED}
    store.close()


async def test_retry_rejects_a_node_that_did_not_fail(tmp_path, reg, contracts):
    store = Store(tmp_path / "runs.db")
    ex = FakeExecutor(default=[base.StepEvent.done(base.OUTCOME_SUCCESS, "ok")])
    orch = _orch(tmp_path, reg, contracts, store, ex)
    run_id = await orch.start_run(_pipe())
    await orch.wait_quiescent(run_id)

    with pytest.raises(orchestrator.OperatorActionError, match="succeeded"):
        await orch.retry(run_id, "a")
    store.close()


async def test_cancel_marks_remaining_nodes_cancelled(tmp_path, reg, contracts):
    store = Store(tmp_path / "runs.db")
    ex = FakeExecutor({"doc-ingest": [base.StepEvent.done(base.OUTCOME_FAILURE, "broke", error="e")]})
    orch = _orch(tmp_path, reg, contracts, store, ex)
    run_id = await orch.start_run(_pipe())
    await orch.wait_quiescent(run_id)

    await orch.cancel(run_id)

    assert orch.run_status(run_id) == rs.RUN_CANCELLED
    assert orch.node_statuses(run_id)["b"] == rs.CANCELLED
    store.close()


async def test_recover_marks_orphaned_running_nodes_failed(tmp_path, reg, contracts):
    """A node persisted as running did not survive the restart. Say so; do not retry it."""
    db = tmp_path / "runs.db"
    store1 = Store(db)
    p = _pipe()
    store1.create_run("r1", p, ["a", "b"])
    store1.set_node_status("r1", "a", rs.RUNNING)
    store1.close()

    store2 = Store(db)
    orch = _orch(tmp_path, reg, contracts, store2, FakeExecutor())

    affected = orch.recover()

    assert affected == ["r1"]
    assert orch.node_statuses("r1")["a"] == rs.FAILED
    assert "restart" in store2.get_node("r1", "a")["error"].lower()
    assert orch.run_status("r1") == rs.RUN_PAUSED
    store2.close()


async def test_recover_also_fails_awaiting_input_nodes(tmp_path, reg, contracts):
    """An awaiting-input node's session is gone too - its process did not survive."""
    db = tmp_path / "runs.db"
    store1 = Store(db)
    store1.create_run("r1", _pipe(), ["a", "b"])
    store1.set_node_status("r1", "a", rs.AWAITING_INPUT)
    store1.close()

    store2 = Store(db)
    orch = _orch(tmp_path, reg, contracts, store2, FakeExecutor())
    orch.recover()

    assert orch.node_statuses("r1")["a"] == rs.FAILED
    store2.close()


async def test_recover_leaves_completed_runs_alone(tmp_path, reg, contracts):
    db = tmp_path / "runs.db"
    store1 = Store(db)
    store1.create_run("r1", _pipe(), ["a", "b"])
    store1.set_node_status("r1", "a", rs.SUCCEEDED)
    store1.set_node_status("r1", "b", rs.SUCCEEDED)
    store1.set_run_status("r1", rs.RUN_SUCCEEDED)
    store1.close()

    store2 = Store(db)
    orch = _orch(tmp_path, reg, contracts, store2, FakeExecutor())

    assert orch.recover() == []
    assert orch.run_status("r1") == rs.RUN_SUCCEEDED
    store2.close()


async def test_recovered_run_can_be_retried_and_completed(tmp_path, reg, contracts):
    """The point of recovery: the operator resumes rather than starting over."""
    db = tmp_path / "runs.db"
    store1 = Store(db)
    store1.create_run("r1", _pipe(), ["a", "b"])
    store1.set_node_status("r1", "a", rs.RUNNING)
    store1.close()

    store2 = Store(db)
    ex = FakeExecutor(default=[base.StepEvent.done(base.OUTCOME_SUCCESS, "ok")])
    orch = _orch(tmp_path, reg, contracts, store2, ex)
    orch.recover()

    await orch.retry("r1", "a")
    await orch.wait_quiescent("r1")

    assert orch.node_statuses("r1") == {"a": rs.SUCCEEDED, "b": rs.SUCCEEDED}
    assert orch.run_status("r1") == rs.RUN_SUCCEEDED
    store2.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd studio/backend && python -m pytest tests/test_orchestrator_recovery.py -v`
Expected: FAIL — `AttributeError: 'Orchestrator' object has no attribute 'approve'`

- [ ] **Step 3: Append operator actions to `orchestrator.py`**

Add near `UnavailableStepError`:

```python
class OperatorActionError(Exception):
    """The requested action does not apply to the node's current status."""
```

Append these methods to `Orchestrator`:

```python
    async def approve(self, run_id: str, node_id: str) -> None:
        node = self.store.get_node(run_id, node_id)
        if node is None:
            raise KeyError("unknown node: %s" % node_id)
        if node["status"] != rs.AWAITING_APPROVAL:
            raise OperatorActionError(
                "node %s is %s, not awaiting approval" % (node_id, node["status"])
            )
        self.store.set_manual_approved(run_id, node_id)
        self.store.append_event(run_id, node_id, "status", {"status": "approved"})
        self.store.set_run_status(run_id, rs.RUN_RUNNING)
        self._spawn_driver(run_id)

    async def retry(self, run_id: str, node_id: str) -> None:
        node = self.store.get_node(run_id, node_id)
        if node is None:
            raise KeyError("unknown node: %s" % node_id)
        if node["status"] != rs.FAILED:
            raise OperatorActionError(
                "node %s is %s, only a failed node can be retried" % (node_id, node["status"])
            )
        key = (run_id, node_id)
        self._handles.pop(key, None)
        self._streams.pop(key, None)
        self.store.set_node_status(run_id, node_id, rs.PENDING)
        self.store.set_run_status(run_id, rs.RUN_RUNNING)
        self._spawn_driver(run_id)

    async def skip(self, run_id: str, node_id: str) -> None:
        node = self.store.get_node(run_id, node_id)
        if node is None:
            raise KeyError("unknown node: %s" % node_id)
        if node["status"] not in (rs.FAILED, rs.BLOCKED, rs.AWAITING_APPROVAL, rs.PENDING):
            raise OperatorActionError(
                "node %s is %s and cannot be skipped" % (node_id, node["status"])
            )
        key = (run_id, node_id)
        self._handles.pop(key, None)
        self._streams.pop(key, None)
        self.store.set_node_status(run_id, node_id, rs.SKIPPED, summary="skipped by operator")
        self.store.append_event(run_id, node_id, "status", {"status": rs.SKIPPED})
        self.store.set_run_status(run_id, rs.RUN_RUNNING)
        self._spawn_driver(run_id)

    async def cancel(self, run_id: str) -> None:
        for (rid, node_id), handle in list(self._handles.items()):
            if rid == run_id:
                await self.executor.cancel(handle)
                self._handles.pop((rid, node_id), None)
                self._streams.pop((rid, node_id), None)
        for node_id, row in self.store.get_nodes(run_id).items():
            if not rs.is_terminal(row["status"]):
                self.store.set_node_status(run_id, node_id, rs.CANCELLED)
        self.store.set_run_status(run_id, rs.RUN_CANCELLED)
        self.store.append_event(run_id, None, "status", {"status": rs.RUN_CANCELLED})

    def recover(self) -> list[str]:
        """Reconcile persisted state with reality after a service restart.

        A node persisted as running or awaiting-input had a live child process
        that did not survive. Report it as failed - never resume it silently and
        never claim it is still running.
        """
        affected: list[str] = []
        for run in self.store.list_runs():
            if run["status"] in rs.RUN_TERMINAL:
                continue
            touched = False
            for node_id, row in self.store.get_nodes(run["id"]).items():
                if row["status"] in (rs.RUNNING, rs.AWAITING_INPUT):
                    self.store.set_node_status(
                        run["id"], node_id, rs.FAILED,
                        summary="interrupted by service restart",
                        error="the executing process did not survive a service restart",
                    )
                    touched = True
            if touched:
                self.store.set_run_status(run["id"], rs.RUN_PAUSED)
                affected.append(run["id"])
        return affected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd studio/backend && python -m pytest tests/test_orchestrator_recovery.py -v`
Expected: 9 passed

- [ ] **Step 5: Run the whole suite**

Run: `cd studio/backend && python -m pytest -v`
Expected: all Plan 1 + Plan 2 + Plan 3 tests pass

- [ ] **Step 6: Commit**

```bash
git add studio/backend/implr_studio/orchestrator.py studio/backend/tests/test_orchestrator_recovery.py
git commit -m "feat(studio): operator actions and restart recovery"
```

---

## Definition of Done

- [ ] `python -m pytest` in `studio/backend/` passes every test from Plans 1-3.
- [ ] No test in this plan invokes an LLM — all execution goes through `FakeExecutor`.
- [ ] A failing node pauses the run and leaves downstream nodes `pending`, never `failed`.
- [ ] A node interrupted by a restart is reported `failed` with an error naming the restart — not resumed, not retried silently.
- [ ] A run whose gate is unsatisfied stays `paused` and starts no downstream step.
- [ ] `READY` is never written to the store.
- [ ] `_handles` and `_streams` are instance attributes, so two `Orchestrator` objects share no state.
