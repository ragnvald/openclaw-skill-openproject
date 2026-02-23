---
name: openproject-pm-knowledge
description: Manage OpenProject work packages, wiki pages, and lightweight project knowledge artifacts (weekly summaries and decision logs). Use when work requires reading project/work package status, creating or updating work packages, adding comments, reading or updating OpenProject wiki content, generating weekly markdown status updates, or logging project decisions.
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
- `OPENPROJECT_AUTH_MODE` (optional): `token` (default) or `basic`.
- `OPENPROJECT_USERNAME` and `OPENPROJECT_PASSWORD` (optional): used when `OPENPROJECT_AUTH_MODE=basic`; can be required for some legacy wiki endpoints.

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
- `list-wiki-pages --project <id|identifier>`
  - List wiki pages for a project (legacy JSON endpoint compatibility).
- `read-wiki-page [--id <wiki_id> | --project <id|identifier> --title "..."] [--output path.md]`
  - Read wiki page metadata via API v3 and page text via legacy JSON endpoint when available.
- `write-wiki-page --project <id|identifier> --title "..." (--content "..." | --content-file path.md) [--comment "..."]`
  - Create or update wiki page content via legacy JSON endpoint compatibility.
  - If legacy endpoint auth fails in token mode, switch to `OPENPROJECT_AUTH_MODE=basic` and use `OPENPROJECT_USERNAME` / `OPENPROJECT_PASSWORD`.
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

### Wiki read/write

- Use `list-wiki-pages` to discover wiki page titles within a project.
- Use `read-wiki-page` for metadata-first reads (`--id`) and full text reads (`--project --title`).
- Use `write-wiki-page` to create/update wiki pages with explicit text payload.
- Prefer `--content-file` for larger wiki updates to keep command history clean and auditable.
- Report capability limits clearly when OpenProject API v3 exposes wiki metadata only or when legacy endpoints are blocked by auth mode.

### Decision logging

- Use `log-decision` for durable decisions.
- Capture context, decision, impact, and follow-up actions.
- Store files under `project-knowledge/decisions/` with date + slug naming.

## Output Style

- Keep outputs concise and structured.
- Always include work package IDs (e.g., `#123`) when referencing tasks.
- Prefer markdown lists and short sections over long prose.
