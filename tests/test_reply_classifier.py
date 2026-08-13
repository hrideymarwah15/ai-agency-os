"""Reply classification behavior tests."""

import pytest

from backend.services.outreach.reply_classifier import (
    ObjectionType,
    ReplyClassification,
    ReplyClassifier,
)


@pytest.mark.anyio
async def test_llm_high_confidence_auto_handles(tmp_path):
    config = tmp_path / "outreach.yaml"
    config.write_text("objection_responses: {price: 'A phased approach can help.'}\n")

    async def llm(_messages):
        return '{"classification":"interested","confidence":0.91}'

    result = await ReplyClassifier(llm_call=llm, config_path=config).classify("Yes, tell me more")
    assert result.classification == ReplyClassification.INTERESTED
    assert result.escalate is False
    assert result.source == "llm"


@pytest.mark.anyio
async def test_low_confidence_escalates():
    async def llm(_messages):
        return '{"classification":"question","confidence":0.55}'

    result = await ReplyClassifier(llm_call=llm).classify("Maybe?")
    assert result.escalate is True


@pytest.mark.anyio
async def test_provider_failure_uses_deterministic_fallback():
    async def llm(_messages):
        raise RuntimeError("provider unavailable")

    result = await ReplyClassifier(llm_call=llm).classify("Please unsubscribe me")
    assert result.classification == ReplyClassification.UNSUBSCRIBE
    assert result.confidence >= 0.8
    assert result.escalate is False


@pytest.mark.anyio
async def test_objection_uses_yaml_library(tmp_path):
    config = tmp_path / "outreach.yaml"
    config.write_text("objection_responses: {price: 'Budget response for {{ company }}'}\n")
    result = await ReplyClassifier(config_path=config).classify(
        "The price is too expensive", {"company": "Acme"}
    )
    assert result.classification == ReplyClassification.OBJECTION
    assert result.objection_type == ObjectionType.PRICE
    assert result.suggested_response == "Budget response for Acme"
