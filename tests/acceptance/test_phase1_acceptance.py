import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.support.app_factory import create_documents_test_app


FIXTURE_ROOT = Path(__file__).parent / "pf2e_phase1_acceptance_corpus"
CORPUS_PATH = FIXTURE_ROOT / "assets" / "fixtures" / "phase1" / "phase1_corpus.json"
QUESTIONS_PATH = FIXTURE_ROOT / "tests" / "acceptance" / "phase1_questions.json"

RULE_DOCUMENTS = json.loads(CORPUS_PATH.read_text())
QUESTION_CASES = json.loads(QUESTIONS_PATH.read_text())
RULE_QUERY_CASES = [
    case for case in QUESTION_CASES if case.get("expected_kind") == "rule"
]
STRICT_ABSTENTION_CASES = [
    case for case in QUESTION_CASES if case.get("expected_strict_abstain")
]

SUPPORTED_DOCUMENT_FIELDS = {
    "title",
    "kind",
    "content",
    "summary",
    "source_name",
    "url",
}


def _seed_documents(client: TestClient) -> dict[str, int]:
    inserted_ids: dict[str, int] = {}
    for document in RULE_DOCUMENTS:
        payload = {
            field: value
            for field, value in document.items()
            if field in SUPPORTED_DOCUMENT_FIELDS
        }
        response = client.post("/api/documents", json=payload)
        assert response.status_code == 200
        inserted_ids[document["id"]] = response.json()["id"]
    return inserted_ids


def _dispose(engine) -> None:
    asyncio.run(engine.dispose())


def test_phase1_acceptance_search_filters_and_ranks_rule_results():
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        document_ids = _seed_documents(client)

        response = client.get(
            "/api/documents/search",
            params={"q": "fireball", "kind": "rule", "top_k": 3},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["results"]
        assert (
            payload["results"][0]["document"]["id"]
            == document_ids["example-spells-fireball-invisibility-shield"]
        )
        assert all(
            result["document"]["kind"] == "rule" for result in payload["results"]
        )
    finally:
        _dispose(engine)


@pytest.mark.parametrize(
    "case",
    RULE_QUERY_CASES,
    ids=[case["query"] for case in RULE_QUERY_CASES],
)
def test_phase1_acceptance_rules_queries_return_grounded_support(case: dict[str, str]):
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        document_ids = _seed_documents(client)

        response = client.post(
            "/api/documents/rules/query",
            json={"query": case["query"], "strict": True, "top_k": 3},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["citations"]
        combined_text = " ".join(
            [
                payload["answer"],
                *[citation["excerpt"] for citation in payload["citations"]],
            ]
        ).lower()
        assert case["expected_snippet"].lower() in combined_text
        assert document_ids[case["expected_doc_id"]] in {
            citation["document_id"] for citation in payload["citations"]
        }
    finally:
        _dispose(engine)


@pytest.mark.parametrize(
    "case",
    STRICT_ABSTENTION_CASES,
    ids=[case["query"] for case in STRICT_ABSTENTION_CASES],
)
def test_phase1_acceptance_strict_mode_abstains_for_unknown_rule(case: dict[str, str]):
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        _seed_documents(client)

        response = client.post(
            "/api/documents/rules/query",
            json={"query": case["query"], "strict": True, "top_k": 3},
        )

        assert response.status_code == 200
        payload = response.json()
        assert "couldn't find a confident answer" in payload["answer"].lower()
        assert payload["strict_mode"] is True
        assert payload["confidence"] < 0.08 or not payload["citations"]
    finally:
        _dispose(engine)
