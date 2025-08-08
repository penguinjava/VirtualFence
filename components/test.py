import streamlit as st
from streamlit_drawable_canvas import st_canvas
from PIL import Image

pil_img = Image.open("path/to/image.png").convert("RGB")
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