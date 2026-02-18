# OpenCode Migration Plan

## Step 1 - Audit Claude Surface (Completed)

- [x] Clone repo and create audit branch `chore/opencode-migration-audit`
- [x] Generate baseline snapshots in `tasks/migration-audit/00-*`
- [x] Generate code/config/docs footprint in:
  - `tasks/migration-audit/01-claude-footprint.txt`
  - `tasks/migration-audit/02-provider-env-footprint.txt`
  - `tasks/migration-audit/03-dependency-footprint.txt`
  - `tasks/migration-audit/04-claude-files.txt`
  - `tasks/migration-audit/05-provider-env-files.txt`

## Step 2 - Introduce OpenCode Provider Layer (Planned)

- [ ] Add provider abstraction under `src/agent/` and move shared response/session types there
- [ ] Implement `OpenCodeSDKManager` and `OpenCodeProcessManager` under `src/opencode/`
- [ ] Add adapter facade `OpenCodeIntegration` compatible with current call sites
- [ ] Update dependency injection and runtime wiring in `src/main.py`
- [ ] Add new config fields/env vars for OpenCode while keeping temporary Claude compatibility aliases
- [ ] Update tests to cover both provider parity and OpenCode-default behavior

## Step 3 - Validate, Rollout, and Remove Claude-Only Paths (Planned)

- [ ] Run unit/integration tests and lint checks
- [ ] Add migration guide with env var mapping and operational runbook
- [ ] Replace CI workflows from Claude actions to OpenCode-compatible checks
- [ ] Switch defaults to OpenCode and remove Claude-only dependencies
- [ ] Perform final cleanup rename pass (`claude_*` identifiers, docs, package metadata)

## Review

- Audit completed and artifacts saved under `tasks/migration-audit/`
- Next work starts with non-breaking provider abstraction to keep deployment safe
