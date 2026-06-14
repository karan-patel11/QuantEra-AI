from __future__ import annotations

import os

import quantera


def test_project_dotenv_loader_populates_environment_without_overriding(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "GROQ_API_KEY=dummy-groq-key",
                "NEWS_API_KEY=dummy-news-key",
                "LLM_PROVIDER=groq",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("NEWS_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")

    quantera._load_project_dotenv(tmp_path)

    assert os.environ["GROQ_API_KEY"] == "dummy-groq-key"
    assert os.environ["NEWS_API_KEY"] == "dummy-news-key"
    assert os.environ["LLM_PROVIDER"] == "anthropic"
