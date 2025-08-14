import streamlit as st
import os
import platform
import subprocess
import json  # cam_data.json 저장
from components.virtual_fence import delete_fence_csv  # 새로고침/삭제용 (이미 사용 중이면 유지)

def open_folder_in_front(path):
    abs_path = os.path.abspath(path)
    try:
        if platform.system() == "Windows":
            subprocess.Popen(['explorer', abs_path])
        elif platform.system() == "Darwin":
            subprocess.Popen(['open', '-R', abs_path])
        else:
            file_managers = ['nautilus', 'nemo', 'dolphin', 'thunar']
            for fm in file_managers:
                try:
                    subprocess.Popen([fm, abs_path])
                    break
                except (subprocess.SubprocessError, FileNotFoundError):
                    continue
            else:
                subprocess.Popen(['xdg-open', abs_path])
    except Exception as e:
        st.error(f"❌ 폴더를 열 수 없습니다: {str(e)}")

def _persist_cam_data(source_data):
    try:
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cam_json_path = os.path.join(current_dir, "data", "cam_data.json")

        output = []
        for cam in source_data:
            cam_id = cam["cam_id"]
            updated_cam = dict(cam)

            # 녹화 상태 반영
            rec_key = f"recording_state_{cam_id}"
            if rec_key in st.session_state:
                updated_cam["recording"] = bool(st.session_state[rec_key])

            # 영역 리스트 반영 + 번호 재정렬
            area_list_ss = st.session_state.get(f"area_list_{cam_id}", cam.get("area", []))
            normalized_areas = []
            for i, a in enumerate(area_list_ss, start=1):
                aa = dict(a)
                aa["area_number"] = i
                area_key = f"{cam_id}_area_{i-1}"
                if f"area_state_{area_key}" in st.session_state:
                    aa["area_active"] = bool(st.session_state[f"area_state_{area_key}"])
                area_edit_key = f"area_edit_{cam_id}_{i}"
                if area_edit_key in st.session_state:
                    aa["area_edit"] = bool(st.session_state[area_edit_key])
                normalized_areas.append(aa)
            updated_cam["area"] = normalized_areas

            output.append(updated_cam)

        os.makedirs(os.path.dirname(cam_json_path), exist_ok=True)
        with open(cam_json_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"❌ cam_data.json 저장 중 오류: {e}")

def render_sidebar(data):
    st.write("🟢 INTERX-Lounge")

    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    images_path = os.path.join(current_dir, "assets", "cam_images_log")
    videos_path = os.path.join(current_dir, "assets", "cam_videos_log")
    os.makedirs(images_path, exist_ok=True)
    os.makedirs(videos_path, exist_ok=True)

    # 편집 중인 카메라 찾기
    editing_cam_id = None
    for c in data:
        cam_id = c["cam_id"]
        area_list_probe = st.session_state.get(f"area_list_{cam_id}", c.get("area", []))
        for idx, a in enumerate(area_list_probe):
            area_num = a.get("area_number", idx + 1)
            if st.session_state.get(f"area_edit_{cam_id}_{area_num}", a.get("area_edit", False)):
                editing_cam_id = cam_id
                break
        if editing_cam_id:
            break

    # 편집 중이면 해당 카메라만 렌더
    cams_to_render = [cam for cam in data if cam["cam_id"] == editing_cam_id] if editing_cam_id else data

    # 사이드바 내 “동시 편집 방지” 상태 계산(현재 렌더 대상 기준)
    editing_anywhere = any(
        st.session_state.get(f"area_edit_{c['cam_id']}_{a.get('area_number', 1)}", False)
        for c in cams_to_render
        for a in st.session_state.get(f"area_list_{c['cam_id']}", c.get("area", []))
    )

    for cam in cams_to_render:
        cam_id = cam['cam_id']

        if f"recording_state_{cam_id}" not in st.session_state:
            st.session_state[f"recording_state_{cam_id}"] = cam.get("recording", False)

        if f"area_list_{cam_id}" not in st.session_state:
            st.session_state[f"area_list_{cam_id}"] = list(cam.get("area", []))

        area_list = st.session_state[f"area_list_{cam_id}"]

        with st.container():
            st.markdown(f"""
                <div class="cam-box">
                    <div class="cam-title">
                        {cam_id} <span class="cam-subtitle">| {cam['cam_name']}</span>
                    </div>
            """, unsafe_allow_html=True)

            with st.expander("⋮ 더보기"):
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("📁 사진 보관함", key=f"photo_{cam_id}", use_container_width=True):
                        folder = os.path.join(images_path, f"cam{cam_id}")
                        os.makedirs(folder, exist_ok=True)
                        open_folder_in_front(folder)
                with col2:
                    if st.button("📁 영상 보관함", key=f"video_{cam_id}", use_container_width=True):
                        folder = os.path.join(videos_path, f"cam{cam_id}")
                        os.makedirs(folder, exist_ok=True)
                        open_folder_in_front(folder)

            # 상태 뱃지
            safety_message, safety_class = "", ""
            if cam['safe_level'] == 1:
                safety_message, safety_class = "안전합니다", "safe"
            elif cam['safe_level'] == 2:
                safety_message, safety_class = "작업자 진입 확인", "warning"
            elif cam['safe_level'] == 3:
                safety_message, safety_class = "작업자 위험반경 진입", "danger"

            st.markdown(f"""<div class="safety-status {safety_class}">{safety_message}</div>""", unsafe_allow_html=True)

            # 녹화 토글
            current_status = "녹화중" if st.session_state[f"recording_state_{cam_id}"] else "녹화정지"
            new_recording = st.toggle(
                current_status,
                value=st.session_state[f"recording_state_{cam_id}"],
                key=f"recording_toggle_{cam_id}"
            )
            if new_recording != st.session_state[f"recording_state_{cam_id}"]:
                st.session_state[f"recording_state_{cam_id}"] = new_recording
                _persist_cam_data(data)
                st.experimental_rerun()

            # 영역들
            for idx, area in enumerate(area_list):
                area_number = area.get("area_number", idx + 1)
                area_key = f"{cam_id}_area_{idx}"

                if f"area_state_{area_key}" not in st.session_state:
                    st.session_state[f"area_state_{area_key}"] = area.get("area_active", False)

                area_active = st.toggle(
                    f"영역 {area_number}",
                    value=st.session_state[f"area_state_{area_key}"],
                    key=f"area_toggle_{area_key}"
                )
                if area_active != st.session_state[f"area_state_{area_key}"]:
                    st.session_state[f"area_state_{area_key}"] = area_active
                    if idx < len(st.session_state[f"area_list_{cam_id}"]):
                        st.session_state[f"area_list_{cam_id}"][idx]["area_active"] = area_active
                    loaded_flagkey = f"vf_csv_loaded_{cam_id}_{area_key}"
                    st.session_state.pop(loaded_flagkey, None)
                    _persist_cam_data(data)
                    st.experimental_rerun()

                st.markdown(f"""
                    <div class="cam-row">
                        <div class="primary">1차 감지</div><div>{area.get('primary_detection', 0)}</div>
                    </div>
                    <div class="cam-row">
                        <div class="secondary">2차 감지</div><div>{area.get('secondary_detection', 0)}</div>
                    </div>
                """, unsafe_allow_html=True)

                # 편집 모드 토글
                area_edit_key = f"area_edit_{cam_id}_{area_number}"
                if area_edit_key not in st.session_state:
                    st.session_state[area_edit_key] = area.get("area_edit", False)

                disabled = editing_anywhere and not st.session_state[area_edit_key]
                new_edit_value = st.toggle("✏️ 편집 모드", key=f"area_edit_toggle_{area_key}", disabled=disabled)
                prev_edit_value = st.session_state.get(area_edit_key, area.get("area_edit", False))
                if new_edit_value != prev_edit_value:
                    st.session_state[area_edit_key] = new_edit_value
                    if idx < len(st.session_state[f"area_list_{cam_id}"]):
                        st.session_state[f"area_list_{cam_id}"][idx]["area_edit"] = new_edit_value
                    _persist_cam_data(data)
                    st.experimental_rerun()

                # 편집 중일 때만 세부 설정
                if st.session_state.get(area_edit_key, False):
                    with st.expander("⋮ 감지 보기 설정", expanded=True):
                        st.radio(
                            "감지 항목 선택",
                            options=["1차 감지", "2차 감지", "1차+2차 감지"],
                            index=0,
                            key=f"detection_radio_{area_key}"
                        )
                        col_del, col_refresh = st.columns(2)
                        with col_del:
                            if st.button("🗑️ 삭제", key=f"delete_area_{area_key}"):
                                st.session_state[f"area_list_{cam_id}"].pop(idx)
                                # 가상펜스 CSV/세션 정리
                                delete_fence_csv(cam_id, area_key)
                                for m in ["1차 감지", "2차 감지", "1차+2차 감지"]:
                                    st.session_state.pop(f"vf_saved_{area_key}_{m}", None)
                                st.session_state.pop(f"vf_init_{cam_id}_{area_key}", None)
                                st.session_state.pop(f"vf_prev_cnt_{cam_id}_{area_key}", None)
                                st.session_state.pop(f"vf_csv_loaded_{cam_id}_{area_key}", None)
                                _persist_cam_data(data)
                                st.experimental_rerun()
                        with col_refresh:
                            if st.button("🔄 새로고침", key=f"refresh_area_{area_key}"):
                                # 해당 영역 가상펜스 초기화
                                delete_fence_csv(cam_id, area_key)
                                for m in ["1차 감지", "2차 감지", "1차+2차 감지"]:
                                    st.session_state.pop(f"vf_saved_{area_key}_{m}", None)
                                st.session_state.pop(f"vf_init_{cam_id}_{area_key}", None)
                                st.session_state.pop(f"vf_prev_cnt_{cam_id}_{area_key}", None)
                                st.session_state.pop(f"vf_csv_loaded_{cam_id}_{area_key}", None)
                                st.experimental_rerun()

            # 영역 추가
            if len(area_list) < 2:
                if st.button('+ 영역 추가 하기', key=f"add_area_{cam_id}", use_container_width=True):
                    new_area = {
                        "area_active": False,
                        "area_number": len(area_list) + 1,
                        "primary_detection": 0,
                        "secondary_detection": 0,
                        "area_edit": False
                    }
                    st.session_state[f"area_list_{cam_id}"].append(new_area)
                    _persist_cam_data(data)
                    st.experimental_rerun()
            else:
                st.button('+ 영역 추가 하기 (최대 2개)', key=f"add_area_disabled_{cam_id}", use_container_width=True, disabled=True)

        st.markdown("</div>", unsafe_allow_html=True)