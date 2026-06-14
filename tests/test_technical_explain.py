from __future__ import annotations

from quantera.lenses.technicals import explain
from quantera.lenses.technicals.lens import TechnicalsLens
from tests.conftest import MockLLMClient
from tests.test_technicals_lens import MockProvider, make_history


def technicals_result():
    prices = make_history([100 + index for index in range(260)])
    return TechnicalsLens(MockProvider(prices)).analyze("mock", with_explanation=False)


def test_clean_llm_response_passes_through():
    result = technicals_result()
    clean = (
        "MOCK technicals summary for research/education only, not financial advice. "
        "The 14-Day RSI is 100 with an OVERBOUGHT verdict."
    )
    llm_client = MockLLMClient(lambda system, user, max_tokens, temperature: clean)

    assert explain.generate_explanation(result, llm_client=llm_client) == clean
    assert llm_client.calls[0]["temperature"] == 0.0


def test_hallucinated_number_triggers_template_fallback():
    result = technicals_result()
    hallucinated = (
        "MOCK technicals summary for research/education only, not financial advice. "
        "The 14-Day RSI is 100, and a fabricated price target is 999."
    )
    llm_client = MockLLMClient(lambda system, user, max_tokens, temperature: hallucinated)

    output = explain.generate_explanation(result, llm_client=llm_client)

    assert output != hallucinated
    assert "999" not in output
    assert "research/education only, not financial advice" in output


def test_llm_failure_uses_template_fallback():
    result = technicals_result()

    def fail(system, user, max_tokens, temperature):
        raise RuntimeError("offline")

    llm_client = MockLLMClient(fail)

    output = explain.generate_explanation(result, llm_client=llm_client)

    assert "MOCK technicals summary" in output
    assert "not financial advice" in output
