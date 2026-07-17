# CR Schema

Canonical structure for Change Requests (CR-NNN). Produced by `ba-cr`. Consumed by `ba-cr`
(impact analysis), `ba-requirements-gen` (--reprocess), and (future) `ba-jira-populate`.

---

## Change Request — full structure

~~~markdown
---
cr_id: CR-001
slug: azure-cost-cap-reduction
title: Reduce Azure Monthly Cost Cap from $500 to $20–50
status: draft           # draft | approved | rejected | applied
change_type: constraint-change
                        # constraint-change | scope-reduction | scope-expansion
                        # new-rule | correction | override
source: cli-direct      # cli-direct | manual-file | kb-document
affected_domains: []    # populated by ba-cr after impact analysis
targets: []             # all confirmed affected requirement IDs (full impact set).
                        # written by ba-cr after the approval gate from cr-impact-analyzer's
                        # returned set. NOT the applied subset — see cr-log.md for
                        # applied_targets / excluded_targets.
before: ""              # auto-extracted by ba-cr from user input; old value/behaviour
after: ""               # auto-extracted by ba-cr from user input; new value/behaviour
rationale: ""           # captured during ba-cr interview
created_at: {ISO timestamp}
approved_at:            # stamped when human approves at approval gate
applied_at:             # stamped when all downstream chains complete
jira:
  id:                   # filled by ba-jira-populate (e.g. PROJ-99)
  issue_type: Task      # Task or Story depending on project convention
  priority: Medium      # derived from change_type:
                        #   override/constraint-change → High
                        #   new-rule/scope-expansion → Medium
                        #   correction → Low
  labels: [change-request]
  components: []        # derived from affected_domains after impact analysis
  story_points:
  epic_link:
  linked_issues: []     # populated after impact analysis from affected req Jira IDs
                        # format: [{id: "PROJ-12", link_type: "relates to"}]
---

# CR-001 — {title}

## Description of Change
Plain-language explanation of what is changing and why. Written by ba-cr from user input.

## Expected Impact (Human Note, optional)
Human's own assessment of what this will touch. Leave blank if using ba-cr impact analysis.
~~~

---

## cr-index.md — Current-State Register

Location: `docs/implr/requirements/cr-index.md`

Maintained by ba-cr. Do not edit manually.

~~~markdown
# CR Index

> Maintained by ba-cr. Do not edit manually.
> Last updated: {ISO timestamp}

## Change Requests

| CR ID  | Title | Status | Change Type | Affected Reqs | Applied At |
|--------|-------|--------|-------------|---------------|------------|

## Pending Human Action

_(none)_
~~~

---

## cr-log.md — Append-Only Run History

Location: `docs/implr/requirements/cr-log.md`

~~~markdown
# cr-log
# Append-only run history for ba-cr. Newest entry first.

---

## {ISO timestamp} — {cr_id} — {status}

- **CR:** {cr_id} {title}
- **Trigger:** cli-direct | manual-file | kb-document
- **Phases executed:** {list}
- **Requirements updated:** {list of req IDs, or none}
- **Plans replanned:** {list of plan IDs, or none}
- **arch-gen triggered:** yes | no
- **Applied targets:** {list of req IDs applied this run, or none}
- **Excluded targets:** {list of req IDs the user declined this run, or none}
~~~

`targets` on the CR frontmatter is the durable full impact set; `applied_targets`/`excluded_targets` here are per-run because a later run may apply a previously excluded target.

---

## change_type Values

| Value | When to use |
|-------|------------|
| `constraint-change` | A numeric or categorical limit is changing (cost cap, rate limit, SLA target) |
| `scope-reduction` | Functionality is being removed or narrowed |
| `scope-expansion` | New functionality is being added beyond existing requirements |
| `new-rule` | A business rule that did not previously exist is being introduced |
| `correction` | A requirement was wrong or misunderstood; this corrects it |
| `override` | A previously approved decision is being reversed |

---

## status Lifecycle

~~~
draft → approved → applied
      ↘ rejected
~~~

- `draft` — created by ba-cr during interview, from a manual file, or auto-generated from a KB doc
- `approved` — human approved at the ba-cr approval gate
- `rejected` — human rejected; terminal state (create a new CR to supersede)
- `applied` — all downstream chains completed successfully
