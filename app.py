from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from sp_pdf_judger.pipeline import DocumentJudgePipeline
from sp_pdf_judger.ui_html import render_result_html, render_summary_card


st.set_page_config(
    page_title="SP 시험결과 자동판별 시스템",
    layout="wide",
)


def file_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def save_upload_to_cache(uploaded_file) -> Path:
    data = uploaded_file.getvalue()
    digest = file_digest(data)
    cache_dir = Path(tempfile.gettempdir()) / "sp_pdf_judger_uploads"
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_path = cache_dir / f"{digest}_{uploaded_file.name}"
    out_path.write_bytes(data)
    return out_path


def main() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("입력")
        uploaded_pdf = st.file_uploader("PDF 업로드", type=["pdf"])

    st.title("SP 시험결과 자동판별 시스템")

    if uploaded_pdf is None:
        st.info("왼쪽에서 PDF를 업로드해 주세요.")
        return

    pdf_path = save_upload_to_cache(uploaded_pdf)
    cache_key = f"processed::{pdf_path.name}::{pdf_path.stat().st_size}"

    if cache_key not in st.session_state:
        with st.spinner("PDF를 분석하고 있습니다..."):
            pipeline = DocumentJudgePipeline()
            st.session_state[cache_key] = pipeline.run(pdf_path)

    result = st.session_state[cache_key]

    col1, col2 = st.columns([3.4, 1.2], gap="large")
    with col1:
        st.image(str(result.preview_image_path), use_container_width=True)
    with col2:
        st.markdown(render_summary_card(result.summary), unsafe_allow_html=True)

    st.markdown("---")

    html = render_result_html(result)
    components.html(html, height=1600, scrolling=True)


if __name__ == "__main__":
    main()