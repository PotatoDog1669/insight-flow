<div align="center">
  <img src="docs/banner.svg" alt="Insight Flow banner" />
</div>

---

<div align="center">
  <p>
    <a href="https://insight-flow.potatodog.cc/en/introduction">
      <img src="https://img.shields.io/badge/docs-home-0EA5E9?style=flat-square" alt="Documentation">
    </a>
    <a href="backend/">
      <img src="https://img.shields.io/badge/backend-FastAPI-009688?style=flat-square" alt="Backend: FastAPI">
    </a>
    <a href="frontend/">
      <img src="https://img.shields.io/badge/frontend-Next.js-111111?style=flat-square" alt="Frontend: Next.js">
    </a>
    <a href="https://insight-flow.potatodog.cc/en/quickstart">
      <img src="https://img.shields.io/badge/python-3.12%2B-3776AB?style=flat-square" alt="Python 3.12+">
    </a>
    <a href="https://insight-flow.potatodog.cc/en/introduction">
      <img src="https://img.shields.io/badge/status-active-65A30D?style=flat-square" alt="Status: active">
    </a>
  </p>
  <p>
    <a href="README.en.md">English</a>
    |
    <a href="README.md">简体中文</a>
  </p>
</div>

Insight Flow is a workspace for research monitoring, continuous intelligence collection, and structured knowledge capture.

You can use Insight Flow in two ways: configure monitors manually, or tell the Agent what topics, entities, or directions you want to track and let it generate an editable monitor draft. After that, the system continuously handles collection, filtering, summarization, report generation, and publishing based on your configured sources, models, and destinations.

The current project already covers the full workflow: on the source side it supports RSS, website scraping, GitHub Trending, Hugging Face, plus academic and community sources such as OpenAlex, PubMed, Europe PMC, Reddit, and X. On the task side it supports scheduled monitors that generate daily digests, weekly digests, research reports, and paper recommendations. On the model side it can use OpenAI-compatible LLM endpoints or Codex, with AI routing for different processing stages. On the output side it can publish results to Notion, Obsidian, or RSS, while preserving run history, report archives, and manual republishing flows.

## Demo

insight-flow.mp4

## Requirements

- Python 3.12+
- Node.js 18+
- Docker / Docker Compose

## Quick Start

For first-time setup:

```bash
cp .env.example .env
make bootstrap
make doctor
```

For day-to-day local development:

```bash
make dev-local
```

Notes:

- `make bootstrap`: run this the first time, or again if dependencies or the virtual environment become inconsistent
- `make doctor`: environment self-check; recommended for first-time setup and whenever you suspect local issues
- `make dev-local`: the standard command for starting the local development environment

After startup, visit:

- Frontend: `http://localhost:3018`
- Backend API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

If you need browser-based collection, also run:

```bash
make backend-browser-deps
```

On first backend startup, the system automatically initializes the default user and syncs the preset sources from `backend/app/collectors/source_presets.yaml` into the database.

## Local Docs Preview

The Mint configuration file lives at `docs/docs.json`.

```bash
cd docs
npx mint dev
```

If you need the full backend OpenAPI docs, start the backend separately and open `http://localhost:8000/docs`.
