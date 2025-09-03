import streamlit as st
from streamlit_drawable_canvas import st_canvas
import os
from components.virtual_fence import render_virtual_fence_editor, load_fence_csv
from PIL import Image
import streamlit.components.v1 as components
import cv2

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

# 🔸 활성(ON)된 여러 영역을 하나의 initial_drawing으로 병합
def _merge_initial_for_camera(cam_id: str, area_list, disp_w: int, disp_h: int):
    modes = ["1차 감지", "2차 감지", "1차+2차 감지"]
    color_fallback = {"1차 감지": "yellow", "2차 감지": "red", "1차+2차 감지": "lime"}
    merged_objects = []

    for idx, _area in enumerate(area_list):
        area_key = f"{cam_id}_area_{idx}"
        area_active = st.session_state.get(f"area_state_{area_key}", False)
        if not area_active:
            continue  # OFF 영역은 합치지 않음

        # 각 영역 CSV 자동 로드(최초 1회)
        loaded_flagkey = f"vf_csv_loaded_{cam_id}_{area_key}"
        if area_active and not st.session_state.get(loaded_flagkey, False):
            if load_fence_csv(cam_id, area_key):
                st.session_state[loaded_flagkey] = True

        for m in modes:
            data = st.session_state.get(f"vf_saved_{area_key}_{m}")
            if not isinstance(data, dict):
                continue
            if data.get("norm_points"):
                pts = [{"x": x * disp_w, "y": y * disp_h} for (x, y) in data["norm_points"]]
                color = data.get("color", color_fallback.get(m, "yellow"))
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
                merged_objects.append(poly)
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
                        merged_objects.append(oo)

    return {"objects": merged_objects} if merged_objects else None


def capture_video_frame(video_path, cam_id, area_number):
    """
    비디오에서 첫 프레임 캡처 및 저장

    :param video_path: 비디오 파일 경로
    :param cam_id: 카메라 ID
    :param area_number: 영역 번호
    :return: 캡처 성공 여부
    """
    try:
        # 비디오 경로 확인
        if not os.path.exists(video_path):
            st.warning(f"비디오 파일을 찾을 수 없습니다: {video_path}")
            return False

        # OpenCV로 비디오 캡처
        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            st.warning(f"비디오에서 프레임을 캡처할 수 없습니다: {video_path}")
            return False

        # 저장 경로 및 파일명 생성
        save_dir = "./assets/images"
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, f"cam_{cam_id}_frame.jpg")

        # 프레임 저장
        cv2.imwrite(save_path, frame)
        #st.success(f"프레임 캡처 완料: {save_path}")
        return True

    except Exception as e:
        st.error(f"프레임 캡처 중 오류: {e}")
        return False


def render_camera_card(cam, full_width=False):
    cam_id = cam['cam_id']
    recording = st.session_state.get(f"recording_state_{cam_id}", cam.get("recording", False))
    recording_state = "🔴 녹화중" if recording else "⚫ 녹화정지"

    area_list = st.session_state.get(f"area_list_{cam_id}", cam.get("area", []))

    # 카메라 헤더 (공통)
    st.markdown(f"""
        <div class="camera-header">
            <span class="camera-id">{cam_id}</span>
            <span class="camera-name">| {cam['cam_name']}</span>
            <span class="camera-status">| {recording_state}</span>
        </div>
    """, unsafe_allow_html=True)

    # 화면 폭 계산
    try:
        screen_width = st.session_state.get("screen_width", 1200)
        card_width = int(screen_width * (0.98 if full_width else 0.48))

        # 편집 중 여부 체크
        any_area_edit = False
        for idx, area in enumerate(area_list):
            area_number = area.get("area_number", idx + 1)
            area_edit_key = f"area_edit_{cam_id}_{area_number}"

            if st.session_state.get(area_edit_key, area.get("area_edit", False)):
                any_area_edit = True

                # 비디오 프레임 캡처
                if (not st.session_state.get(f"frame_captured_{cam_id}_{area_number}", False)):
                    if cam.get("video_path"):
                        capture_result = capture_video_frame(
                            os.path.abspath(cam["video_path"]),
                            cam_id,
                            area_number
                        )

                        # 캡처 성공 시 세션에 표시
                        if capture_result:
                            st.session_state[f"frame_captured_{cam_id}_{area_number}"] = True

        if any_area_edit:
            # image_path = os.path.abspath(cam["image_path"])
            # 편집 모드 → 기존 이미지 기반 에디터 유지
            captured_image_path = os.path.join("./assets/images", f"cam_{cam_id}_frame.jpg")

            if not os.path.exists(captured_image_path):
                st.warning(f"캡처된 이미지를 찾을 수 없습니다 : {captured_image_path}")
                return

            pil_img = Image.open(captured_image_path).convert("RGB")
            orig_w, orig_h = pil_img.size
            scale_ratio = card_width / orig_w
            disp_w = card_width
            disp_h = int(orig_h * scale_ratio)

            any_area_edit = False
            for idx, area in enumerate(area_list):
                area_number = area.get("area_number", idx + 1)
                area_key = f"{cam_id}_area_{idx}"
                area_edit_key = f"area_edit_{cam_id}_{area_number}"
                area_edit = st.session_state.get(area_edit_key, area.get("area_edit", False))

                # 영역 헤더
                st.markdown(f"""
                    <div class="info-row">
                        <b>영역 {area_number}</b> | {"🟢 편집모드" if area_edit else "🟠 감시모드"} |
                        <span class="safety-status {'safe' if cam['safe_level']==1 else 'warning' if cam['safe_level']==2 else 'danger'}">
                            {"안전합니다" if cam['safe_level']==1 else "작업자 진입 확인" if cam['safe_level']==2 else "작업자 위험반경 진입"}
                        </span> |
                        1차: {area['primary_detection']} / 2차: {area['secondary_detection']}
                    </div>
                """, unsafe_allow_html=True)

                if area_edit:
                    render_virtual_fence_editor(
                        cam_id=cam_id,
                        img_path=captured_image_path,
                        area_key=area_key
                    )
        else:
            # 감시 모드 → 비디오 재생으로 전환 (오버레이는 이후 단계에서)
            video_path = os.path.abspath(cam["video_path"])
            if not os.path.exists(video_path):
                st.error(f"❌ 비디오 파일이 존재하지 않습니다: {video_path}")
                return

            # 카드 폭 맞춰 레이아웃만 유지
            with st.container():
                st.video(video_path)

            # 캔버스 하단에 영역별 요약만 출력
            for idx, area in enumerate(area_list):
                area_number = area.get("area_number", idx + 1)
                area_key = f"{cam_id}_area_{idx}"
                area_active = st.session_state.get(f"area_state_{area_key}", False)
                st.markdown(f"""
                    <div class="info-row">
                        <b>영역 {area_number}</b> | {"표시중" if area_active else "숨김"} |
                        <span class="safety-status {'safe' if cam['safe_level']==1 else 'warning' if cam['safe_level']==2 else 'danger'}">
                            {"안전합니다" if cam['safe_level']==1 else "작업자 진입 확인" if cam['safe_level']==2 else "작업자 위험반경 진입"}
                        </span> |
                        1차: {area['primary_detection']} / 2차: {area['secondary_detection']}
                    </div>
                """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"영상을 불러올 수 없습니다: {e}")


def render_camera_grid(data):
    """카메라 리스트를 2열 그리드(또는 편집 중인 카메라만 전체 폭)로 렌더링."""
    _update_screen_width()  # 매번 호출하여 화면 폭 갱신

    # 편집 중인 카메라가 하나라도 있으면 그 카메라만 전체 폭으로 표시
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