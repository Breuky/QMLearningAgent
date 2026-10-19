def test_create_and_list_courses(client):
    response = client.post(
        "/api/courses",
        json={"name": "数据结构", "term": "2026秋"},
    )
    assert response.status_code == 201
    course = response.json()
    assert course["name"] == "数据结构"

    response = client.get("/api/courses")
    assert response.status_code == 200
    assert any(item["id"] == course["id"] for item in response.json())
