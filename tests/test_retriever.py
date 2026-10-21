from app.db.session import SessionLocal
from app.models import Chunk, Course, Document
from app.retrieval.retriever import _source_weight, query_terms, search_chunks


def test_query_terms_keeps_domain_terms_and_drops_fillers():
    terms = query_terms("线性表、栈和队列之间的相互区别是什么？")

    assert {"线性表", "栈", "队列", "区别"} <= set(terms)
    assert "什么" not in terms
    assert "之间" not in terms


def test_query_terms_splits_compounds():
    terms = query_terms("已知先序和中序序列，能否唯一确定一棵二叉树？")

    assert {"先序", "中序", "二叉树"} <= set(terms)
    assert "中序序列" in terms


def test_source_weight_downranks_exams_covers_and_toc():
    assert _source_weight("22-23-2-sjjg-A.pdf", 1, None, "") == 0.4
    assert _source_weight("第3章 栈和队列.pptx", 1, None, "") == 0.3
    assert _source_weight("第3章 栈和队列.pptx", 2, None, "目录导航 3.1 3.2") == 0.25
    assert _source_weight("第3章 栈和队列.pptx", 11, None, "栈、队列是一种操作受限的线性表") == 1.0


def test_search_prefers_specific_short_chunk():
    with SessionLocal() as db:
        course = Course(name="检索测试")
        db.add(course)
        db.flush()
        document = Document(
            course_id=course.id,
            filename="第8章 排序.pptx",
            stored_name="sort.pptx",
            file_type="pptx",
            file_path="sort.pptx",
            checksum="retrieval-test",
            status="ready",
        )
        db.add(document)
        db.flush()
        db.add_all(
            [
                Chunk(
                    document_id=document.id,
                    course_id=course.id,
                    page=27,
                    text="希尔排序 增量序列 插入排序 算法分析 时间复杂度 " + "无关内容 " * 200,
                    token_count=0,
                ),
                Chunk(
                    document_id=document.id,
                    course_id=course.id,
                    page=28,
                    text="希尔排序 增量序列 基本思想 先将整个待排记录序列分割成若干子序列",
                    token_count=0,
                ),
            ]
        )
        db.commit()

        results = search_chunks(db, course.id, "希尔排序的增量序列是什么？", top_k=2)

    assert results
    assert results[0].page == 28
