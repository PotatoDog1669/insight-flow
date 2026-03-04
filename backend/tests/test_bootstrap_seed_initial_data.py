from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
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

