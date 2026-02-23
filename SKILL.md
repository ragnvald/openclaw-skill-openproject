---
name: openproject-pm-knowledge
description: Manage OpenProject work packages and lightweight project knowledge artifacts (weekly summaries and decision logs). Use when work requires reading project/work package status, creating or updating work packages, adding comments, generating weekly markdown status updates, or logging project decisions.
---

# OpenProject PM + Knowledge Skill

Purpose: use OpenProject as project source of truth and keep lightweight knowledge artifacts in markdown.

## Safety Rules

- Never execute arbitrary shell commands.
- Only use the local Python wrapper: `scripts/openproject_cli.py`.
- Never expose API tokens, credentials, or secret values.
- Do not perform delete operations in v1.
- Fail closed with clear errors when permissions, transitions, or endpoints are not available.

## Environment Variables

- `OPENPROJECT_BASE_URL` (required): OpenProject base URL, e.g. `https://openproject.example.org`.
- `OPENPROJECT_API_TOKEN` (required for default auth): API token used with username `apikey`.
- `OPENPROJECT_DEFAULT_PROJECT` (optional): default project id/identifier used when `--project` is omitted.
- `OPENPROJECT_DECISION_LOG_DIR` (optional): directory for decision markdown files. Default: `project-knowledge/decisions`.

## Supported Operations

Use `python scripts/openproject_cli.py <command> [args]`.

- `list-projects`
  - List visible projects with project ID, identifier, and name.
- `list-work-packages --project <id|identifier> [--status ...] [--assignee ...] [--limit N]`
  - List work packages with WP ID, subject, status, assignee, and updated date.
  - Applies filtering conservatively (API-side where practical, otherwise client-side).
- `create-work-package --project <id|identifier> --subject "..." [--type Task] [--description "..."]`
  - Create a work package and print created ID and subject.
  - Resolves type by name with helpful errors if type is unknown.
- `update-work-package-status --id <wp_id> --status "..."`
  - Resolve status by name (case-insensitive) and patch the work package.
  - Prints confirmation including WP ID and resulting status.
- `add-comment --id <wp_id> --comment "..."`
  - Best-effort comment creation using OpenProject API v3.
  - Returns a clear message when endpoint behavior differs by version/config.
- `weekly-summary --project <id|identifier> [--output path.md]`
  - Build compact markdown grouped by completion/in-progress/blockers/next focus.
  - Writes output to provided path or default `project-knowledge/status/YYYY-MM-DD-weekly-status.md`.
- `log-decision --project <id|identifier> --title "..." --decision "..." [--context ...] [--impact ...] [--followup ...]`
  - Create a decision markdown entry in `project-knowledge/decisions`.

## Agent Behavior

### Project status

- Prefer `list-work-packages` against the project in scope.
- Summarize by status buckets and include key WP IDs in outputs.
- Flag uncertainty explicitly when status labels are ambiguous.

### Creating tasks

- Use `create-work-package` with clear subject and optional description.
- Keep task type explicit when not defaulting to `Task`.
- Return created WP ID for traceability.

### Updating tasks

- Use `update-work-package-status` for status changes.
- Resolve status by name and handle transition errors clearly.
- Confirm update with WP ID and resulting status label.

### Weekly status summary

- Use `weekly-summary`.
- Produce compact markdown with sections:
  - Wins / completed
  - In progress
  - Blockers / risks
  - Next focus
- Save summary in `project-knowledge/status/` with date-based filename unless output path is provided.

### Decision logging

- Use `log-decision` for durable decisions.
- Capture context, decision, impact, and follow-up actions.
- Store files under `project-knowledge/decisions/` with date + slug naming.

## Output Style

- Keep outputs concise and structured.
- Always include work package IDs (e.g., `#123`) when referencing tasks.
- Prefer markdown lists and short sections over long prose.
