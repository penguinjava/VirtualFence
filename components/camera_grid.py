import streamlit as st
import os
from components.virtual_fence import render_virtual_fence_editor
from PIL import Image
import numpy as np

def render_camera_grid(data):
    editing_cam_id = None
    for cam in data:
        area_list = st.session_state.get(f"area_list_{cam['cam_id']}", cam.get("area", []))
        for area in area_list:
            area_edit_key = f"area_edit_{cam['cam_id']}_{area.get('area_number', 1)}"
            if st.session_state.get(area_edit_key, area.get("area_edit", False)):
                editing_cam_id = cam['cam_id']
                break
        if editing_cam_id:
            break

    if editing_cam_id:
        for cam in data:
            if cam['cam_id'] == editing_cam_id:
                render_camera_card(cam, full_width=True)
    else:
        col1, col2 = st.columns(2)
        for idx, cam in enumerate(data):
            current_col = col1 if idx % 2 == 0 else col2
            with current_col:
                render_camera_card(cam, full_width=False)

def render_camera_card(cam, full_width=False):
    cam_id = cam['cam_id']
    recording = st.session_state.get(f"recording_state_{cam_id}", cam.get("recording", False))
    recording_state = "🔴 녹화중" if recording else "⚫ 녹화정지"

    area_list = st.session_state.get(f"area_list_{cam_id}", cam.get("area", []))
    area = area_list[0] if area_list else {"primary_detection": 0, "secondary_detection": 0, "area_number": 1}

    area_edit_key = f"area_edit_{cam_id}_{area.get('area_number', 1)}"
    area_edit = st.session_state.get(area_edit_key, area.get("area_edit", False))
    area_edit_state = "🟢 편집모드" if area_edit else "🟠 감시모드"

    safety_message = ""
    safety_class = ""
    if cam['safe_level'] == 1:
        safety_message = "안전합니다"
        safety_class = "safe"
    elif cam['safe_level'] == 2:
        safety_message = "작업자 진입 확인"
        safety_class = "warning"
    elif cam['safe_level'] == 3:
        safety_message = "작업자 위험반경 진입"
        safety_class = "danger"

    st.markdown(f"""
        <div class="camera-header">
            <span class="camera-id">{cam_id}</span>
            <span class="camera-name">| {cam['cam_name']}</span>
            <span class="camera-status">| {recording_state} | {area_edit_state}</span>
        </div>
        <div class="info-row">
            <div class="safety-status {safety_class}">{safety_message}</div>
            <div class="detection-stats">
                <span>1차: {area['primary_detection']}</span>
                <span>2차: {area['secondary_detection']}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    try:
        image_path = os.path.abspath(cam["image_path"])
        if not os.path.exists(image_path):
            st.error(f"❌ 이미지 파일이 존재하지 않습니다: {image_path}")
            return

        if area_edit:
            render_virtual_fence_editor(cam_id, image_path)
        else:
            pil_img = Image.open(image_path).convert("RGB")

            # 최대 너비 제한 (예: 430px)
            max_width = 430

            # 이미지 크기 얻기
            img_width, img_height = pil_img.size

            # 이미지 너비가 max_width보다 크면 리사이징
            if img_width > max_width:
                new_height = int(max_width * img_height / img_width)
                pil_img = pil_img.resize((max_width, new_height), resample=Image.LANCZOS)

            # 리사이징된 이미지 출력 (width만 지정하면 자동 비율 유지)
            st.image(pil_img, width=max_width)

            st.markdown("🔒 감시모드에서는 팬스를 편집할 수 없습니다.")

    except Exception as e:
        st.error(f"이미지를 불러올 수 없습니다: {e}")
