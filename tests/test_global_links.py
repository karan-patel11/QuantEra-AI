from __future__ import annotations

import json

from quantera.lenses.news_sentiment.global_links import propose_global_links
from tests.conftest import MockLLMClient, sample_news_item


def test_link_with_unknown_supporting_id_is_dropped():
    item = sample_news_item()

    def llm(system, user, max_tokens, temperature):
        return json.dumps(
            {
                "global_links": [
                    {
                        "claim": "Higher supply costs may pressure margins.",
                        "confidence": "LOW",
                        "supporting_item_ids": ["unknown"],
                        "caveat": "Based on a limited item set.",
                    }
                ]
            }
        )

    assert propose_global_links([item], llm_client=MockLLMClient(llm)) == []


def test_link_without_confidence_is_dropped():
    item = sample_news_item()

    def llm(system, user, max_tokens, temperature):
        payload = json.loads(user)
        return json.dumps(
            {
                "global_links": [
                    {
                        "claim": "Services demand may support revenue mix.",
                        "supporting_item_ids": [payload["items"][0]["id"]],
                        "caveat": "Only one article supports the hypothesis.",
                    }
                ]
            }
        )

    assert propose_global_links([item], llm_client=MockLLMClient(llm)) == []


def test_no_qualifying_links_returns_empty_list():
    item = sample_news_item()

    def llm(system, user, max_tokens, temperature):
        payload = json.loads(user)
        return json.dumps(
            {
                "global_links": [
                    {
                        "claim": "Services demand supports revenue mix.",
                        "confidence": "MEDIUM",
                        "supporting_item_ids": [payload["items"][0]["id"]],
                        "caveat": "Only one article supports the hypothesis.",
                    }
                ]
            }
        )

    assert propose_global_links([item], llm_client=MockLLMClient(llm)) == []
