import logging
from dataclasses import dataclass

import httpx
from sqlalchemy.orm import Session

from app.agent.prompts import SYSTEM_PROMPT, build_user_prompt
from app.agent.tools import search_materials
from app.core.config import get_settings
from app.retrieval.citation import extract_citation_ids, strip_invalid_citations
from app.retrieval.retriever import RetrievedChunk
from app.schemas.chat import Citation

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    answer: str
    citations: list[Citation]
    intent: str


def route_intent(message: str) -> str:
    if any(keyword in message for keyword in ("出题", "题目", "练习", "测验")):
        return "quiz"
    if any(keyword in message for keyword in ("重点", "总结", "提纲", "考点")):
        return "summary"
    return "qa"


def _build_context(chunks: list[RetrievedChunk]) -> str:
    blocks = []
    for index, chunk in enumerate(chunks, start=1):
        blocks.append(
            f"[{index}] 文件：{chunk.document}，第 {chunk.page} 页\n{chunk.text}"
        )
    return "\n\n".join(blocks)


def _mock_answer(chunks: list[RetrievedChunk], intent: str) -> str:
    header = "（演示模式：未配置 DeepSeek API Key，以下为检索到的资料摘录）"
    if intent == "quiz":
        header += "\n出题功能需要配置 LLM；当前先展示可出题的资料片段。"

    blocks = [header]
    for index, chunk in enumerate(chunks[:3], start=1):
        excerpt = chunk.text[:500].strip()
        blocks.append(f"[{index}] {chunk.document} · 第 {chunk.page} 页\n{excerpt}")
    return "\n\n".join(blocks)


def _call_llm(question: str, context: str, intent: str) -> str | None:
    settings = get_settings()
    if not settings.deepseek_api_key:
        return None

    url = settings.deepseek_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(question, context, intent)},
        ],
        "temperature": 0.2,
        "stream": False,
    }
    try:
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception:
        logger.exception("LLM request failed")
        return None


def run_agent(db: Session, course_id: int, message: str) -> AgentResult:
    settings = get_settings()
    intent = route_intent(message)
    chunks = search_materials(db, course_id, message, top_k=settings.top_k)

    if not chunks:
        return AgentResult(
            answer="根据现有资料无法确定。请确认课程资料已成功入库，或换一个更具体的问题。",
            citations=[],
            intent=intent,
        )

    citations = [
        Citation(
            document=chunk.document,
            page=chunk.page,
            text=chunk.text[:400],
            score=chunk.score,
        )
        for chunk in chunks
    ]

    context = _build_context(chunks)
    answer = _call_llm(message, context, intent)
    if answer is None:
        answer = _mock_answer(chunks, intent)

    answer = strip_invalid_citations(answer, len(citations))
    if not extract_citation_ids(answer):
        sources = "\n".join(
            f"[{index}] {citation.document} · 第 {citation.page} 页"
            for index, citation in enumerate(citations, start=1)
        )
        answer += f"\n\n来源：\n{sources}"

    return AgentResult(answer=answer, citations=citations, intent=intent)
