# Jira Integration Schema

Defines how implr requirements map to Jira issues. Used by the future `ba-jira-populate` skill.
The requirement schema already carries the `jira:` block; this file documents the mapping and
the configuration contract so the data is ready before the skill is built.

---

## Field Mapping

| Requirement field | Jira field | Notes |
|------------------|-----------|-------|
| `title` | Summary | Direct |
| `summary` | Description (lead paragraph) | |
| `detailed_description` | Description (body) | Markdown converted to Jira wiki/ADF |
| `acceptance_criteria` | Acceptance Criteria field or Description section | Depends on Jira config |
| `jira.issue_type` | Issue Type | Epic / Story / Task / Bug |
| `jira.priority` | Priority | Critical / High / Medium / Low |
| `jira.labels` | Labels | |
| `jira.epic_link` | Epic Link | Resolved from a REQ id to its Jira key |
| `jira.components` | Components | Must exist in the Jira project |
| `jira.story_points` | Story Points | Custom field, configurable id |
| `subtasks` | Child issues | Created as Subtask type or linked Tasks (config) |
| `req_id` | Custom field `implr_req_id` | Bidirectional traceability |

---

## Configuration Contract

`ba-jira-populate` reads connection and mapping config from `implr.config.yaml`:

```yaml
jira:
  base_url: https://your-org.atlassian.net
  project_key: STOK
  api_token_env: JIRA_API_TOKEN      # name of env var holding the token; never the token itself
  api_email_env: JIRA_API_EMAIL      # Atlassian account email for basic auth
  default_issue_type: Story
  default_priority: Medium
  subtask_strategy: subtask          # subtask | linked_task
  custom_fields:
    implr_req_id: customfield_10001
    story_points: customfield_10016
```

The API token is always read from an environment variable, never stored in any file.

---

## Mapping Behaviour (for the future skill)

1. Process only requirements with `status: approved`.
2. Skip requirements that already have a non-empty `jira.id` (idempotent — never duplicate).
3. Create the issue via Jira REST API v3.
4. Write the returned issue key back into the requirement's `jira.id` field and bump
   `updated_at`.
5. Create subtasks (per `subtask_strategy`) and link them to the parent.
6. Set the `implr_req_id` custom field on every created issue for traceability.
7. Record a run log entry (mirroring digest-log style) under
   `docs/implr/requirements/jira-sync-log.md`.

---

## Epic Handling

- A requirement with `jira.issue_type: Epic` is created first.
- Requirements referencing it via `jira.epic_link: REQ-F-NNN` are linked once the epic's Jira
  key is known. The skill resolves `REQ-F-NNN` → its `jira.id` at link time.

---

## Error Handling

- Missing env var for the token → stop with a clear message, create nothing.
- Component or custom field not found in Jira → skip that field, warn, continue.
- API error on one requirement → log, continue with the rest, summarise failures at the end.

This file is a forward contract. No skill consumes it yet; `ba-requirements-gen` populates the
`jira:` block with sensible defaults so the data is present when the skill is added.
