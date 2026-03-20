from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.bootstrap import DEFAULT_USER_ID, _source_uuid, seed_initial_data
from app.models import Source
from app.models.database import Base
from app.models.subscription import UserSubscription


def _write_presets(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            """
            sources:
              - key: deepseek
                company: DeepSeek
                urls: ["https://api-docs.deepseek.com"]
                strategy: github_plus_docs
                priority: p0
                enabled: true
                category: blog
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _write_arxiv_preset(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            """
            sources:
              - key: arxiv
                company: arXiv
                urls: ["https://arxiv.org/list/cs/recent"]
                rss_url: "https://export.arxiv.org/api/query"
                strategy: rss_then_article_fulltext
                priority: p0
                enabled: true
                category: academic
                collect_config:
                  arxiv_api: true
                  keywords: ["reasoning", "agent"]
                  categories: ["cs.AI", "cs.LG"]
                  max_results: 25
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _write_academic_api_presets(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            """
            sources:
              - key: openalex
                company: OpenAlex
                urls: ["https://api.openalex.org/works"]
                strategy: openalex_api
                priority: p0
                enabled: true
                category: academic
                collect_config:
                  base_url: "https://api.openalex.org/works"
                  keywords: ["reasoning", "agent"]
                  max_results: 20
                  mailto: "research@example.com"
                  supports_time_window: true
                  auth_mode: optional_api_key
              - key: europe_pmc
                company: Europe PMC
                urls: ["https://www.ebi.ac.uk/europepmc/webservices/rest/search"]
                strategy: europe_pmc_api
                priority: p0
                enabled: true
                category: academic
                collect_config:
                  base_url: "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
                  keywords: ["reasoning", "agent"]
                  max_results: 20
                  supports_time_window: true
                  auth_mode: none
              - key: pubmed
                company: PubMed
                urls: ["https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"]
                strategy: pubmed_api
                priority: p0
                enabled: true
                category: academic
                collect_config:
                  base_url: "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
                  keywords: ["reasoning", "agent"]
                  max_results: 20
                  api_key: ""
                  tool: "lexdeepresearch"
                  email: "research@example.com"
                  supports_time_window: true
                  auth_mode: optional_api_key
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _write_mixed_priority_presets(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            """
            sources:
              - key: deepseek
                company: DeepSeek
                urls: ["https://www.deepseek.com/news"]
                strategy: site_profile_scraper
                priority: p0
                enabled: true
                category: blog
              - key: minimax
                company: MiniMax
                urls: ["https://minimax.io/news"]
                strategy: site_profile_scraper
                priority: p1
                enabled: false
                category: blog
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _write_upsert_presets(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            """
            sources:
              - key: deepseek
                company: DeepSeek New
                urls: ["https://www.deepseek.com/news"]
                strategy: site_profile_scraper
                priority: p0
                enabled: false
                category: blog
              - key: arxiv
                company: arXiv
                urls: ["https://arxiv.org/list/cs/recent"]
                rss_url: "https://export.arxiv.org/api/query"
                strategy: rss_then_article_fulltext
                priority: p1
                enabled: true
                category: academic
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _write_x_preset(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            """
            sources:
              - key: x_social
                company: X
                urls: ["https://x.com"]
                strategy: twitter_snaplytics
                priority: p1
                enabled: true
                category: social
                collect_config:
                  usernames:
                    - OpenAI
                    - AnthropicAI
                    - Google
                    - karpathy
                    - cursor_ai
                    - Alibaba_Qwen
                    - perplexity_ai
                    - GoogleDeepMind
                  max_items: 30
                  max_pages: 1
                  include_retweets: false
                  include_pinned: true
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _write_reddit_preset(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            """
            sources:
              - key: reddit_social
                company: Reddit
                urls: ["https://www.reddit.com"]
                rss_url: "https://www.reddit.com/search.rss?q=subreddit%3ALocalLLaMA+OR+subreddit%3Asingularity+OR+subreddit%3AOpenAI&sort=new"
                strategy: rss_then_feed_summary
                priority: p1
                enabled: true
                category: social
                collect_config:
                  subreddits:
                    - LocalLLaMA
                    - singularity
                    - OpenAI
                  max_items: 30
                  fetch_detail: false
                  user_agent: LexDeepResearchBot/0.1
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def test_shipped_x_preset_includes_default_watchlist() -> None:
    presets_path = Path(__file__).resolve().parents[1] / "app" / "collectors" / "source_presets.yaml"
    payload = yaml.safe_load(presets_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)

    sources = payload.get("sources", [])
    assert isinstance(sources, list)
    x_source = next(source for source in sources if isinstance(source, dict) and source.get("key") == "x_social")
    config = x_source.get("collect_config")
    assert isinstance(config, dict)
    assert config.get("usernames") == [
        "OpenAI",
        "AnthropicAI",
        "Google",
        "karpathy",
        "cursor_ai",
        "Alibaba_Qwen",
        "perplexity_ai",
        "GoogleDeepMind",
    ]


def test_shipped_reddit_preset_includes_default_subreddits() -> None:
    presets_path = Path(__file__).resolve().parents[1] / "app" / "collectors" / "source_presets.yaml"
    payload = yaml.safe_load(presets_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)

    sources = payload.get("sources", [])
    assert isinstance(sources, list)
    reddit_source = next(source for source in sources if isinstance(source, dict) and source.get("key") == "reddit_social")
    config = reddit_source.get("collect_config")
    assert isinstance(config, dict)
    assert config.get("subreddits") == ["LocalLLaMA", "singularity", "OpenAI"]


@pytest.mark.asyncio
async def test_seed_initial_data_sets_deepseek_category_from_preset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "seed-empty.db"
    presets_path = tmp_path / "source_presets.yaml"
    profiles_dir = tmp_path / "site_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    _write_presets(presets_path)

    monkeypatch.setattr("app.bootstrap.PRESETS_PATH", presets_path)
    monkeypatch.setattr("app.bootstrap.SITE_PROFILE_DIR", profiles_dir)

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            await seed_initial_data(session)

        async with session_factory() as session:
            deepseek = await session.get(Source, _source_uuid("deepseek"))
            assert deepseek is not None
            assert deepseek.category == "blog"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_seed_initial_data_imports_all_presets_and_preserves_enabled_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "seed-all.db"
    presets_path = tmp_path / "source_presets.yaml"
    profiles_dir = tmp_path / "site_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    _write_mixed_priority_presets(presets_path)

    monkeypatch.setattr("app.bootstrap.PRESETS_PATH", presets_path)
    monkeypatch.setattr("app.bootstrap.SITE_PROFILE_DIR", profiles_dir)

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            await seed_initial_data(session)

        async with session_factory() as session:
            deepseek = await session.get(Source, _source_uuid("deepseek"))
            minimax = await session.get(Source, _source_uuid("minimax"))
            assert deepseek is not None
            assert minimax is not None
            assert deepseek.enabled is True
            assert minimax.enabled is False
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_seed_initial_data_upserts_presets_even_when_database_is_not_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "seed-upsert.db"
    presets_path = tmp_path / "source_presets.yaml"
    profiles_dir = tmp_path / "site_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    _write_upsert_presets(presets_path)

    monkeypatch.setattr("app.bootstrap.PRESETS_PATH", presets_path)
    monkeypatch.setattr("app.bootstrap.SITE_PROFILE_DIR", profiles_dir)

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            session.add(
                Source(
                    id=_source_uuid("deepseek"),
                    name="DeepSeek Old",
                    category="open_source",
                    collect_method="blog_scraper",
                    config={"site_key": "deepseek_old"},
                    enabled=True,
                )
            )
            await session.commit()

        async with session_factory() as session:
            await seed_initial_data(session)

        async with session_factory() as session:
            deepseek = await session.get(Source, _source_uuid("deepseek"))
            arxiv = await session.get(Source, _source_uuid("arxiv"))
            assert deepseek is not None
            assert arxiv is not None
            assert deepseek.name == "DeepSeek New"
            assert deepseek.category == "blog"
            assert deepseek.enabled is False
            assert arxiv.collect_method == "rss"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_seed_initial_data_does_not_duplicate_subscriptions_on_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "seed-subscriptions.db"
    presets_path = tmp_path / "source_presets.yaml"
    profiles_dir = tmp_path / "site_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    _write_presets(presets_path)

    monkeypatch.setattr("app.bootstrap.PRESETS_PATH", presets_path)
    monkeypatch.setattr("app.bootstrap.SITE_PROFILE_DIR", profiles_dir)

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            await seed_initial_data(session)
            await seed_initial_data(session)

        async with session_factory() as session:
            rows = await session.execute(
                select(UserSubscription.source_id).where(UserSubscription.user_id == DEFAULT_USER_ID)
            )
            source_ids = rows.scalars().all()
            assert len(source_ids) == len(set(source_ids))
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_seed_initial_data_migrates_existing_deepseek_category_to_blog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "seed-existing.db"
    presets_path = tmp_path / "source_presets.yaml"
    profiles_dir = tmp_path / "site_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    _write_presets(presets_path)

    monkeypatch.setattr("app.bootstrap.PRESETS_PATH", presets_path)
    monkeypatch.setattr("app.bootstrap.SITE_PROFILE_DIR", profiles_dir)

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            session.add(
                Source(
                    id=_source_uuid("deepseek"),
                    name="DeepSeek",
                    category="open_source",
                    collect_method="blog_scraper",
                    config={},
                    enabled=True,
                )
            )
            await session.commit()

        async with session_factory() as session:
            await seed_initial_data(session)

        async with session_factory() as session:
            deepseek = await session.get(Source, _source_uuid("deepseek"))
            assert deepseek is not None
            assert deepseek.category == "blog"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_seed_initial_data_merges_rss_collect_config_from_preset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "seed-arxiv.db"
    presets_path = tmp_path / "source_presets.yaml"
    profiles_dir = tmp_path / "site_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    _write_arxiv_preset(presets_path)

    monkeypatch.setattr("app.bootstrap.PRESETS_PATH", presets_path)
    monkeypatch.setattr("app.bootstrap.SITE_PROFILE_DIR", profiles_dir)

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            await seed_initial_data(session)

        async with session_factory() as session:
            arxiv = await session.get(Source, _source_uuid("arxiv"))
            assert arxiv is not None
            assert arxiv.collect_method == "rss"
            assert arxiv.category == "academic"
            assert arxiv.config.get("feed_url") == "https://export.arxiv.org/api/query"
            assert arxiv.config.get("arxiv_api") is True
            assert arxiv.config.get("keywords") == ["reasoning", "agent"]
            assert arxiv.config.get("categories") == ["cs.AI", "cs.LG"]
            assert arxiv.config.get("max_results") == 25
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_seed_initial_data_imports_academic_api_presets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "seed-academic-api.db"
    presets_path = tmp_path / "source_presets.yaml"
    profiles_dir = tmp_path / "site_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    _write_academic_api_presets(presets_path)

    monkeypatch.setattr("app.bootstrap.PRESETS_PATH", presets_path)
    monkeypatch.setattr("app.bootstrap.SITE_PROFILE_DIR", profiles_dir)

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            await seed_initial_data(session)

        async with session_factory() as session:
            openalex = await session.get(Source, _source_uuid("openalex"))
            europe_pmc = await session.get(Source, _source_uuid("europe_pmc"))
            pubmed = await session.get(Source, _source_uuid("pubmed"))

            assert openalex is not None
            assert openalex.category == "academic"
            assert openalex.collect_method == "openalex"
            assert openalex.config.get("base_url") == "https://api.openalex.org/works"
            assert openalex.config.get("keywords") == ["reasoning", "agent"]
            assert openalex.config.get("max_results") == 20
            assert openalex.config.get("mailto") == "research@example.com"
            assert openalex.config.get("supports_time_window") is True
            assert openalex.config.get("auth_mode") == "optional_api_key"

            assert europe_pmc is not None
            assert europe_pmc.category == "academic"
            assert europe_pmc.collect_method == "europe_pmc"
            assert europe_pmc.config.get("base_url") == "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
            assert europe_pmc.config.get("keywords") == ["reasoning", "agent"]
            assert europe_pmc.config.get("max_results") == 20
            assert europe_pmc.config.get("supports_time_window") is True
            assert europe_pmc.config.get("auth_mode") == "none"

            assert pubmed is not None
            assert pubmed.category == "academic"
            assert pubmed.collect_method == "pubmed"
            assert pubmed.config.get("base_url") == "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
            assert pubmed.config.get("keywords") == ["reasoning", "agent"]
            assert pubmed.config.get("max_results") == 20
            assert pubmed.config.get("api_key") == ""
            assert pubmed.config.get("tool") == "lexdeepresearch"
            assert pubmed.config.get("email") == "research@example.com"
            assert pubmed.config.get("supports_time_window") is True
            assert pubmed.config.get("auth_mode") == "optional_api_key"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_seed_initial_data_merges_existing_twitter_usernames_with_preset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "seed-x.db"
    presets_path = tmp_path / "source_presets.yaml"
    profiles_dir = tmp_path / "site_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    _write_x_preset(presets_path)

    monkeypatch.setattr("app.bootstrap.PRESETS_PATH", presets_path)
    monkeypatch.setattr("app.bootstrap.SITE_PROFILE_DIR", profiles_dir)

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            session.add(
                Source(
                    id=_source_uuid("x_social"),
                    name="X",
                    category="social",
                    collect_method="twitter_snaplytics",
                    config={
                        "usernames": ["karpathy", "Google"],
                        "max_items": 50,
                        "max_pages": 2,
                        "include_retweets": False,
                        "include_pinned": True,
                    },
                    enabled=True,
                )
            )
            await session.commit()

        async with session_factory() as session:
            await seed_initial_data(session)

        async with session_factory() as session:
            x_source = await session.get(Source, _source_uuid("x_social"))
            assert x_source is not None
            assert x_source.collect_method == "twitter_snaplytics"
            assert x_source.config.get("usernames") == [
                "karpathy",
                "Google",
                "OpenAI",
                "AnthropicAI",
                "cursor_ai",
                "Alibaba_Qwen",
                "perplexity_ai",
                "GoogleDeepMind",
            ]
            assert x_source.config.get("include_retweets") is False
            assert x_source.config.get("include_pinned") is True
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_seed_initial_data_merges_existing_reddit_subreddits_with_preset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "seed-reddit.db"
    presets_path = tmp_path / "source_presets.yaml"
    profiles_dir = tmp_path / "site_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    _write_reddit_preset(presets_path)

    monkeypatch.setattr("app.bootstrap.PRESETS_PATH", presets_path)
    monkeypatch.setattr("app.bootstrap.SITE_PROFILE_DIR", profiles_dir)

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            session.add(
                Source(
                    id=_source_uuid("reddit_social"),
                    name="Reddit",
                    category="social",
                    collect_method="rss",
                    config={
                        "subreddits": ["r/LocalLLaMA", "MachineLearning", "openai"],
                        "max_items": 40,
                        "fetch_detail": False,
                    },
                    enabled=True,
                )
            )
            await session.commit()

        async with session_factory() as session:
            await seed_initial_data(session)

        async with session_factory() as session:
            reddit_source = await session.get(Source, _source_uuid("reddit_social"))
            assert reddit_source is not None
            assert reddit_source.collect_method == "rss"
            assert reddit_source.config.get("subreddits") == [
                "LocalLLaMA",
                "MachineLearning",
                "OpenAI",
                "singularity",
            ]
            assert reddit_source.config.get("max_items") == 30
            assert reddit_source.config.get("fetch_detail") is False
    finally:
        await engine.dispose()
