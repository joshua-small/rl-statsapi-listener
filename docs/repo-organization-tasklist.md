# Repository Organization Tasklist

Created: 2026-05-09 (UTC)
Status: Execution started; media asset documentation and test-suite discoverability completed.

## Objectives
- Reduce duplicated entry points and stale compatibility layers.
- Make integration boundaries (core listener vs OBS script vs web overlay host) clearer.
- Improve contributor onboarding with concise, role-based docs.
- Keep assets and tests easy to audit as the overlay evolves.

## Prioritized Tasklist

### 1) Audit and classify root-level compatibility wrappers
- [ ] Confirm whether `listen.py`, `obs_rl_statsapi.py`, and any equivalent package entry points are still all needed.
- [ ] If redundant wrappers exist, deprecate with warnings first, then remove in a follow-up release.
- [ ] Add a short migration note in `README.md` for any removed commands.

### 2) Consolidate architecture docs
- [ ] Add a single `docs/architecture.md` with a "current state" diagram and responsibility map.
- [ ] Move deep implementation details out of `README.md` into focused docs pages.
- [ ] Keep `README.md` as quick-start + decision tree for "Which workflow should I use?"

### 3) Normalize integration documentation
- [ ] Create dedicated docs pages for each integration path:
  - OBS Python script workflow
  - Text-file output workflow
  - Browser overlay workflow
  - Windows WebView host workflow
- [ ] Ensure each page has setup steps, known limitations, and troubleshooting.

### 4) Prune outdated references and legacy terminology
- [ ] Review `docs/reference/obscounter-stats.txt` and annotate whether each item is still in scope.
- [ ] Remove or clearly mark aspirational/unfinished features in docs to reduce confusion.
- [ ] Check for stale commands/flags in README examples vs actual CLI help output.

### 5) Reorganize media assets for maintainability
- [x] Establish a documented naming convention for `media/icons/**`.
- [x] Decide whether `media/icons/rank/old/` should be archived externally or retained with explicit rationale.
- [x] Add a lightweight asset manifest (filename -> semantic meaning) for non-obvious icons.

Completed 2026-05-09 UTC in `docs/media-assets.md`. Current decision: retain `media/icons/rank/old/` as an explicit rollback/comparison set and keep runtime code pointed at `media/icons/rank/`.

### 6) Improve test-suite discoverability and grouping
- [x] Split tests conceptually (state logic, CLI behavior, web overlay rendering, integration contracts).
- [x] Add a short `tests/README.md` explaining how to run fast vs full test paths.
- [x] Identify any test fixtures that can be centralized to reduce duplication.

Completed 2026-05-09 UTC in `tests/README.md`. No test files were moved; the split is documented by behavioral surface so future changes can be organized without disturbing the current suite.

### 7) Add repository hygiene automation
- [ ] Add a minimal lint/format/type-check matrix appropriate to Python + JS test tooling.
- [ ] Add a CI check that validates docs examples against current CLI flags where practical.
- [ ] Add a periodic check for broken internal markdown links.

### 8) Document data directory contracts
- [ ] Add `docs/data-contracts.md` for `.data` inputs/outputs and schema expectations.
- [ ] Explicitly version snapshot file expectations to prevent silent importer drift.
- [ ] Document backup/restore workflows around `tools/backup_data.py` and SQLite files.

## Suggested Execution Phases

### Phase A (low risk, high clarity)
1. Architecture + integration docs consolidation.
2. Tests README and runbook updates.
3. README trimming and link cleanup.

### Phase B (medium risk)
1. Wrapper deprecation decisions.
2. Media asset policy + rank old/ archive decision.
3. Reference docs pruning.

### Phase C (higher effort)
1. Automation/CI additions.
2. Data contract versioning and validation checks.

## Exit Criteria
- New contributor can choose a workflow in under 2 minutes from docs.
- No ambiguous duplicate entry point remains undocumented.
- Docs examples match real commands and tested behavior.
- Asset and data contracts are explicit enough to support safe refactors.
