# openclaw-skill-openproject

`openclaw-skill-openproject` is an alpha OpenClaw skill for conservative OpenProject project management plus lightweight markdown knowledge handling.

It treats OpenProject as the source of truth for work package/project status and adds local artifacts for:
- Weekly status summaries
- Decision logs

## What This Skill Does

- Lists OpenProject projects and work packages
- Creates work packages
- Updates work package status
- Adds comments to work packages (best effort by API version/config)
- Generates weekly status markdown summaries
- Logs project decisions in markdown files

## What This Skill Does Not Do

- No delete operations
- No arbitrary shell command execution policy
- No secret/token output
- No broad automation framework or destructive actions

## Repository Structure

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
```

## Requirements

- Python 3.10+
- OpenProject API v3 access
- API token with least-privilege permissions for intended actions

## Setup

1. Create and activate a virtual environment.

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies.

```bash
pip install -r requirements.txt
```

3. Configure environment.

```bash
cp .env.example .env
# then edit .env values
```

4. Verify CLI help.

```bash
python scripts/openproject_cli.py --help
```

## Environment Variables

- `OPENPROJECT_BASE_URL` (required)
- `OPENPROJECT_API_TOKEN` (required for default auth)
- `OPENPROJECT_DEFAULT_PROJECT` (optional)
- `OPENPROJECT_DECISION_LOG_DIR` (optional)

## CLI Usage

General form:

```bash
python scripts/openproject_cli.py <subcommand> [options]
```

### 1) List projects

```bash
python scripts/openproject_cli.py list-projects
```

### 2) List work packages

```bash
python scripts/openproject_cli.py list-work-packages --project my-project --limit 50
python scripts/openproject_cli.py list-work-packages --project my-project --status "In progress"
python scripts/openproject_cli.py list-work-packages --project my-project --assignee "alice"
```

### 3) Create work package

```bash
python scripts/openproject_cli.py create-work-package \
  --project my-project \
  --subject "Define alpha rollout checklist" \
  --type Task \
  --description "Capture technical and process checks for alpha rollout."
```

### 4) Update work package status

```bash
python scripts/openproject_cli.py update-work-package-status --id 123 --status "In progress"
```

### 5) Add comment

```bash
python scripts/openproject_cli.py add-comment --id 123 --comment "Reviewed scope with platform team."
```

### 6) Weekly summary

```bash
python scripts/openproject_cli.py weekly-summary --project my-project
python scripts/openproject_cli.py weekly-summary --project my-project --output ./project-knowledge/status/custom-weekly.md
```

### 7) Decision logging

```bash
python scripts/openproject_cli.py log-decision \
  --project my-project \
  --title "Use OpenProject as PM source of truth" \
  --decision "Adopt OpenProject work packages as canonical execution tracker." \
  --context "Team currently tracks work in multiple systems." \
  --impact "Improves visibility and reduces duplicate updates." \
  --followup "Migrate outstanding sprint items by Friday."
```

## Security Notes

- Never commit `.env`.
- Use least-privilege API tokens.
- Review scripts before running in production environments.
- Do not paste secrets into logs, issues, PRs, or chat.

See `SECURITY.md` for reporting guidance.

## Alpha Status

This is `v0.1.0-alpha`.

Expect small behavioral differences across OpenProject versions, especially around:
- Comment write endpoints
- Status transitions enforced by workflow rules
- Available type/status catalogs by project and permissions

## Roadmap

### v0.2 ideas

- Better server-side filtering and pagination
- Optional richer summary heuristics (aging work, owner load)
- Configurable markdown output formatting

### v0.3 ideas

- Workflow-aware transition checks before updates
- Optional mapping of custom fields into summaries
- Optional sync helpers for linking local decisions to work packages

## License

MIT. See `LICENSE`.
