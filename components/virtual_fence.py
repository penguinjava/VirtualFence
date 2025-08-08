import streamlit as st
from streamlit_drawable_canvas import st_canvas
from PIL import Image

def render_virtual_fence_editor(cam_id, img_path):
    pil_img = Image.open(img_path).convert("RGB")
    max_width = 800
    if pil_img.width > max_width:
        new_height = int(max_width * pil_img.height / pil_img.width)
        pil_img = pil_img.resize((max_width, new_height))

    area_key = f"{cam_id}_area_0"
    detection_mode = st.session_state.get(f"detection_radio_{area_key}", "1차 감지")

    color_map = {
        "1차 감지": "yellow",
        "2차 감지": "red",
        "1차+2차 감지": "lime"
    }
    stroke_color = color_map.get(detection_mode, "gray")

    canvas_result = st_canvas(
        fill_color="rgba(0, 0, 0, 0)",  # 투명 배경
        stroke_width=3,
        stroke_color=stroke_color,
        background_image=pil_img,
        height=pil_img.height,
        width=pil_img.width,
        drawing_mode="line",
        key=f"canvas_{cam_id}",
        update_streamlit=True,
    )

    if canvas_result.json_data is not None:
        objects = canvas_result.json_data.get("objects", [])
        for i, obj in enumerate(objects):
            if obj.get("type") == "line":
                x0 = obj.get("x1")
                y0 = obj.get("y1")
                x1 = obj.get("x2")
                y1 = obj.get("y2")
                color = obj.get("stroke")
                st.write(f"선 {i} 좌표: ({x0}, {y0}) - ({x1}, {y1}), 색상: {color}")
