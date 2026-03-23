# GitHub Community Health Design

**Goal:** Add a complete baseline GitHub collaboration layer so contributors have clear issue intake, pull request guidance, ownership routing, dependency upkeep, and CI entry points.

## Scope

- Add GitHub issue forms for bugs, feature requests, and documentation updates.
- Add issue configuration that disables blank issues and points users to docs and security policy.
- Add a pull request template for change summary, validation, screenshots, and release-impact notes.
- Add `CODEOWNERS`, `Dependabot`, and a baseline CI workflow aligned with existing backend and frontend commands.
- Update contributor-facing docs so the new GitHub workflow is discoverable.

## Approach

- Keep the package intentionally small and conventional: use standard GitHub-native files under `.github/`.
- Reuse the repository's current verification surface instead of inventing new tooling. Backend CI will run `pytest`; frontend CI will run `lint`, `test`, and `build`.
- Keep ownership simple with a single maintainer as the default owner, while still separating major repository areas for future expansion.
- Use bilingual issue form labels where it improves accessibility without making the forms verbose.

## Non-Goals

- Do not add release automation, stale issue bots, funding metadata, or citation metadata in this pass.
- Do not change runtime code, package dependencies, database schema, or application behavior.
- Do not introduce new local tooling requirements such as pre-commit hooks or external workflow linters.

## Risks

- The largest practical risk is adding GitHub automation that does not match the repository's current commands.
- `CODEOWNERS` is only as accurate as the current maintainer mapping, so it should stay minimal until the maintainer group expands.
- Dependabot volume can become noisy if update cadence is too aggressive, so the initial schedule should stay weekly.

## Validation

- Parse every added YAML file to confirm valid syntax.
- Check the repository diff for formatting and whitespace issues.
- Verify the workflow commands match commands already documented in `Makefile` and `CONTRIBUTING.md`.
