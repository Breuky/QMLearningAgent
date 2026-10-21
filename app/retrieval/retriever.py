import logging
import math
import re
from dataclasses import dataclass

import jieba
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Chunk, Document
from app.retrieval.reranker import rerank

jieba.setLogLevel(logging.ERROR)

BM25_K1 = 1.2
BM25_B = 0.75
TITLE_BOOST = 0.5
MAX_QUERY_TERMS = 60
EXAM_SOURCE_WEIGHT = 0.4
CHAPTER_COVER_WEIGHT = 0.3
TOC_SOURCE_WEIGHT = 0.25

EXAM_FILENAME_RE = re.compile(r"sjjg|试卷|真题|样卷|答案|\d{2}-\d{2}")
TOC_MARKERS = (
    "目录导航",
    "本章目标",
    "学习目标",
    "教学目标",
    "本章要求",
    "本章内容",
    "课程内容",
    "教学安排",
)


def _effective_title(title: str | None, text: str) -> str:
    if title:
        return title
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line[:80]
    return ""


def _source_weight(filename: str, page: int, title: str | None, text: str) -> float:
    if EXAM_FILENAME_RE.search(filename.lower()):
        return EXAM_SOURCE_WEIGHT
    weight = 1.0
    if page == 1:
        weight *= CHAPTER_COVER_WEIGHT
    head = f"{title or ''}\n{text}"
    if any(marker in head for marker in TOC_MARKERS):
        weight *= TOC_SOURCE_WEIGHT
    return weight


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    document: str
    page: int
    title: str | None
    content_type: str
    text: str
    score: float


_STOPWORDS = frozenset(
    {
        "的", "了", "是", "和", "与", "及", "或", "在", "有", "为", "从", "可", "将",
        "请", "设", "若", "则", "并", "其", "这", "那", "哪", "什么", "如何", "怎么",
        "怎样", "为什么", "是否", "下列", "以下", "以上", "如下", "关于", "哪些",
        "哪个", "哪种", "多少", "几类", "几个", "分为", "各有", "把", "被", "还是",
        "已知", "写出", "得到", "共有", "种", "吗", "呢", "需要", "应该", "可以",
        "一个", "两个", "三个", "一般", "主要", "方面", "之间", "相互", "以及",
        "对于", "根据", "按照", "通过", "由于", "作为", "其中", "进行", "使用",
        "具有", "包括", "例如", "比如", "这种", "那种", "一种", "两种", "三种",
        "题目", "试述", "简述", "说明", "画出", "判断", "选择", "填空", "计算",
        "上", "中", "下", "里", "内", "外", "个", "第", "应", "能", "会", "对",
        "用", "求", "要", "使", "做", "由", "所", "之", "也", "都", "而", "就",
        "但", "如果", "那么", "因为", "所以", "然后", "现在", "下面", "上面",
        "前面", "后面", "能否", "一棵", "中有",
    }
)
_SINGLE_CHAR_TERMS = frozenset({"栈", "树", "图", "堆", "串", "链"})


def _normalize_token(token: str) -> str:
    if len(token) >= 2 and token[-1] in "上中下":
        return token[:-1]
    return token


def query_terms(query: str) -> list[str]:
    terms: list[str] = []
    han_sequence: list[str | None] = []

    for raw in jieba.lcut(query.lower()):
        token = raw.strip()
        if not token:
            han_sequence.append(None)
            continue
        if re.fullmatch(r"[一-鿿]+", token):
            token = _normalize_token(token)
            if token in _STOPWORDS or (len(token) == 1 and token not in _SINGLE_CHAR_TERMS):
                han_sequence.append(None)
                continue
            terms.append(token)
            han_sequence.append(token)
        else:
            han_sequence.append(None)
            if re.fullmatch(r"[a-z0-9_]+", token) and token not in _STOPWORDS:
                terms.append(token)

    for left, right in zip(han_sequence, han_sequence[1:]):
        if left and right and len(left) + len(right) <= 6:
            terms.append(left + right)

    return list(dict.fromkeys(terms))[:MAX_QUERY_TERMS]


def search_chunks(
    db: Session,
    course_id: int,
    query: str,
    top_k: int = 8,
) -> list[RetrievedChunk]:
    terms = query_terms(query)
    if not terms:
        return []

    chunk_filter = (
        Chunk.course_id == course_id,
        Document.status == "ready",
    )
    statement = (
        select(Chunk, Document.filename)
        .join(Document, Chunk.document_id == Document.id)
        .where(*chunk_filter, or_(*[Chunk.text.ilike(f"%{term}%") for term in terms]))
    )
    rows = db.execute(statement).all()
    if not rows:
        return []

    total_chunks = db.scalar(
        select(func.count())
        .select_from(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .where(*chunk_filter)
    ) or len(rows)
    avg_length = db.scalar(
        select(func.avg(func.length(Chunk.text)))
        .select_from(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .where(*chunk_filter)
    ) or 1.0

    haystacks = [(chunk, filename, chunk.text.lower()) for chunk, filename in rows]
    idf = {}
    for term in terms:
        freq = sum(1 for _, _, text in haystacks if term in text)
        idf[term] = math.log(1 + (total_chunks - freq + 0.5) / (freq + 0.5))

    results: list[RetrievedChunk] = []
    for chunk, filename, text in haystacks:
        length_norm = BM25_K1 * (1 - BM25_B + BM25_B * len(text) / avg_length)
        score = 0.0
        for term in terms:
            tf = text.count(term)
            if tf:
                score += idf[term] * (tf * (BM25_K1 + 1)) / (tf + length_norm)
        title_text = _effective_title(chunk.slide_title, chunk.text).lower()
        if title_text:
            score += TITLE_BOOST * sum(idf[term] for term in terms if term in title_text)
        score *= _source_weight(filename, chunk.page, chunk.slide_title, chunk.text)
        results.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document=filename,
                page=chunk.page,
                title=chunk.slide_title,
                content_type=chunk.content_type,
                text=chunk.text,
                score=score,
            )
        )

    results.sort(key=lambda item: (-item.score, item.document_id, item.page))
    return rerank(query, results, top_k)
