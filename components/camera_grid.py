import streamlit as st
from streamlit_drawable_canvas import st_canvas
import os
from components.virtual_fence import render_virtual_fence_editor
from PIL import Image
import streamlit.components.v1 as components

# 🔹 JS로 브라우저 폭 읽어서 세션에 저장 + 폭 변경 시 자동 rerun
def _update_screen_width():
    components.html("""
    <script>
    const sendWidth = () => {
        const width = document.querySelector('.block-container').offsetWidth;
        // 값 전달
        window.parent.postMessage(
            {type: 'streamlit:setComponentValue', value: width},
            '*'
        );
    };
    window.addEventListener('resize', sendWidth);
    sendWidth();
    </script>
    """, height=0)

    # JS에서 받은 값 적용
    if "component_value" in st.session_state:
        if st.session_state.get("screen_width") != st.session_state["component_value"]:
            st.session_state["screen_width"] = st.session_state["component_value"]
            st.experimental_rerun()  # 🔥 폭 변경 시 즉시 rerun

def render_camera_grid(data):
    _update_screen_width()  # 매번 호출하여 화면 폭 갱신

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


def _get_saved_fence_initial(area_key: str, disp_w: int, disp_h: int):
    """정규화 좌표를 현재 표시 크기로 되살려 initial_drawing 생성."""
    modes = ["1차 감지", "2차 감지", "1차+2차 감지"]
    merged = []
    for m in modes:
        data = st.session_state.get(f"vf_saved_{area_key}_{m}")
        if not isinstance(data, dict):
            continue

        if "norm_points" in data:
            pts = [{"x": x * disp_w, "y": y * disp_h} for (x, y) in data["norm_points"]]
            color = data.get("color", "yellow")
            poly = {
                "type": "polygon",
                "fill": "rgba(0,0,0,0)",
                "stroke": color,
                "strokeWidth": 3,
                "objectCaching": False,
                "points": pts,
                "selectable": False, "evented": False,
                "hasControls": False, "hasBorders": False,
                "lockMovementX": True, "lockMovementY": True,
                "lockScalingX": True, "lockScalingY": True,
                "lockRotation": True,
            }
            merged.append(poly)
        else:
            # 구버전 호환
            for o in data.get("objects", []):
                if o.get("type") == "polygon":
                    oo = dict(o)
                    oo.update({
                        "selectable": False, "evented": False,
                        "hasControls": False, "hasBorders": False,
                        "lockMovementX": True, "lockMovementY": True,
                        "lockScalingX": True, "lockScalingY": True,
                        "lockRotation": True,
                    })
                    merged.append(oo)

    return {"objects": merged} if merged else None


def render_camera_card(cam, full_width=False):
    cam_id = cam['cam_id']
    recording = st.session_state.get(f"recording_state_{cam_id}", cam.get("recording", False))
    recording_state = "🔴 녹화중" if recording else "⚫ 녹화정지"

    area_list = st.session_state.get(f"area_list_{cam_id}", cam.get("area", []))

    active_idx = 0
    for idx, a in enumerate(area_list):
        edit_key = f"area_edit_{cam_id}_{a.get('area_number', idx + 1)}"
        if st.session_state.get(edit_key, a.get("area_edit", False)):
            active_idx = idx
            break

    area = area_list[active_idx] if area_list else {"primary_detection": 0, "secondary_detection": 0, "area_number": 1}
    area_number = area.get("area_number", active_idx + 1)
    area_key = f"{cam_id}_area_{active_idx}"

    area_edit_key = f"area_edit_{cam_id}_{area_number}"
    area_edit = st.session_state.get(area_edit_key, area.get("area_edit", False))
    area_edit_state = "🟢 편집모드" if area_edit else "🟠 감시모드"

    safety_message = ""
    safety_class = ""
    if cam['safe_level'] == 1:
        safety_message, safety_class = "안전합니다", "safe"
    elif cam['safe_level'] == 2:
        safety_message, safety_class = "작업자 진입 확인", "warning"
    elif cam['safe_level'] == 3:
        safety_message, safety_class = "작업자 위험반경 진입", "danger"

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

        pil_img = Image.open(image_path).convert("RGB")
        orig_w, orig_h = pil_img.size

        # 현재 화면 폭 기반 카드 폭 계산
        screen_width = st.session_state.get("screen_width", 1200)
        if full_width:
            card_width = int(screen_width * 0.98)
        else:
            card_width = int(screen_width * 0.48)  # 2열일 때 한 칸 폭

        scale_ratio = card_width / orig_w
        disp_w = card_width
        disp_h = int(orig_h * scale_ratio)

        if area_edit:
            render_virtual_fence_editor(
                cam_id=cam_id,
                img_path=image_path,
                area_key=area_key
            )
        else:
            initial = _get_saved_fence_initial(area_key, disp_w, disp_h)

            st_canvas(
                fill_color="rgba(0, 0, 0, 0)",
                stroke_width=3,
                background_image=pil_img,
                height=disp_h,
                width=disp_w,
                drawing_mode="transform",
                update_streamlit=False,
                initial_drawing=initial,
                key=f"readonly_canvas_{cam_id}_{area_key}",
                display_toolbar=False
            )

            st.markdown("🔒 감시모드에서는 팬스를 편집할 수 없습니다.")

    except Exception as e:
        st.error(f"이미지를 불러올 수 없습니다: {e}")
