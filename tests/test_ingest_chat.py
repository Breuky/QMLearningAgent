def test_upload_then_chat(client):
    course_response = client.post(
        "/api/courses",
        json={"name": "数据结构", "term": "2026秋"},
    )
    course_id = course_response.json()["id"]

    content = (
        "栈是一种后进先出（LIFO）的数据结构，只在栈顶插入和删除。\n"
        "队列是一种先进先出（FIFO）的数据结构，在队尾插入、队头删除。\n"
    ).encode("utf-8")
    upload_response = client.post(
        f"/api/courses/{course_id}/documents",
        files={"file": ("stack.txt", content, "text/plain")},
    )
    assert upload_response.status_code == 202
    upload = upload_response.json()
    document_id = upload["document"]["id"]

    document_response = client.get(f"/api/documents/{document_id}")
    assert document_response.status_code == 200
    assert document_response.json()["status"] == "ready"

    chat_response = client.post(
        "/api/chat",
        json={"course_id": course_id, "message": "栈和队列有什么区别？"},
    )
    assert chat_response.status_code == 200
    chat = chat_response.json()
    assert chat["citations"]
    assert "栈" in chat["answer"]
    assert chat["session_id"] > 0


def test_duplicate_upload_returns_existing_document(client):
    course = client.post("/api/courses", json={"name": "操作系统"}).json()
    content = "操作系统管理进程、内存和文件。".encode("utf-8")
    first = client.post(
        f"/api/courses/{course['id']}/documents",
        files={"file": ("os.txt", content, "text/plain")},
    ).json()
    second = client.post(
        f"/api/courses/{course['id']}/documents",
        files={"file": ("os-copy.txt", content, "text/plain")},
    ).json()
    assert first["document"]["id"] == second["document"]["id"]
