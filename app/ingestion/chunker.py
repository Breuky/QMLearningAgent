from dataclasses import dataclass

from app.ingestion.parser import ParsedPage


@dataclass
class ChunkData:
    page: int
    slide_title: str | None
    content_type: str
    text: str
    token_count: int


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 2)


def split_text(text: str, max_chars: int = 1200, overlap: int = 120) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            cut = text.rfind("\n", start, end)
            if cut > start + max_chars // 2:
                end = cut
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def chunk_pages(
    pages: list[ParsedPage],
    max_chars: int = 1200,
    overlap: int = 120,
) -> list[ChunkData]:
    chunks: list[ChunkData] = []
    for page in pages:
        for piece in split_text(page.text, max_chars=max_chars, overlap=overlap):
            chunks.append(
                ChunkData(
                    page=page.page,
                    slide_title=page.title,
                    content_type=page.content_type,
                    text=piece,
                    token_count=estimate_tokens(piece),
                )
            )
    return chunks
