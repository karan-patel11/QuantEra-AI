from __future__ import annotations

from quantera.lenses.fundamentals.lens import FundamentalsLens
from quantera.lenses.fundamentals import explain
from tests.conftest import MockLLMClient, sample_financials


class MockProvider:
    def __init__(self, financials):
        self.financials = financials

    def get_financials(self, ticker: str):
        return self.financials


def fundamentals_result(fetched_at):
    return FundamentalsLens(MockProvider(sample_financials(fetched_at))).analyze(
        "mock",
        with_explanation=False,
    )


def test_clean_llm_response_passes_through(fetched_at):
    result = fundamentals_result(fetched_at)
    clean = (
        "MOCK fundamentals summary for research/education only, not financial advice. "
        "Price / Earnings is 2.5 with a STRONG verdict."
    )
    llm_client = MockLLMClient(lambda system, user, max_tokens, temperature: clean)

    assert explain.generate_explanation(result, llm_client=llm_client) == clean
    assert llm_client.calls[0]["temperature"] == 0.0


def test_hallucinated_number_triggers_template_fallback(fetched_at):
    result = fundamentals_result(fetched_at)
    hallucinated = (
        "MOCK fundamentals summary for research/education only, not financial advice. "
        "Price / Earnings is 2.5, and a fabricated figure is 999."
    )
    llm_client = MockLLMClient(lambda system, user, max_tokens, temperature: hallucinated)

    output = explain.generate_explanation(result, llm_client=llm_client)

    assert output != hallucinated
    assert "999" not in output
    assert "research/education only, not financial advice" in output


def test_llm_failure_uses_template_fallback(fetched_at):
    result = fundamentals_result(fetched_at)

    def fail(system, user, max_tokens, temperature):
        raise RuntimeError("offline")

    llm_client = MockLLMClient(fail)

    output = explain.generate_explanation(result, llm_client=llm_client)

    assert "MOCK fundamentals summary" in output
    assert "not financial advice" in output
