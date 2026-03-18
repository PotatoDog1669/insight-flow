# Contributing to Insight Flow

Thanks for your interest in contributing to Insight Flow.

## Before You Start

- Read [README.md](README.md) for the repository overview and local setup
- Read [AGENTS.md](AGENTS.md) for the repository coding standards
- Read the development docs at https://insight-flow.potatodog.cc/zh/development/contributing
- Keep API contracts, database schema, and frontend types in sync when making changes

## Development Workflow

1. Fork the repository or create a working branch from the default branch.
2. Set up the local environment.
3. Make focused changes with clear commit messages.
4. Run the relevant checks before opening a pull request.
5. Describe the user-facing impact and verification steps in the pull request.

## Local Setup

```bash
cp .env.example .env
make bootstrap
make doctor
make dev-local
```

If you need browser collection support, also run:

```bash
make backend-browser-deps
```

## Verification

Run the narrowest checks that cover your change first. Before opening a pull
request, run the broad checks that apply to your work.

Common commands:

```bash
make test-all
make test-backend
make frontend
make backend
```

## Contribution Guidelines

- Keep changes concise and avoid unrelated refactors
- Use Alembic migrations for schema changes
- Keep frontend API calls inside `frontend/src/lib/api.ts`
- Use the existing plugin and registry patterns for collectors, renderers, and sinks
- Update docs when changing behavior, routes, or user-facing workflows

## Pull Request Checklist

- The change is scoped to one clear goal
- Tests or validation steps were run and documented
- New environment variables, routes, or migrations are described
- Related docs were updated when needed

## Need Help?

If you want to discuss a change before implementing it, open an issue or start
with a draft pull request so maintainers can give feedback early.
