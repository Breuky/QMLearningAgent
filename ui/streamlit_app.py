import os

import requests
import streamlit as st

DEFAULT_API = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="期末复习智能体", layout="wide")
st.title("期末复习智能体")
st.caption("MVP 骨架：上传资料 -> 解析 -> 关键词检索 -> 带引用回答")

with st.sidebar:
    st.subheader("连接")
    api_base = st.text_input("API 地址", DEFAULT_API).rstrip("/")
    try:
        health = requests.get(f"{api_base}/api/health", timeout=3).json()
        st.success(f"API 正常：{health.get('status')}")
    except Exception:
        st.error("无法连接 API，请先启动 uvicorn")
        st.stop()

    st.divider()
    st.subheader("创建课程")
    with st.form("create_course"):
        course_name = st.text_input("课程名称")
        course_term = st.text_input("学期（可选）")
        submitted = st.form_submit_button("创建")
    if submitted and course_name.strip():
        response = requests.post(
            f"{api_base}/api/courses",
            json={"name": course_name.strip(), "term": course_term.strip() or None},
            timeout=10,
        )
        if response.ok:
            st.success("课程已创建")
            st.rerun()
        else:
            st.error(f"{response.status_code}: {response.text}")

try:
    courses = requests.get(f"{api_base}/api/courses", timeout=5).json()
except Exception as exc:
    st.error(f"获取课程失败：{exc}")
    st.stop()

if not courses:
    st.info("请先在左侧创建一门课程。")
    st.stop()

labels = {f"{course['id']} · {course['name']}": course for course in courses}
selected = st.sidebar.selectbox("当前课程", list(labels))
course = labels[selected]

if st.session_state.get("active_course") != course["id"]:
    st.session_state.active_course = course["id"]
    st.session_state.messages = []
    st.session_state.pop("session_id", None)

upload_tab, chat_tab = st.tabs(["资料", "问答"])

with upload_tab:
    uploaded = st.file_uploader(
        "上传 PPTX / PDF / TXT / MD",
        type=["pptx", "pdf", "txt", "md"],
    )
    if uploaded is not None and st.button("上传并入库"):
        with st.spinner("上传中..."):
            response = requests.post(
                f"{api_base}/api/courses/{course['id']}/documents",
                files={"file": (uploaded.name, uploaded.getvalue())},
                timeout=120,
            )
        if response.ok:
            data = response.json()
            st.success(
                f"已上传 #{data['document']['id']}，任务 #{data['job_id']}，"
                f"状态：{data['document']['status']}"
            )
        else:
            st.error(f"{response.status_code}: {response.text}")

    if st.button("刷新资料列表"):
        st.rerun()

    try:
        documents = requests.get(
            f"{api_base}/api/courses/{course['id']}/documents",
            timeout=10,
        ).json()
        if documents:
            for document in documents:
                error = document.get("error") or ""
                st.write(
                    f"#{document['id']} {document['filename']} | "
                    f"{document['status']} | {error}"
                )
        else:
            st.info("还没有资料。")
    except Exception as exc:
        st.error(f"获取资料列表失败：{exc}")

with chat_tab:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            for citation in message.get("citations", []):
                st.caption(
                    f"[{citation['document']} · 第 {citation['page']} 页] "
                    f"{citation['text'][:120]}"
                )

    question = st.chat_input("问一个课程问题")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        payload = {"course_id": course["id"], "message": question}
        if st.session_state.get("session_id"):
            payload["session_id"] = st.session_state.session_id

        with st.spinner("检索并生成中..."):
            response = requests.post(
                f"{api_base}/api/chat",
                json=payload,
                timeout=120,
            )

        if response.ok:
            data = response.json()
            st.session_state.session_id = data["session_id"]
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": data["answer"],
                    "citations": data["citations"],
                }
            )
            st.rerun()
        else:
            st.session_state.messages.pop()
            st.error(f"{response.status_code}: {response.text}")
