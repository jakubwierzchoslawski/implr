# implr Studio — Phase 5: Pick models

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drop `task-executor` to Sonnet and watch the node's tier dots, the pipeline's model-mix meter and the YAML all change — then set it back and watch the override *disappear* rather than pin.

**Roadmap:** `2026-08-25-studio-phases.md` · **Spec:** `../specs/2026-08-25-implr-studio-design.md` (*Why model tier is per agent*) · **Runtime:** `../../RUNTIME.md`

**Depends on:** Phase 4 — the Agents tab reuses `Modal.tsx`.

---

## Demo

Click **Implementation** → **Agents**. Three cards, in dispatch order:

```
● arch-excerpter    1 per plan            sonnet        Read Grep Glob
● plan-runner       1 per plan, cap 5     opus          Read Write Edit Bash Agent
● task-executor     1 per task            opus          Read Write Edit Bash Grep Glob
```

The tiers are read from the project's `implr.config.yaml`, not invented. Write-capable tools
are tinted.

1. Drop `task-executor` to **sonnet**. It marks *overridden*, the node's dots change, the
   right rail's mix meter shifts, and the modal footer gains `implr.config.yaml`.
2. **Save.** The YAML gains `models: {task-executor: sonnet}`.
3. Set it back to **opus** — the project default. The override **clears**: `models` disappears
   from the YAML entirely.

That last step is the one worth watching. Selecting the project default must not pin it, or a
project that later raises its default silently leaves this node behind.

---

## Why tier is per agent and not per step

`docs/implr/config/implr.config.yaml` already ships an `agents:` block mapping each of the
eleven implr subagents to `haiku | sonnet | opus`. That block is where this decision already
lives.

So the configurator edits **it**, and the registry's `agents` array exists only to tell the UI
which of those keys are relevant to a given step. A per-step `model` field would be a second
source of truth for the same decision — the mistake `status-vocabulary.json`'s own header
forbids for statuses, applied to models.

**The Agents tab is read-only apart from the tier**, and says so. For a `kind: "skill"` step,
which agents run is decided by the SKILL.md's prose: the studio sends `/dev-executor` and the
skill dispatches what it dispatches. Only the tier maps onto a real `ClaudeAgentOptions`
field. A pane that looked editable and silently discarded the edit would be worse than one
that admits the boundary. Phase 8's `kind: "agent"` steps make the whole card editable.

---

## Scope boundary — not in this phase

- **No editing which agents a step dispatches.** Architecturally impossible for a skill-backed
  step; Phase 8 for agent-backed ones.
- **No cost estimate in currency.** The meter counts agents by tier. Turning that into money
  needs per-tier pricing and a token forecast, and a wrong number is worse than none.
- **No run-wide tier override.** There is no "run everything on Sonnet" switch; the meter
  exists so you can see the aggregate and go change the nodes that matter.
- **No Input/Output tabs.** Phase 7.

---

## Global constraints

- Nothing hardcodes an agent name or a tier. Both arrive from `GET /api/projects/{pid}/registry`.
- A `models` entry naming an agent the step does not dispatch is a save-time error, not a
  silently-ignored key.
- Selecting the project default **clears** the override rather than writing it.
- `--tier-*` are already reserved tokens. No new colour.

---

## File Structure

| File | Responsibility |
|---|---|
| `packages/implr_studio/pipeline.py` | **Modified** — `Node.models`, two findings. |
| `packages/implr_studio/serialize.py` | **Modified** — `agent_defaults`, `agent_tools`. |
| `packages/implr_studio/api.py` | **Modified** — registry response grows two keys. |
| `web/src/models.ts` | **Pure** tier resolution and aggregation. No React. |
| `web/src/modal/StepConfig.tsx` | **Modified** — the Agents pane. |
| `web/src/nodes/StepNode.tsx` | **Modified** — the tier-dot row. |
| `web/src/panels/HealthPanel.tsx` | **Modified** — the mix meter. |

---

### Task 1: `models` on the node

**Files:**
- Modify: `packages/implr_studio/pipeline.py`
- Test: `packages/implr_studio/tests/test_models_config.py`

**Interfaces:**
- `Node.models: dict = {}` — agent name → tier. Sparse; omitted when empty.
- `validate_pipeline` gains `unknown-agent`, `illegal-tier`.

- [ ] **Step 1: Write the failing test**

```python
def test_models_defaults_to_empty():
    """Absent means inherit. Every pre-Phase-5 pipeline keeps behaving identically."""
    assert _p({"id": "a", "step": "dev-executor"}).nodes[0].models == {}


def test_an_override_for_a_dispatched_agent_is_accepted(reg):
    assert pipeline.validate_pipeline(
        _p({"id": "a", "step": "dev-executor",
            "models": {"task-executor": "haiku"}}), reg) == []


def test_an_override_for_an_agent_the_step_does_not_dispatch_is_rejected(reg):
    """Otherwise the UI can write a key that configures nothing, forever."""
    findings = pipeline.validate_pipeline(
        _p({"id": "a", "step": "dev-executor",
            "models": {"cr-applier": "haiku"}}), reg)

    assert [f.code for f in findings] == ["unknown-agent"]
    assert "cr-applier" in findings[0].message
    assert "task-executor" in findings[0].message      # names what IS dispatched


def test_an_illegal_tier_is_rejected(reg):
    findings = pipeline.validate_pipeline(
        _p({"id": "a", "step": "dev-executor",
            "models": {"task-executor": "gpt-4"}}), reg)

    assert [f.code for f in findings] == ["illegal-tier"]
    assert "haiku" in findings[0].message              # names the legal tiers


def test_a_step_that_dispatches_nothing_rejects_any_override(reg):
    findings = pipeline.validate_pipeline(
        _p({"id": "a", "step": "sec-review", "models": {"anything": "sonnet"}}), reg)

    assert [f.code for f in findings] == ["unknown-agent"]
    assert "none" in findings[0].message               # says it dispatches nothing


def test_models_is_omitted_from_the_yaml_when_empty():
    assert "models" not in pipeline.pipeline_to_dict(
        _p({"id": "a", "step": "dev-executor"}))["nodes"][0]


def test_models_survives_the_round_trip():
    p = _p({"id": "a", "step": "dev-executor", "models": {"task-executor": "sonnet"}})

    assert pipeline.pipeline_from_dict(pipeline.pipeline_to_dict(p)) == p
```

- [ ] **Step 2: Implement, run, commit**

```bash
git commit -m "feat(studio): per-agent model overrides on a node"
```

---

### Task 2: Serving the defaults and the tool grants

**Files:**
- Modify: `packages/implr_studio/serialize.py`, `api.py`
- Test: `packages/implr_studio/tests/test_agent_payload.py`

**Interfaces:**
- `serialize.agent_defaults(workspace) -> dict[str, str]` — reads the project's `implr.config.yaml` `agents:` block.
- `serialize.agent_tools(plugin_dir) -> dict[str, list[str]]` — reads `plugin/agents/*.md` frontmatter.
- `GET /api/projects/{pid}/registry` grows `agent_defaults` and `agent_tools`.

**Both read real files, and both must survive them being absent or malformed.** The shipped
`implr.config.yaml` has its `agents:` block **commented out** — that is not an error, it means
every agent runs on its own built-in default, and the UI must say *project default* rather
than invent a tier.

`agent_tools` reads `plugin/agents/` (post Phase −1; it was `.claude/agents/`). Parsed with
`implr_bridge.parse_frontmatter` — no second parser.

- [ ] **Step 1: Write the failing test**

```python
def test_agent_defaults_reads_the_agents_block(tmp_path):
    cfg = tmp_path / "docs" / "implr" / "config"
    cfg.mkdir(parents=True)
    (cfg / "implr.config.yaml").write_text(
        "agents:\n  task-executor: opus\n  plan-worker: sonnet\n", encoding="utf-8")

    assert serialize.agent_defaults(tmp_path) == {
        "task-executor": "opus", "plan-worker": "sonnet"}


def test_a_commented_out_block_yields_no_defaults(tmp_path):
    """The SHIPPED template has it commented out. That is normal: every agent runs
    on its built-in default and the UI must say so rather than invent a tier."""
    cfg = tmp_path / "docs" / "implr" / "config"
    cfg.mkdir(parents=True)
    (cfg / "implr.config.yaml").write_text(
        "# agents:\n#   task-executor: opus\n", encoding="utf-8")

    assert serialize.agent_defaults(tmp_path) == {}


def test_a_missing_config_file_yields_no_defaults(tmp_path):
    assert serialize.agent_defaults(tmp_path) == {}


def test_malformed_yaml_yields_no_defaults_rather_than_raising(tmp_path):
    """A broken config must not take the registry endpoint down."""
    cfg = tmp_path / "docs" / "implr" / "config"
    cfg.mkdir(parents=True)
    (cfg / "implr.config.yaml").write_text("agents: [unclosed\n", encoding="utf-8")

    assert serialize.agent_defaults(tmp_path) == {}


def test_an_illegal_tier_in_the_config_is_dropped(tmp_path):
    """A hand-edited config must not put a value in the UI that the save would refuse."""
    cfg = tmp_path / "docs" / "implr" / "config"
    cfg.mkdir(parents=True)
    (cfg / "implr.config.yaml").write_text(
        "agents:\n  task-executor: gpt-4\n  plan-worker: sonnet\n", encoding="utf-8")

    assert serialize.agent_defaults(tmp_path) == {"plan-worker": "sonnet"}


def test_agent_tools_reads_the_declared_grant(tmp_path):
    d = tmp_path / "agents"
    d.mkdir()
    (d / "plan-runner.md").write_text(
        "---\nname: plan-runner\ndescription: d\n"
        "tools: [Read, Write, Edit, Bash, Agent]\n---\nbody\n", encoding="utf-8")

    assert serialize.agent_tools(tmp_path) == {
        "plan-runner": ["Read", "Write", "Edit", "Bash", "Agent"]}


def test_an_agent_with_no_tools_line_is_omitted(tmp_path):
    d = tmp_path / "agents"
    d.mkdir()
    (d / "x.md").write_text("---\nname: x\n---\nbody\n", encoding="utf-8")

    assert serialize.agent_tools(tmp_path) == {}


def test_agent_tools_covers_every_real_agent():
    """All eleven, from the real plugin/agents tree."""
    from implr_studio import implr_bridge

    tools = serialize.agent_tools(implr_bridge.repo_root() / "plugin")

    assert len(tools) == 11
    assert "Agent" in tools["plan-runner"]
    assert "Bash" in tools["task-executor"]
    assert tools["arch-drafter"] == ["Read", "Write"]


def test_the_registry_response_carries_both(client):
    body = client.get(f"/api/projects/{PID}/registry").json()

    assert "agent_defaults" in body
    assert "agent_tools" in body
    assert len(body["agent_tools"]) == 11
    assert body["tiers"] == ["haiku", "sonnet", "opus"]
```

- [ ] **Step 2: Implement, run, commit**

---

### Task 3: `models.ts` — pure tier logic

**Files:**
- Create: `web/src/models.ts`
- Test: `web/src/models.test.ts`

**Interfaces:**
- `resolveTier(node, agent, defaults) -> Tier | null`
- `isOverridden(node, agent, defaults) -> boolean`
- `mixFor(nodes, steps, defaults) -> Record<Tier, number>`
- `worstTier(step, node, defaults) -> Tier | null`

Pure and React-free, because this is where the interesting rules live and they deserve tests
that do not render anything.

- [ ] **Step 1: Write the failing test**

```ts
describe('resolveTier', () => {
  it('falls back to the project default', () => {
    expect(models.resolveTier(node(), 'task-executor', DEFAULTS)).toBe('opus');
  });

  it('prefers a node override', () => {
    expect(models.resolveTier(node({ 'task-executor': 'sonnet' }), 'task-executor', DEFAULTS))
      .toBe('sonnet');
  });

  it('returns null when neither the node nor the project sets a tier', () => {
    // A commented-out agents: block is normal. The UI says "project default"
    // rather than inventing one.
    expect(models.resolveTier(node(), 'task-executor', {})).toBeNull();
  });

  it('ignores a garbage tier in the defaults', () => {
    expect(models.resolveTier(node(), 'task-executor', { 'task-executor': 'gpt-4' })).toBeNull();
  });
});

describe('isOverridden', () => {
  it('is false when the node matches the default', () => {
    expect(models.isOverridden(node({ 'task-executor': 'opus' }), 'task-executor', DEFAULTS))
      .toBe(false);
  });

  it('is true when the node differs', () => {
    expect(models.isOverridden(node({ 'task-executor': 'haiku' }), 'task-executor', DEFAULTS))
      .toBe(true);
  });

  it('is true when the node sets a tier and the project sets none', () => {
    expect(models.isOverridden(node({ 'task-executor': 'haiku' }), 'task-executor', {}))
      .toBe(true);
  });
});

describe('mixFor', () => {
  it('counts every agent of every node by resolved tier', () => {
    expect(models.mixFor([node(), node()], { 'dev-executor': STEP }, DEFAULTS))
      .toEqual({ haiku: 0, sonnet: 2, opus: 4 });
  });

  it('reflects an override in the aggregate', () => {
    expect(models.mixFor([node({ 'task-executor': 'haiku' })], { 'dev-executor': STEP }, DEFAULTS))
      .toEqual({ haiku: 1, sonnet: 1, opus: 1 });
  });

  it('ignores a node whose step is not in the registry', () => {
    expect(models.mixFor([{ step: 'ghost', models: {} }], {}, DEFAULTS))
      .toEqual({ haiku: 0, sonnet: 0, opus: 0 });
  });

  it('ignores an agent with no resolvable tier', () => {
    expect(models.mixFor([node()], { 'dev-executor': STEP }, {}))
      .toEqual({ haiku: 0, sonnet: 0, opus: 0 });
  });
});

describe('worstTier', () => {
  it('reports the most expensive tier a step will use', () => {
    expect(models.worstTier(STEP, node(), DEFAULTS)).toBe('opus');
  });

  it('drops when every expensive agent is overridden downward', () => {
    expect(models.worstTier(STEP, node({ 'plan-runner': 'haiku', 'task-executor': 'haiku' }),
                            DEFAULTS)).toBe('sonnet');
  });

  it('is null for a step that dispatches nothing', () => {
    expect(models.worstTier({ ...STEP, agents: [] }, node(), DEFAULTS)).toBeNull();
  });
});
```

- [ ] **Step 2: Implement, run, commit**

---

### Task 4: The Agents pane, the tier dots, the meter

**Files:**
- Modify: `web/src/modal/StepConfig.tsx`, `web/src/nodes/StepNode.tsx`, `web/src/panels/HealthPanel.tsx`, `web/src/store.ts`, `web/src/api.ts`, `web/src/app.css`
- Test: `web/src/modal/StepConfig.test.tsx` (extend), `web/src/panels/HealthPanel.test.tsx` (extend)

**Interfaces:**
- `store.agentDefaults`, `store.agentTools`, `store.setNodeModel(nodeId, agent, tier | null)` — `null` clears.
- The Agents pane; the node's tier-dot row; the meter and the "most expensive" line.

- [ ] **Step 1: Write the failing tests**

```tsx
describe('StepConfig — Agents tab', () => {
  it('lists the agents the step dispatches, in dispatch order, with fan-out', async () => {
    open(); await goAgents();
    expect(screen.getAllByTestId(/^agent-/).map((n) => n.dataset.testid)).toEqual([
      'agent-arch-excerpter', 'agent-plan-runner', 'agent-task-executor']);
    expect(screen.getByText('1 per plan, cap 5')).toBeInTheDocument();
  });

  it('defaults each tier to the project default', async () => {
    open(); await goAgents();
    expect(within(card('task-executor')).getByRole('button', { name: /opus/i }))
      .toHaveAttribute('aria-pressed', 'true');
  });

  it('says "project default" when the config sets no tier', async () => {
    openWith({ agentDefaults: {} }); await goAgents();
    expect(screen.getByText(/project default/i)).toBeInTheDocument();
  });

  it('changing a tier records an override and marks it', async () => {
    open(); await goAgents();
    await userEvent.click(within(card('task-executor')).getByRole('button', { name: /sonnet/i }));

    expect(node('build').data.models).toEqual({ 'task-executor': 'sonnet' });
    expect(within(card('task-executor')).getByText(/overridden/i)).toBeInTheDocument();
  });

  it('selecting the project default CLEARS the override', async () => {
    // Not pins. Otherwise a project that later raises its default silently
    // leaves this node behind.
    open(); await goAgents();
    await userEvent.click(within(card('task-executor')).getByRole('button', { name: /sonnet/i }));

    await userEvent.click(within(card('task-executor')).getByRole('button', { name: /opus/i }));

    expect(node('build').data.models).toEqual({});
  });

  it('shows the declared tool grant', async () => {
    open(); await goAgents();
    expect(within(card('plan-runner')).getByText('Bash')).toBeInTheDocument();
  });

  it('marks tools that can change the repository', async () => {
    open(); await goAgents();
    expect(within(card('plan-runner')).getByTitle(/changes the repository/i)).toBeInTheDocument();
  });

  it('does not mark a read-only tool', async () => {
    open(); await goAgents();
    expect(within(card('arch-excerpter')).queryByTitle(/changes the repository/i)).toBeNull();
  });

  it('says the pane is read-only apart from the tier', async () => {
    // The honest boundary: which agents run is the SKILL.md's decision.
    open(); await goAgents();
    expect(screen.getByText(/the skill decides/i)).toBeInTheDocument();
  });

  it('says so for a step that dispatches nothing', async () => {
    open('sec'); await goAgents();
    expect(screen.getByText(/dispatches no subagents/i)).toBeInTheDocument();
  });

  it('adds implr.config.yaml to the footer once a tier is overridden', async () => {
    open(); await goAgents();
    expect(screen.getByTestId('writes').textContent).not.toContain('implr.config.yaml');

    await userEvent.click(within(card('task-executor')).getByRole('button', { name: /haiku/i }));

    expect(screen.getByTestId('writes').textContent).toContain('implr.config.yaml');
  });
});
```

```tsx
describe('HealthPanel — model mix', () => {
  it('counts every agent of every node', () => { ... });
  it('shifts when a tier is overridden', () => { ... });
  it('names the most expensive step', () => { ... });
  it('offers to configure the most expensive step', async () => { ... });
  it('renders nothing when no node resolves a tier', () => { ... });
});
```

```tsx
// StepNode
it('shows one tier dot per dispatched agent', () => { ... });
it('colours a dot by resolved tier', () => { ... });
it('greys a dot with no resolvable tier', () => { ... });
```

- [ ] **Step 2: Implement**

The clearing rule, which is the one line worth reading twice:

```tsx
                      onClick={() =>
                        // Selecting the project default clears the override rather
                        // than pinning it, so the node keeps inheriting.
                        setNodeModel(nodeId, agent.name,
                          defaults[agent.name] === tier ? null : (tier as Tier))
                      }
```

Read `agentTools` with a selector at the top of the pane, not `getState()` inside the map, so
the pane re-renders if the registry arrives late.

- [ ] **Step 3: Run, build, commit**

---

### Task 5: Run the demo

- [ ] **Step 1** — the three steps in *Demo*, in order, watching all four surfaces change
      together: the card badge, the node dots, the meter, the footer.
- [ ] **Step 2** — set it back to the project default and confirm `models` **disappears** from
      the YAML rather than being written as `opus`.
- [ ] **Step 3** — comment out the `agents:` block in the probe workspace's
      `implr.config.yaml`, reload. Every tier reads *project default*, no tier is pre-selected,
      and the meter is empty. Nothing invents a value.
- [ ] **Step 4** — hand-edit the YAML to `models: {cr-applier: sonnet}` on the Implementation
      node, reload, Save → `422`, `unknown-agent`, naming what the step actually dispatches.
- [ ] **Step 5** — confirm the read-only boundary is legible: the Agents pane says which
      agents run is the skill's decision, and offers no way to add or remove one.

---

## Definition of Done

- [ ] `python -m pytest` and `npm test` / `npm run build` pass.
- [ ] `models` is omitted from the YAML when empty — Phase 4 pipelines round-trip unchanged.
- [ ] An override naming an undispatched agent produces `unknown-agent` and the message names
      what the step *does* dispatch.
- [ ] An illegal tier produces `illegal-tier` and the message names the legal three.
- [ ] `agent_defaults` returns `{}` for a missing file, a commented-out block and malformed
      YAML — and drops an illegal tier rather than serving one the save would refuse.
- [ ] `agent_tools` covers all **eleven** real agents, parsed with `implr_bridge`.
- [ ] Selecting the project default **clears** the override.
- [ ] The Agents pane states that which agents run is the skill's decision, and offers no
      control to change it.
- [ ] Repository-mutating tools are marked; read-only ones are not.
- [ ] The footer gains `implr.config.yaml` only once a tier is overridden.
- [ ] With no defaults configured, nothing is pre-selected and the meter is empty.
- [ ] **The demo:** four surfaces move together, and setting the default back removes the key.

---

## What the next phase gets

The configurator's second tab, and the first surface that shows what a run will cost.
**Phase 6** adds the gate editor — the same modal shell with one pane, and the payoff of the
Python backend: an illegal status is refused while you design.
