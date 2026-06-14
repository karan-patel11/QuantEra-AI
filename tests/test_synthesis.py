from __future__ import annotations

from quantera.models_fundamentals import VerdictLevel
from quantera.models_news import OverallTone
from quantera.models_technicals import VerdictLevel as TechnicalVerdictLevel
from quantera.synthesis.synthesize import detect_disagreements, generate_narrative
from tests.conftest import MockLLMClient
from tests.phase4_helpers import (
    fundamentals_result,
    news_result,
    synthesis_result,
    technicals_result,
)


def test_disagreement_rules_find_expected_conflicts():
    disagreements = detect_disagreements(
        fundamentals_result(valuation_level=VerdictLevel.STRONG),
        technicals_result(trend_level=TechnicalVerdictLevel.ABOVE),
        news_result(tone=OverallTone.NEGATIVE),
    )

    descriptions = {item.description for item in disagreements}
    assert "Fundamentals lean strong while recent news tone is negative." in descriptions
    assert (
        "The long-term price trend is above its 200-day SMA while recent news tone is negative."
        in descriptions
    )
    assert any("fundamentals STRONG=1" in item.basis for item in disagreements)
    assert any("price_vs_sma_200=ABOVE" in item.basis for item in disagreements)


def test_disagreement_rules_skip_aligned_lenses():
    disagreements = detect_disagreements(
        fundamentals_result(valuation_level=VerdictLevel.STRONG),
        technicals_result(trend_level=TechnicalVerdictLevel.ABOVE),
        news_result(tone=OverallTone.POSITIVE),
    )

    assert disagreements == []


def test_valuation_growth_tension_is_detected_inside_fundamentals():
    disagreements = detect_disagreements(
        fundamentals_result(
            valuation_level=VerdictLevel.WEAK,
            growth_level=VerdictLevel.STRONG,
        ),
        None,
        None,
    )

    assert len(disagreements) == 1
    assert disagreements[0].lens_a == "fundamentals.valuation"
    assert "valuation verdicts: pe_ratio=WEAK" in disagreements[0].basis
    assert "growth verdicts: revenue_growth_yoy=STRONG" in disagreements[0].basis


def test_synthesis_narrative_guardrail_falls_back_on_unknown_source_and_number():
    result = synthesis_result()

    def bad_llm(system, user, max_tokens, temperature):
        return (
            "AAPL looks better by 999% according to "
            "[Unknown Source](https://example.invalid/story). "
            "Research/education only, not financial advice."
        )

    output = generate_narrative(result, llm_client=MockLLMClient(bad_llm))

    assert "999" not in output
    assert "example.invalid" not in output
    assert "Research/education only, not financial advice." in output
