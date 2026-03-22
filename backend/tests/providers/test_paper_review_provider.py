from __future__ import annotations

import pytest

from app.providers.paper_review import LLMPaperReviewProvider


@pytest.mark.asyncio
async def test_llm_paper_review_provider_builds_prompt_from_candidate_papers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_prompt: dict[str, str] = {}

    async def _fake_llm(prompt: str, config: dict | None = None) -> dict:
        captured_prompt["text"] = prompt
        return {
            "digest_title": "2026-03-21 论文推荐",
            "digest_summary": "本期重点是具身智能与 world model 的方法收敛速度明显加快。",
            "papers": [
                {
                    "paper_identity": "2603.12345",
                    "title": "World Model Policy",
                    "recommendation": "必读",
                    "one_line_judgment": "把 world model 和 policy 学习真正绑到了一起。",
                    "core_problem": "现有方法推理成本高。",
                    "core_method": "用分层 world model 降低规划开销。",
                    "key_result": "在多个控制任务上超过 baseline。",
                    "why_it_matters": "更接近可复用范式。",
                    "reading_advice": "先读方法再看实验。",
                    "note_candidate": True,
                }
            ],
        }

    monkeypatch.setattr("app.providers.paper_review.run_llm_json", _fake_llm)
    provider = LLMPaperReviewProvider()
    tail_marker = "TAIL_MARKER_SHOULD_NOT_APPEAR"

    await provider.run(
        payload={
            "title": "2026-03-21 论文推荐",
            "papers": [
                {
                    "paper_identity": "2603.12345",
                    "title": "World Model Policy",
                    "summary": "A paper about world model policy learning.",
                    "detail": ("detail " * 300) + tail_marker,
                    "authors": ["Alice", "Bob"],
                    "affiliations": ["Example Lab"],
                    "links": ["https://arxiv.org/abs/2603.12345"],
                }
            ],
        },
        config={"model": "gpt-4o-mini", "api_key": "sk-demo"},
    )

    assert "World Model Policy" in captured_prompt["text"]
    assert "2603.12345" in captured_prompt["text"]
    assert tail_marker not in captured_prompt["text"]


@pytest.mark.asyncio
async def test_llm_paper_review_provider_normalizes_digest_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_llm(prompt: str, config: dict | None = None) -> dict:
        return {
            "digest_title": " GUI 智能体的评测、安全与长程记忆 ",
            "digest_summary": "  本期重点是 world model 和 embodied agent 两条线都开始从 demo 走向更可复用框架。  ",
            "editorial_observations": ["方向开始收敛", "", "工程化比单点指标更重要"],
            "papers": [
                {
                    "paper_identity": " 2603.12345 ",
                    "paper_slug": " world-model-policy ",
                    "title": " World Model Policy ",
                    "topic_label": " World Model ",
                    "authors": ["Alice", "Alice", "Bob"],
                    "affiliations": "Example Lab",
                    "links": ["https://arxiv.org/abs/2603.12345", "https://arxiv.org/abs/2603.12345"],
                    "figure": " https://example.com/figure.png ",
                    "recommendation": "强推",
                    "one_line_judgment": " 这篇终于把 world model 说清楚了。 ",
                    "core_problem": " 现有方法成本高。 ",
                    "core_method": " 用分层 world model 降低规划开销。 ",
                    "key_result": " 多任务超过 baseline。 ",
                    "why_it_matters": " 更接近可复用范式。 ",
                    "reading_advice": " 先看方法再看实验。 ",
                    "note_candidate": "yes",
                }
            ],
            "excluded_papers": [{"paper_identity": "skip-1", "title": "Irrelevant Paper", "reason": "不相关"}],
        }

    monkeypatch.setattr("app.providers.paper_review.run_llm_json", _fake_llm)
    provider = LLMPaperReviewProvider()
    output = await provider.run(
        payload={
            "title": "2026-03-21 论文推荐",
            "papers": [{"paper_identity": "2603.12345", "title": "World Model Policy"}],
        },
        config={"model": "gpt-4o-mini", "api_key": "sk-demo"},
    )

    assert output["digest_title"] == "2026-03-21 论文推荐"
    assert output["digest_summary"].startswith("本期重点是 world model")
    assert output["editorial_observations"] == ["方向开始收敛", "工程化比单点指标更重要"]
    assert output["papers"][0]["paper_identity"] == "2603.12345"
    assert output["papers"][0]["paper_slug"] == "world-model-policy"
    assert output["papers"][0]["topic_label"] == "World Model"
    assert output["papers"][0]["authors"] == ["Alice", "Bob"]
    assert output["papers"][0]["affiliations"] == ["Example Lab"]
    assert output["papers"][0]["links"] == ["https://arxiv.org/abs/2603.12345"]
    assert output["papers"][0]["figure"] == "https://example.com/figure.png"
    assert output["papers"][0]["recommendation"] == "必读"
    assert output["papers"][0]["note_candidate"] is True
    assert output["excluded_papers"] == [{"paper_identity": "skip-1", "title": "Irrelevant Paper", "reason": "不相关"}]


@pytest.mark.asyncio
async def test_llm_paper_review_provider_keeps_detailed_digest_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detailed_summary = " ".join(["本期的共同主题不是单点能力突破，而是 GUI agent 的评测、安全、长程记忆与奖励建模开始一起向基础设施化收敛。"] * 12)

    async def _fake_llm(prompt: str, config: dict | None = None) -> dict:
        return {
            "digest_title": "任意标题都会被规范化",
            "digest_summary": detailed_summary,
            "papers": [
                {
                    "paper_identity": "2603.12345",
                    "title": "World Model Policy",
                    "recommendation": "必读",
                    "one_line_judgment": "把 world model 和 policy 学习真正绑到了一起。",
                    "core_problem": "现有方法推理成本高。",
                    "core_method": "用分层 world model 降低规划开销。",
                    "key_result": "在多个控制任务上超过 baseline。",
                    "why_it_matters": "更接近可复用范式。",
                    "reading_advice": "先读方法再看实验。",
                    "note_candidate": True,
                }
            ],
        }

    monkeypatch.setattr("app.providers.paper_review.run_llm_json", _fake_llm)
    provider = LLMPaperReviewProvider()
    output = await provider.run(
        payload={
            "title": "2026-03-21 论文推荐",
            "papers": [{"paper_identity": "2603.12345", "title": "World Model Policy"}],
        },
        config={"model": "gpt-4o-mini", "api_key": "sk-demo"},
    )

    assert output["digest_title"] == "2026-03-21 论文推荐"
    assert output["digest_summary"] == detailed_summary


@pytest.mark.asyncio
async def test_llm_paper_review_provider_keeps_dense_multisentence_digest_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    long_method = (
        "先做任务诊断，明确把长程失败归因到任务内记忆而不是感知误差；"
        "再把交互序列压缩为具因果关联的状态锚点，用于子目标检索和带归因决策；"
        "最后通过 Anchored State Memory 把长流程中真正需要回看的信息保留下来。"
    )
    long_result = (
        "基准覆盖 1069 个任务和 34473 个交互步骤；"
        "在 12 个开源与闭源 GUI 智能体上，相比完整回放和摘要式 baseline，"
        "ASM 带来 5%-30.16% 的 TCR 提升，以及 4.93%-24.66% 的 AMS 提升。"
    )
    long_why = (
        "这篇工作的价值不只是又给 memory 加了一个模块，"
        "而是把长程 GUI agent 的核心瓶颈从笼统的‘能力不够’重新收束到任务内记忆架构。"
    )
    long_advice = (
        "建议先看作者如何定义 failure mode，再看 ASM 的状态锚点设计；"
        "如果你在做长程 agent，这篇更值得作为架构参考而不是单纯 benchmark 结果。"
    )

    async def _fake_llm(prompt: str, config: dict | None = None) -> dict:
        return {
            "digest_title": "2026-03-21 论文推荐",
            "digest_summary": "本期重点是 GUI agent 的评测、安全与长程记忆开始一起走向更系统的基础设施建设。",
            "papers": [
                {
                    "paper_identity": "2603.18429",
                    "title": "AndroTMem",
                    "recommendation": "必读",
                    "one_line_judgment": "长程 GUI agent 的记忆短板终于被说清楚了。",
                    "core_problem": "现有代理在跨步骤依赖任务里容易失效。",
                    "core_method": long_method,
                    "key_result": long_result,
                    "why_it_matters": long_why,
                    "reading_advice": long_advice,
                    "note_candidate": True,
                }
            ],
        }

    monkeypatch.setattr("app.providers.paper_review.run_llm_json", _fake_llm)
    provider = LLMPaperReviewProvider()
    output = await provider.run(
        payload={
            "title": "2026-03-21 论文推荐",
            "papers": [{"paper_identity": "2603.18429", "title": "AndroTMem"}],
        },
        config={"model": "gpt-4o-mini", "api_key": "sk-demo"},
    )

    paper = output["papers"][0]
    assert "状态锚点" in paper["core_method"]
    assert "34473 个交互步骤" in paper["key_result"]
    assert "任务内记忆架构" in paper["why_it_matters"]
    assert "架构参考" in paper["reading_advice"]


@pytest.mark.asyncio
async def test_llm_paper_review_provider_rejects_incomplete_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_llm(prompt: str, config: dict | None = None) -> dict:
        return {"digest_title": "论文推荐", "papers": []}

    monkeypatch.setattr("app.providers.paper_review.run_llm_json", _fake_llm)
    provider = LLMPaperReviewProvider()

    with pytest.raises(ValueError, match="Missing digest_summary"):
        await provider.run(
            payload={
                "title": "2026-03-21 论文推荐",
                "papers": [{"paper_identity": "2603.12345", "title": "World Model Policy"}],
            },
            config={"model": "gpt-4o-mini", "api_key": "sk-demo"},
        )
