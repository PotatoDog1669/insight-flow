# Reddit Custom Subreddits Design

**Date:** 2026-03-19  
**Status:** Approved  
**Scope:** Make the Reddit source configurable like X so users can add and remove tracked subreddits while preserving the existing default watchlist

---

## 1. Goal

Replace the hardcoded Reddit RSS query with a configurable `subreddits` list that behaves like X `usernames`.

Users should be able to:

- see the current subreddit watchlist
- add a subreddit
- remove a subreddit
- keep the existing default values on seeded sources

The change should not expand Reddit collection scope beyond the current RSS-based strategy.

## 2. Current State

Today the Reddit preset is fixed to a single `feed_url`:

- `https://www.reddit.com/search.rss?q=subreddit:LocalLLaMA OR subreddit:singularity OR subreddit:OpenAI&sort=new`

That means:

- subreddit selection is not user-configurable
- UI treats Reddit like a generic RSS source
- changing coverage requires editing preset YAML or raw config

This is inconsistent with X, where the source exposes a first-class editable list of tracked accounts.

## 3. Product Decision

Reddit should expose a first-class `subreddits: string[]` config field.

Behavior rules:

- seeded Reddit sources keep the current default values: `LocalLLaMA`, `singularity`, `OpenAI`
- users edit `subreddits` through chip-style add/remove interactions in the source detail modal
- subreddit input is free-form text
- input is normalized by removing leading `r/`, trimming whitespace, and de-duplicating case-insensitively
- Reddit continues using public RSS only
- Reddit does not expose direct `feed_url` editing in the UI

## 4. Recommended Approach

Use a Reddit-specific config flow layered on top of the existing RSS collector instead of adding a new collector.

Why this is the right fit:

- keeps the implementation small
- reuses the existing RSS pipeline and tests
- matches the existing X mental model in the UI
- preserves backward compatibility with current seeded data

## 5. Data Model And Config Contract

Reddit source config should support:

```json
{
  "subreddits": ["LocalLLaMA", "singularity", "OpenAI"],
  "max_items": 30,
  "fetch_detail": false,
  "user_agent": "LexDeepResearchBot/0.1"
}
```

Compatibility expectations:

- `feed_url` may still exist on older rows
- bootstrap should populate `subreddits` for the seeded Reddit source
- runtime config resolution should derive `feed_url` from `subreddits` when the source is Reddit
- generic RSS sources remain unchanged and continue using editable `feed_url`

## 6. Backend Design

### 6.1 Preset Seeding

Update the Reddit preset so the canonical source of truth is `collect_config.subreddits`, not a fixed RSS URL string.

Bootstrap should merge persisted Reddit `subreddits` with synced defaults in the same spirit as X username merging:

- keep existing user-added values
- preserve default seeded values
- output a normalized deduplicated array

### 6.2 Runtime Resolution

When the orchestrator prepares a Reddit RSS source, it should:

- read `config.subreddits`
- normalize and deduplicate them
- build a Reddit RSS search URL with `sort=new`
- place the derived URL into `config.feed_url`

If `subreddits` is empty after normalization:

- fall back to the seeded defaults for the built-in Reddit source

This keeps collection resilient and avoids turning the source into a silently broken empty query.

### 6.3 Collector Scope

The generic RSS collector should stay generic.

No Reddit-only behavior should be pushed into `RSSCollector` if it can be handled earlier during config preparation. This keeps the collector contract simple: it still receives a resolved `feed_url`.

## 7. Frontend Design

### 7.1 Source Detail Modal

`SourceDetailModal` should add a Reddit-specific editor that mirrors the X username editor:

- label: `Tracked Subreddits`
- input placeholder: `r/LocalLLaMA`
- add button
- removable chips for each configured subreddit
- immediate persistence on add/remove
- no separate save button for subreddit changes

Normalization rules in the UI:

- `r/LocalLLaMA` becomes `LocalLLaMA`
- empty values are ignored
- duplicates are removed regardless of case

### 7.2 URL Editing Behavior

Generic RSS sources should still show `Target URL`.

Reddit should not, because exposing both `feed_url` and `subreddits` would create conflicting configuration paths.

## 8. Testing Strategy

Add coverage for:

- bootstrap merging of Reddit default and persisted subreddit lists
- runtime feed URL derivation from `subreddits`
- modal add/remove persistence for Reddit subreddits
- normalization rules such as `r/` stripping and deduplication

Keep tests targeted and avoid broad unrelated UI churn.

## 9. Risks And Mitigations

### Risk: Old rows only contain `feed_url`

Mitigation:

- seed the canonical built-in Reddit source with defaults on every bootstrap
- resolve runtime `feed_url` from `subreddits` so future runs stop depending on the old URL string

### Risk: Invalid subreddit names

Mitigation:

- normalize basic syntax only
- stay permissive in the UI
- let the RSS endpoint be the final validator

### Risk: Generic RSS regression

Mitigation:

- scope Reddit logic to explicit source identity checks
- preserve existing RSS modal behavior for all non-Reddit sources

## 10. Non-Goals

This change does not:

- add Reddit API integration
- collect comments, score, flair, or author metadata
- add subreddit discovery or autocomplete
- expose Reddit-specific sort or time range controls
