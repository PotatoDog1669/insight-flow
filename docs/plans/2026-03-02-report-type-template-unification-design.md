# Report Type & Template Unification Design

## Goal

Remove the old `depth` concept (`brief/deep`) and unify report generation around explicit template types:

- `daily`
- `weekly`
- `research`

At the same time, support monitor schedules:

- `daily` (auto)
- `weekly` (auto)
- `custom` (cron auto + user-selected template type)

## Why Change

Current behavior mixes two incompatible models:

1. Data/API model exposes `depth` only (`brief/deep`).
2. Renderer layer still carries L1/L2/L3/L4 semantics.
3. Runtime generation mostly persists one `deep` report, which does not match product wording.

This causes product-language drift and makes monitor configuration confusing.

## Scope

In scope:

- Database schema migration (`depth` -> `report_type`)
- Monitor schema alignment (`depth` removal + `report_type` addition)
- Scheduler and manual run logic alignment with schedule/template rules
- API contract updates for monitors/reports/users settings
- Frontend monitor/report UI and filters alignment
- One-time migration of historical report and monitor data
- Template-based report generation as the primary mechanism

Out of scope:

- Major content quality redesign for weekly/research narratives
- New sink providers
- Historical backfill beyond direct field mapping

## Target Domain Model

### Reports

- Replace `reports.depth` with `reports.report_type`.
- `report_type` allowed values:
  - `daily`
  - `weekly`
  - `research`

### Monitors

- Keep schedule dimension (`time_period`) for execution cadence:
  - `daily`
  - `weekly`
  - `custom`
- Remove monitor `depth`.
- Add monitor `report_type`:
  - For `daily` monitor: fixed to `daily`
  - For `weekly` monitor: fixed to `weekly`
  - For `custom` monitor: user-selectable (`daily|weekly|research`)

### User Settings

- Replace `default_depth` with `default_report_type`.

## Scheduling Rules

### Automatic Runs

- `time_period=daily` -> runs daily -> generates `report_type=daily`.
- `time_period=weekly` -> runs weekly -> generates `report_type=weekly`.
- `time_period=custom` + cron -> runs by cron -> generates monitor-selected `report_type`.

### Manual Runs

- Manual trigger always uses that monitor's `report_type`.

## Template Strategy

Use templates as the primary report-output contract:

- `templates/reports/daily/...`
- `templates/reports/weekly/...`
- `templates/reports/research/...`

The backend should:

1. Prepare structured context (`events`, `topics`, `tldr`, metadata).
2. Select template by `report_type`.
3. Render final content for web and sinks.

Renderer-level L1/L2/L3/L4 naming is no longer a product-facing taxonomy and should be phased out.

## Migration Plan (One-time)

### Reports table migration

1. Add `report_type` column (nullable first).
2. Backfill:
   - if `time_period='weekly'` -> `report_type='weekly'`
   - else -> `report_type='daily'`
3. Add non-null constraint + index on `report_type`.
4. Remove `depth` column.

### Monitors table migration

1. Add `report_type` column (nullable first).
2. Backfill:
   - `time_period='daily'` -> `report_type='daily'`
   - `time_period='weekly'` -> `report_type='weekly'`
   - `time_period='custom'` -> `report_type='daily'` (default baseline)
3. Add non-null constraint.
4. Remove `depth` column.

### User settings migration

Transform stored settings:

- `default_depth` -> `default_report_type`
- map existing values:
  - `brief` -> `daily`
  - `deep` -> `research` (or `daily`, based on migration policy; pick one explicitly in implementation)

## API Contract Changes

### Monitors API

- Remove `depth` from create/update/response.
- Add `report_type`.
- Validation:
  - if `time_period='custom'`, `report_type` required
  - if `time_period='daily'`, force `report_type='daily'`
  - if `time_period='weekly'`, force `report_type='weekly'`

### Reports API

- Replace filter `depth` with `report_type`.
- Update response schema to expose `report_type`.
- Keep response `metadata.report_type` only as optional redundant data during transition.

### Users API

- Replace `default_depth` with `default_report_type`.

## Frontend Changes

### Monitor Create/Edit

- Remove depth selector.
- Keep schedule selector (`daily|weekly|custom`).
- For `custom`, show `report_type` selector.
- For `daily/weekly`, display locked template type.

### Reports List/Discover/Library

- Replace depth badges and filter chips with report-type badges:
  - Daily
  - Weekly
  - Research

### Report Detail

- Remove hardcoded `brief->L1 / deep->L2` mapping.
- Display report type directly.

## Risks and Mitigations

1. Risk: older clients still send `depth`.
   - Mitigation: temporary compatibility parser for one release window (optional).

2. Risk: data migration ambiguity (`deep` historical meaning).
   - Mitigation: deterministic mapping and migration note in release docs.

3. Risk: weekly/research template quality gaps.
   - Mitigation: default to safe minimal templates and iterate content quality separately.

## Testing Strategy

Backend:

- migration tests for report/monitor/users settings mapping
- API contract tests for monitor/report schemas and filter params
- scheduler tests for daily/weekly/custom + report_type routing
- monitor run tests asserting stored report_type and publish flow

Frontend:

- monitor form behavior tests (custom template selector and validation)
- reports filter tests (`report_type`)
- report card/detail badge rendering tests

E2E:

- create custom monitor with cron + `report_type=research`
- run scheduled/manual and verify persisted report_type + log visibility

## Rollout Plan

1. Ship migration + backward-compatible API parsing.
2. Deploy backend first.
3. Deploy frontend with new fields/filters.
4. Remove compatibility shim after verification window.

## Success Criteria

1. No `depth` field in DB schema, API contracts, or frontend state.
2. Every generated report has explicit `report_type`.
3. Monitor schedule and report template semantics are clear and consistent.
4. Existing historical data remains queryable after migration.
