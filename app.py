import streamlit as st
import json
import os
from pathlib import Path
from PIL import Image
from streamlit_drawable_canvas import st_canvas

# (옵션) 오른쪽 위 메뉴 항목 비활성화
st.set_page_config(
    layout="wide",
    menu_items={"Get Help": None, "Report a bug": None, "About": None}
)

# ---------- 상단 Deploy / ... / 메뉴 / 푸터 숨기기 ----------
HIDE_TOP_UI = """
<style>
/* 햄버거 메뉴 */
#MainMenu { visibility: hidden; }
/* 푸터('Made with Streamlit') */
footer { visibility: hidden; }
/* 상단 툴바(… 포함) */
[data-testid="stToolbar"] { visibility: hidden; }
/* Deploy 포함 상단 액션버튼 영역 */
[data-testid="stHeaderActionButtons"] { display: none; }
/* 버전별 데코/상태 */
[data-testid="stDecoration"] { display: none; }
[data-testid="stStatusWidget"] { display: none; }
</style>
"""
st.markdown(HIDE_TOP_UI, unsafe_allow_html=True)

# ---------- 경로 안정화 ----------
app_dir = Path(__file__).resolve().parent
css_paths = [
    app_dir / "assets" / "style" / "cam_style.css",
    app_dir / "assets" / "style" / "camera_grid_style.css",
]
images_dir = app_dir / "assets" / "images"
cam_json = app_dir / "data" / "cam_data.json"   # <- 기존 'data/cam_data.json' 은 CWD 영향 받음

# ---------- CSS 로드(안전) ----------
for p in css_paths:
    try:
        with open(p, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"스타일 파일이 없습니다: {p}")

# ---------- cam_data 로드(안전) ----------
try:
    with open(cam_json, "r", encoding="utf-8") as f:
        cam_data = json.load(f)
    for cam in cam_data:
        # 이미지 경로를 절대경로로 보정
        cam["image_path"] = str(images_dir / cam["image_path"])
except Exception as e:
    st.error(f"카메라 데이터 로드 실패: {e}")
    cam_data = []

# ---------- 탭 ----------
tab1, tab2 = st.tabs(["AllSense.AI", "감시중인 구역"])

with tab1:
    # 사이드바/그리드 렌더러가 모듈에 있다면 안전 임포트
    try:
        from components.sidebar import render_sidebar
        from components.camera_grid import render_camera_grid
        col1, col2 = st.columns([1, 4])
        with col1:
            render_sidebar(cam_data)
        with col2:
            render_camera_grid(cam_data)
    except Exception as e:
        st.error(f"UI 컴포넌트 렌더 중 오류: {e}")

with tab2:
    st.write("🔧 감시중인 구역 - 캔버스 테스트")
    if cam_data:
        try:
            test_img_path = cam_data[0]["image_path"]
            pil_img = Image.open(test_img_path).convert("RGB")
            w, h = pil_img.size

            canvas_result = st_canvas(
                background_image=pil_img,
                width=w,
                height=h,
                drawing_mode="line",
                stroke_color="red",
                stroke_width=3,
                fill_color="rgba(0,0,0,0)",
                key="test_canvas",
            )
            st.write("캔버스 테스트 완료")
        except Exception as e:
            st.error(f"캔버스 처리 중 오류: {e}")
    else:
        st.info("카메라 데이터가 없어 캔버스를 표시할 수 없습니다.")
