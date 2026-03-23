from __future__ import annotations

import pytest

from app.providers.paper_review import CodexPaperReviewProvider, LLMPaperReviewProvider


@pytest.mark.asyncio
async def test_llm_paper_review_provider_uses_llm_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"llm": 0}

    async def _fake_llm(prompt: str, config: dict | None = None) -> dict:
        calls["llm"] += 1
        return {
            "digest_title": "LLM Paper Digest",
            "digest_summary": "本期最值得看的工作开始把系统能力和方法设计一起推进。",
            "papers": [
                {
                    "paper_identity": "2603.12345",
                    "title": "World Model Policy",
                    "recommendation": "必读",
                    "core_method": "方法扎实。",
                    "baselines": "对比设置清晰。",
                    "why_it_matters": "有迁移价值。",
                    "note_candidate": True,
                }
            ],
        }

    monkeypatch.setattr("app.providers.paper_review.run_llm_json", _fake_llm)
    provider = LLMPaperReviewProvider()
    output = await provider.run(
        payload={"title": "Paper Digest", "papers": [{"paper_identity": "2603.12345", "title": "World Model Policy"}]},
        config={"model": "gpt-4o-mini", "api_key": "sk-demo"},
    )

    assert output["digest_title"] == "Paper Digest"
    assert calls["llm"] == 1


@pytest.mark.asyncio
async def test_codex_paper_review_provider_uses_codex_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"codex": 0}

    async def _fake_codex(prompt: str, config: dict | None = None) -> dict:
        calls["codex"] += 1
        return {
            "digest_title": "Codex Paper Digest",
            "digest_summary": "本期更值得关注方法能否沉淀成可复用框架。",
            "papers": [
                {
                    "paper_identity": "2603.12345",
                    "title": "World Model Policy",
                    "recommendation": "值得看",
                    "core_method": "方法扎实。",
                    "baselines": "对比设置清晰。",
                    "why_it_matters": "有迁移价值。",
                    "note_candidate": False,
                }
            ],
        }

    monkeypatch.setattr("app.providers.paper_review.run_codex_json", _fake_codex)
    provider = CodexPaperReviewProvider()
    output = await provider.run(
        payload={"title": "Paper Digest", "papers": [{"paper_identity": "2603.12345", "title": "World Model Policy"}]},
        config={"model": "gpt-5-codex", "api_key": "sk-demo"},
    )

    assert output["digest_title"] == "Paper Digest"
    assert output["papers"][0]["recommendation"] == "值得看"
    assert calls["codex"] == 1
