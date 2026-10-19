from app.retrieval.citation import extract_citation_ids, strip_invalid_citations


def test_extract_citation_ids():
    assert extract_citation_ids("结论[1]，依据[2]，错误[9]") == {1, 2, 9}


def test_strip_invalid_citations():
    text = "结论[1]，错误[9]"
    assert strip_invalid_citations(text, max_id=2) == "结论[1]，错误"
