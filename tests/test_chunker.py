from app.ingestion.chunker import chunk_pages, split_text
from app.ingestion.parser import ParsedPage


def test_split_text_respects_size_and_overlap():
    text = "第一段内容。" * 200
    chunks = split_text(text, max_chars=300, overlap=40)
    assert len(chunks) > 1
    assert all(len(chunk) <= 300 for chunk in chunks)


def test_chunk_pages_preserves_page_metadata():
    pages = [
        ParsedPage(page=2, title="栈", text="栈是一种后进先出的数据结构。" * 100),
    ]
    chunks = chunk_pages(pages, max_chars=400, overlap=50)
    assert len(chunks) > 1
    assert all(chunk.page == 2 for chunk in chunks)
    assert all(chunk.slide_title == "栈" for chunk in chunks)
