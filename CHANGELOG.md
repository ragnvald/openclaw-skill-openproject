# Changelog

## v0.1.4-alpha

- Added non-destructive API coverage for status/type/priority/user metadata lookups
- Added work package detail read and multi-field update command support
- Added work package relation list/create command support
- Updated `SKILL.md` and `README.md` to include expanded API-backed workflows

## v0.1.3-alpha

- Reduced skill scope to supported OpenProject work-package and markdown knowledge workflows
- Removed wiki read/write guidance from `SKILL.md` and `README.md`
- Clarified that wiki operations are out of scope due to inconsistent API behavior

## v0.1.2-alpha

- Documentation refresh for OpenProject wiki usage
- Expanded skill trigger description to include wiki read/write operations
- Added explicit wiki auth-mode guidance (`token` vs `basic`)
- Improved README troubleshooting and workflow notes for wiki endpoint compatibility

## v0.1.1-alpha

- Added wiki support commands (`list-wiki-pages`, `read-wiki-page`, `write-wiki-page`)
- Improved wiki compatibility/error messaging for API v3 stub scenarios
- Added helper tests for API path normalization and wiki payload parsing

## v0.1.0-alpha

- Initial skill definition
- CLI wrapper with core OpenProject operations
- Weekly summary and decision logging
