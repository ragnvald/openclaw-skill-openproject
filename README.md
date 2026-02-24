# openclaw-skill-openproject

`openclaw-skill-openproject` is an alpha OpenClaw skill that combines:
- Conservative OpenProject project management operations
- Work package metadata and relation management operations
- Lightweight knowledge handling in local Markdown files

The project is intentionally narrow and safety-first: OpenProject remains the source of truth for execution status, while weekly summaries and decision logs are generated as auditable local artifacts.

## Table of Contents

- Overview
- Goals and Non-Goals
- Design Principles
- Security Model
- Repository Layout
- Requirements
- Setup
- Configuration
- Authentication
- Command Reference
- Typical Workflows
- Knowledge Artifacts
- Testing and Validation
- Troubleshooting
- OpenProject Compatibility Notes
- Documentation Best Practices for Skill Projects
- Contributing
- Release Checklist
- Alpha Status and Roadmap
- License

## Overview

This repository provides:
- A skill definition in `SKILL.md` (`openproject-pm-knowledge`)
- A Python CLI wrapper in `scripts/openproject_cli.py`
- Markdown templates for reusable reporting and logging

The CLI is deliberately conservative:
- No delete operations
- No arbitrary shell execution behavior in skill policy
- Clear error messages with non-zero exit codes on failure
- Token/credential-safe output behavior

## Goals and Non-Goals

### Goals

- Use OpenProject API v3 as the authoritative PM backend.
- Support practical daily operations with low operational risk.
- Produce human-readable weekly summaries.
- Keep key decisions in simple, version-controlled Markdown.

### Non-Goals (v0.1.x)

- No destructive actions (`delete`, bulk destructive updates).
- No heavy framework or orchestration runtime.
- No broad enterprise workflow engine.
- No hidden side effects beyond explicit command behavior.

## Design Principles

- Conservative by default: explicit commands, explicit args, clear outcomes.
- Security first: minimal dependencies, least-privilege token usage, no secret leakage.
- Transparent behavior: output includes IDs and concise status.
- Extensible structure: helper functions and templates keep future changes simple.
- Version tolerance: best-effort fallback logic where OpenProject endpoints vary.

## Security Model

Primary security controls in this repo:
- API access through token-based auth by default (`apikey:<token>` basic auth pattern).
- No secret values printed in normal command output.
- Local `.env` usage with `.gitignore` protection.
- No delete operations in CLI command set.
- Explicit safety constraints documented in `SKILL.md` and `SECURITY.md`.

Read `SECURITY.md` before production usage.

## Repository Layout

```text
openclaw-skill-openproject/
  SKILL.md
  README.md
  LICENSE
  .gitignore
  .env.example
  requirements.txt
  SECURITY.md
  CHANGELOG.md
  scripts/
    openproject_cli.py
  project-knowledge/
    decisions/
      .gitkeep
    status/
      .gitkeep
  templates/
    decision-log-entry.md
    weekly-status-template.md
  tests/
    test_cli_helpers.py
```

## Requirements

- Python 3.10+
- OpenProject instance exposing API v3
- API token with least-privilege permissions for required operations

## Setup

1. Create and activate a virtual environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies.

```bash
python3 -m pip install -r requirements.txt
```

3. Configure environment.

```bash
cp .env.example .env
```

4. Validate CLI wiring.

```bash
python3 scripts/openproject_cli.py --help
```

## Configuration

Environment variables:

| Variable | Required | Description |
|---|---|---|
| `OPENPROJECT_BASE_URL` | Yes | Base URL, e.g. `https://openproject.example.org` |
| `OPENPROJECT_API_TOKEN` | Yes (default auth mode) | API token used with username `apikey` |
| `OPENPROJECT_DEFAULT_PROJECT` | No | Default project id/identifier for commands that support `--project` |
| `OPENPROJECT_DECISION_LOG_DIR` | No | Decision output directory (default `project-knowledge/decisions`) |

Reference `.env.example` for baseline values.

## Authentication

Default mode (`token`):
- Uses HTTP Basic auth with username `apikey` and password `<OPENPROJECT_API_TOKEN>`.

Quick auth check:

```bash
python3 scripts/openproject_cli.py list-projects
```

If auth fails, verify URL, token scope/validity, and server policy for API auth.

## Wiki Scope

Wiki operations are intentionally excluded from the supported skill workflow due to inconsistent API behavior across OpenProject instances.
If you need wiki updates, handle them manually outside this skill.

## Command Reference

General form:

```bash
python3 scripts/openproject_cli.py <subcommand> [options]
```

| Subcommand | Purpose | Key Arguments |
|---|---|---|
| `list-projects` | List visible projects | none |
| `list-work-packages` | List project work packages with optional filters | `--project`, `--status`, `--assignee`, `--limit` |
| `get-work-package` | Read one work package in detail | `--id` |
| `create-work-package` | Create a new work package | `--project`, `--subject`, `--type`, `--description` |
| `update-work-package-status` | Transition a work package status | `--id`, `--status` |
| `update-work-package` | Update multiple work package fields | `--id` plus any of `--subject`, `--description`, `--status`, `--assignee`, `--priority`, `--type`, `--start-date`, `--due-date` |
| `add-comment` | Add note/comment to work package | `--id`, `--comment` |
| `list-statuses` | List available statuses | none |
| `list-types` | List available types | optional `--project` |
| `list-priorities` | List available priorities | none |
| `list-users` | List visible users | optional `--query`, `--limit` |
| `list-relations` | List relations for one work package | `--id`, optional `--limit` |
| `create-relation` | Create a relation between work packages | `--from-id`, `--to-id`, `--type`, optional `--description`, `--lag` |
| `weekly-summary` | Generate compact markdown summary | `--project`, `--output` |
| `log-decision` | Write decision log markdown file | `--project`, `--title`, `--decision`, optional context fields |

Note: the CLI may still contain legacy wiki subcommands for compatibility experiments, but they are not part of the supported skill command set.

### Examples

```bash
python3 scripts/openproject_cli.py list-projects

python3 scripts/openproject_cli.py list-work-packages --project know-malawi --limit 50
python3 scripts/openproject_cli.py list-work-packages --project know-malawi --status "In progress"
python3 scripts/openproject_cli.py list-work-packages --project know-malawi --assignee "alice"
python3 scripts/openproject_cli.py get-work-package --id 123

python3 scripts/openproject_cli.py create-work-package \
  --project know-malawi \
  --subject "Define alpha rollout checklist" \
  --type Task \
  --description "Capture technical and process checks for alpha rollout."

python3 scripts/openproject_cli.py update-work-package-status --id 123 --status "In progress"
python3 scripts/openproject_cli.py update-work-package \
  --id 123 \
  --priority High \
  --assignee alice \
  --due-date 2026-03-05

python3 scripts/openproject_cli.py add-comment --id 123 --comment "Reviewed scope with platform team."
python3 scripts/openproject_cli.py list-statuses
python3 scripts/openproject_cli.py list-types --project know-malawi
python3 scripts/openproject_cli.py list-priorities
python3 scripts/openproject_cli.py list-users --query "alice"
python3 scripts/openproject_cli.py list-relations --id 123
python3 scripts/openproject_cli.py create-relation --from-id 123 --to-id 140 --type blocks --lag 1

python3 scripts/openproject_cli.py weekly-summary --project know-malawi
python3 scripts/openproject_cli.py weekly-summary --project know-malawi --output ./project-knowledge/status/custom-weekly.md

python3 scripts/openproject_cli.py log-decision \
  --project know-malawi \
  --title "Use OpenProject as PM source of truth" \
  --decision "Adopt OpenProject work packages as canonical execution tracker." \
  --context "Team currently tracks work in multiple systems." \
  --impact "Improves visibility and reduces duplicate updates." \
  --followup "Migrate outstanding sprint items by Friday."
```

## Typical Workflows

### Daily status check

1. Run `list-work-packages` with relevant filters.
2. Identify WPs needing movement or clarification.
3. Add comments to capture context and unblockers.

### Planning and execution

1. Inspect available statuses/types/priorities before changes (`list-statuses`, `list-types`, `list-priorities`).
2. Create work packages for new actionable items.
3. Move status or patch multiple fields using `update-work-package-status` / `update-work-package`.
4. Use relations to model dependencies (`list-relations`, `create-relation`).
5. Keep rationale and decisions in `project-knowledge/decisions/`.

### Weekly reporting

1. Run `weekly-summary` for the target project.
2. Review generated sections and adjust narrative externally if needed.
3. Keep generated file in `project-knowledge/status/` as historical record.

## Knowledge Artifacts

### Weekly summary output

Default output path:
- `project-knowledge/status/YYYY-MM-DD-weekly-status.md`

Section shape:
- Wins / completed
- In progress
- Blockers / risks
- Next focus

### Decision log output

Default output path:
- `project-knowledge/decisions/YYYY-MM-DD_<slugified-title>.md`

Content shape:
- Date
- Project
- Title
- Context
- Decision
- Impact
- Follow-up

Templates are available in `templates/` for manual authoring consistency.

## Testing and Validation

Recommended local checks:

```bash
python3 -m py_compile scripts/openproject_cli.py
python3 scripts/openproject_cli.py --help
python3 -m unittest discover -s tests -p 'test_*.py'
```

Use a non-production/test project for write operations during validation.

## Troubleshooting

### `401` / `403` authentication errors

- Verify `OPENPROJECT_BASE_URL` and token correctness.
- Confirm token has required permissions.
- Confirm server policy allows your selected auth mode.

### `422` status transition errors

- Target status may not be allowed for current role/workflow/state.
- Try a valid intermediate transition supported by your OpenProject workflow.

### `422` on `update-work-package`

- Verify field combinations are valid for your workflow/schema.
- Confirm `--start-date` and `--due-date` use `YYYY-MM-DD`.
- Resolve users/types/priorities first with `list-users`, `list-types`, and `list-priorities`.

### Comment command fails

- Comment endpoints differ across OpenProject versions/configuration.
- CLI uses best-effort fallbacks, but some setups still restrict API comment writes.

### Command works in terminal but fails in tool runtime

- Verify correct interpreter/environment (`python3` vs virtualenv interpreter).
- Confirm `.env` is present in repository root.

## OpenProject Compatibility Notes

This project targets OpenProject API v3 but behavior may vary across versions and deployments.

Known variability points:
- Comment creation endpoint behavior (`addComment`, patch comment, activities endpoint)
- Workflow-restricted status transitions
- Project-specific availability of types/statuses/custom fields

Treat this repository as conservative baseline logic; tune for your instance policies.

## Documentation Best Practices for Skill Projects

This project follows these documentation practices, which are recommended for similar skill repositories:

- Keep one canonical README for onboarding and operations.
- Separate policy from implementation.
- Policy belongs in `SKILL.md` (agent behavior, constraints).
- Implementation details belong in code docs and command help.
- Keep examples executable.
- Every documented command should run as written (modulo project/token values).
- Document non-goals explicitly.
- Prevent misuse by stating what the skill intentionally does not do.
- Document trust boundaries.
- Clearly define where secrets live, how auth works, and what is never printed.
- Document failure modes.
- Include realistic error classes and next actions.
- Prefer stable file conventions.
- Date-based filenames and predictable paths simplify auditability.
- Include maintainers' validation steps.
- A short quality gate section reduces regressions in future changes.
- Keep docs version-aware.
- Note where external API behavior may differ by server version.

Suggested minimum docs for any production-minded skill repo:
- `README.md`
- `SKILL.md`
- `.env.example`
- `SECURITY.md`
- `CHANGELOG.md`
- License file

## Contributing

1. Create a branch from `main`.
2. Keep changes focused and small.
3. Run local validation checks.
4. Update README/SKILL/docs when behavior changes.
5. Open PR with clear scope, risk notes, and test evidence.

Do not commit secrets, `.env`, or generated local artifacts.

## Release Checklist

- Update `CHANGELOG.md`.
- Verify CLI help and all subcommands.
- Run tests and syntax checks.
- Validate examples in README.
- Confirm no secret material in git diff.
- Tag release after merge.

## Alpha Status and Roadmap

Current stage: `v0.1.0-alpha`

Short-term (`v0.2`) ideas:
- Stronger server-side filtering controls
- Richer weekly summary heuristics
- Optional output customization hooks

Mid-term (`v0.3`) ideas:
- Enhanced workflow-transition introspection
- Optional custom-field-aware summaries
- Optional linkbacks between decisions and work packages

## License

MIT. See `LICENSE`.
