import re


def extract_citation_ids(text: str) -> set[int]:
    return {int(match) for match in re.findall(r"\[(\d+)\]", text)}


def strip_invalid_citations(text: str, max_id: int) -> str:
    def replace(match: re.Match[str]) -> str:
        citation_id = int(match.group(1))
        return match.group(0) if 1 <= citation_id <= max_id else ""

    return re.sub(r"\[(\d+)\]", replace, text)
