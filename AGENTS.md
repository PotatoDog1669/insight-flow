# LexDeepResearch — Coding Standards

## Spec & Planning Files

- **Before implementing any feature**, read the relevant docs:
  - `.spec/PRD.md` — product priorities (P0/P1/P2)
  - `.spec/TEC.md` — DB schema, API contracts, module design
  - `.spec/plans/` — per-feature design & implementation plans
- Only implement **P0 features fully**. P1+ only warrant schema/interface stubs.

---

## Code Style

### General
- Be **concise and direct**. Avoid over-engineering.
- Prefer **explicit over implicit**, but never verbose.
- No dead code, no commented-out blocks, no TODO left in PRs.

### Python (Backend)
- Python 3.12+, async-first (`async/await` throughout).
- Type hints on every function signature; use `X | Y` over `Union[X, Y]`.
- **No bare `except`**. Catch specific exceptions; let unknown errors propagate.
- Never use `print()` — use `backend/app/utils/logger.py`.
- Keep functions short (≤ 30 lines is a signal to refactor).

```python
# ✅ Good
async def collect(self, config: dict) -> list[RawArticle]:
    response = await self.client.get(config["url"])
    response.raise_for_status()
    return self._parse(response.json())

# ❌ Bad — swallows errors, unclear types
async def collect(self, config):
    try:
        r = await self.client.get(config.get("url"))
        return self._parse(r.json())
    except Exception:
        return []
```

### TypeScript (Frontend)
- Strict TypeScript. No `any`.
- React functional components only. No class components.
- Keep components focused — if props list > 6, split the component.
- `frontend/src/lib/api.ts` is the only place for API calls.

---

## Architecture Rules

### Plugin Pattern (Core Layers)
All Collector / Renderer / Sink implementations **must** extend the base class and use the registry decorator. Never modify the base class interface.

```python
@register("my_source")
class MyCollector(BaseCollector):
    @property
    def name(self) -> str: return "my_source"
    ...
```

### Database
- All schema changes via **Alembic migrations** — never alter tables directly.
- Follow the naming and field conventions in TEC.md § 3.
- New optional columns should have `DEFAULT` values to avoid migration pain.

### API
- Prefix: `/api/v1/`
- Always use Pydantic schemas in `backend/app/schemas/` for request/response.
- Enums (category, depth, time_period) must match TEC.md § 5.1 constants.
- Changes to an API response shape require updating the corresponding frontend `api.ts` type.

---

## What NOT to Do

- ❌ Don't run destructive DB commands (`DROP`, `TRUNCATE`) without explicit instruction.
- ❌ Don't add heavy dependencies for simple tasks (e.g. `boto3` just for an HTTP PUT).
- ❌ Don't bypass the shared cache layer (Redis) and add per-user collection logic.
- ❌ Don't hardcode model names or API keys — always read from `config.py` / env vars.
