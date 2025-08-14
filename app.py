import streamlit as st
import json
import os
from components.sidebar import render_sidebar
from components.camera_grid import render_camera_grid

from streamlit_drawable_canvas import st_canvas
from PIL import Image

st.set_page_config(layout="wide")

# 디자인 CSS 로드
app_dir = os.path.dirname(os.path.abspath(__file__))
css_paths = [
    os.path.join(app_dir, "assets", "style", "cam_style.css"),
    os.path.join(app_dir, "assets", "style", "camera_grid_style.css")
]

for css_path in css_paths:
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# 이미지 경로 설정 및 데이터 로드
images_dir = os.path.join(app_dir, "assets", "images")

with open("data/cam_data.json") as f:
    cam_data = json.load(f)
    for cam in cam_data:
        cam['image_path'] = os.path.join(images_dir, cam['image_path'])

tab1, tab2 = st.tabs(['AllSense.AI', '감시중인 구역'])

with tab1:
    cam_col1, cam_col2 = st.columns([1, 4])
    with cam_col1:
        render_sidebar(cam_data)
    with cam_col2:
        render_camera_grid(cam_data)

with tab2:
    st.write("🔧 감시중인 구역 - 캔버스 테스트")

    # 테스트용 이미지 불러오기 (첫 번째 카메라 이미지 사용)
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
        key="test_canvas"
    )

    st.write("캔버스 테스트 완료")
