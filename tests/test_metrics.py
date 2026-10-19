from types import SimpleNamespace

from app.evaluation.metrics import recall_at_k


def test_recall_at_k_matches_document_and_page():
    expected = [{"document": "a.pdf", "page": 3}]
    retrieved = [
        SimpleNamespace(document="b.pdf", page=1),
        SimpleNamespace(document="a.pdf", page=3),
    ]
    assert recall_at_k(expected, retrieved, k=2) == 1.0
    assert recall_at_k(expected, retrieved, k=1) == 0.0
