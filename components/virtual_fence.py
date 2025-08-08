import streamlit as st
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import math

SNAP_PX  = 16.0   # 끝점 스냅
CLOSE_PX = 18.0   # 닫힘 인식(미세 틈 허용)

def _dist(a, b): return math.hypot(a[0]-b[0], a[1]-b[1])

def _extract_line_endpoints_abs(objs):
    pts=[]
    for o in (objs or []):
        if o.get("type")=="line":
            left,top=o.get("left",0.0),o.get("top",0.0)
            x1=o.get("x1",0.0)+left; y1=o.get("y1",0.0)+top
            x2=o.get("x2",0.0)+left; y2=o.get("y2",0.0)+top
            pts.extend([(x1,y1),(x2,y2)])
    return pts

def _snap_to_nearest(p, nodes, tol):
    if not nodes: return p
    q=min(nodes, key=lambda n:_dist(p,n))
    return q if _dist(p,q)<=tol else p

def _extract_lines_abs(objs):
    segs=[]
    for o in (objs or []):
        if o.get("type")=="line":
            left,top=o.get("left",0.0),o.get("top",0.0)
            x1=o.get("x1",0.0)+left; y1=o.get("y1",0.0)+top
            x2=o.get("x2",0.0)+left; y2=o.get("y2",0.0)+top
            segs.append(((x1,y1),(x2,y2)))
    return segs

def _cluster_points(pts, tol):
    clusters=[]
    for p in pts:
        placed=False
        for c in clusters:
            if any(_dist(p,q)<=tol for q in c):
                c.append(p); placed=True; break
        if not placed: clusters.append([p])
    reps=[]
    for c in clusters:
        reps.append((sum(x for x,_ in c)/len(c), sum(y for _,y in c)/len(c)))
    return reps

def _remap_lines_to_reps(lines, reps):
    def nearest(p): return min(reps, key=lambda r:_dist(p,r))
    return [(nearest(a), nearest(b)) for a,b in lines]

def _find_closed_polygon(lines_snapped, min_v=3, max_v=4):
    def key(p): return (round(p[0],2), round(p[1],2))
    adj={}
    for a,b in lines_snapped:
        ka,kb=key(a),key(b)
        adj.setdefault(ka,set()).add(kb)
        adj.setdefault(kb,set()).add(ka)

    seen=set()
    for n in adj.keys():
        if n in seen: continue
        stack=[n]; comp=set()
        while stack:
            cur=stack.pop()
            if cur in seen: continue
            seen.add(cur); comp.add(cur)
            for nb in adj[cur]:
                if nb not in seen: stack.append(nb)
        if min_v<=len(comp)<=max_v and all(len(adj[x])==2 for x in comp):
            pts=[(float(x),float(y)) for x,y in comp]
            cx=sum(x for x,_ in pts)/len(pts); cy=sum(y for _,y in pts)/len(pts)
            return sorted(pts, key=lambda p: math.atan2(p[1]-cy, p[0]-cx))
    return None

# --- 드래프트(완성 전) 오브젝트는 절대 선택/이동 금지
def _as_draft_line(o):
    o=dict(o)
    o.update({
        "selectable": False,
        "evented": False,
        "hasControls": False,
        "hasBorders": False,
        "lockMovementX": True,
        "lockMovementY": True,
        "lockScalingX": True,
        "lockScalingY": True,
        "lockRotation": True
    })
    return o

# --- 폴리곤 본체도 이동 금지(핸들만 편집)
def _fabric_polygon(points, color):
    return {
        "type":"polygon",
        "fill":"rgba(0,0,0,0)",
        "stroke": color,
        "strokeWidth": 3,
        "objectCaching": False,
        "points":[{"x":x,"y":y} for x,y in points],
        "selectable": False,
        "evented": False,
        "hasControls": False,
        "hasBorders": False,
        "lockMovementX": True,
        "lockMovementY": True,
        "lockScalingX": True,
        "lockScalingY": True,
        "lockRotation": True
    }

def _vertex_handles(points):
    hs=[]
    for i,(x,y) in enumerate(points):
        hs.append({
            "type":"circle","radius":6,"fill":"rgba(255,0,0,0.9)",
            "left": x-6, "top": y-6,
            "name": f"vf_handle_{i}",
            "selectable": True,
            "evented": True,
            "hasControls": False, "hasBorders": False
        })
    return hs


def _is_invalid_line_abs(x1a, y1a, x2a, y2a, eps=2.0):
    # (0,0) 근처로 찍힌 끝점이 있거나, 선 길이가 거의 0이면 무효
    if _dist((x1a, y1a), (0.0, 0.0)) <= eps or _dist((x2a, y2a), (0.0, 0.0)) <= eps:
        return True
    if _dist((x1a, y1a), (x2a, y2a)) <= eps:
        return True
    return False


def render_virtual_fence_editor(cam_id, img_path, area_key):
    # ===== 이미지 =====
    pil_img = Image.open(img_path).convert("RGB")
    max_width = 800
    if pil_img.width > max_width:
        new_height = int(max_width * pil_img.height / pil_img.width)
        pil_img = pil_img.resize((max_width, new_height))
    disp_w, disp_h = pil_img.width, pil_img.height  # ✅ 에디터 표시 크기

    # ===== 상태 키 (영역 기준) =====
    init_key     = f"vf_init_{cam_id}_{area_key}"       # 드래프트/초기 드로잉
    prev_cnt_key = f"vf_prev_cnt_{cam_id}_{area_key}"   # 이전 오브젝트 수
    busy_key     = f"vf_busy_{cam_id}_{area_key}"

    # ===== 색상/모드 =====
    detection_mode = st.session_state.get(f"detection_radio_{area_key}", "1차 감지")
    color_map = {
        "1차 감지": "yellow",
        "2차 감지": "red",
        "1차+2차 감지": "lime"
    }
    stroke_color = color_map.get(detection_mode, "gray")

    # 색상별 저장 슬롯(각 색상당 최대 1개 폴리곤)
    modes = ["1차 감지", "2차 감지", "1차+2차 감지"]
    saved_keys = {m: f"vf_saved_{area_key}_{m}" for m in modes}
    saved_objs_by_mode = {m: st.session_state.get(saved_keys[m]) for m in modes}

    # 모든 색상의 확정 객체를 하나로 묶어 initial 구성
    merged_objects = []
    for m in modes:
        so = saved_objs_by_mode[m]
        if so and isinstance(so, dict):
            merged_objects.extend(so.get("objects", []))

    # 현재 모드에 이미 확정된 객체가 있으면 그리기 금지(핸들 편집만)
    current_saved = saved_objs_by_mode[detection_mode]
    drawing_mode = "transform" if current_saved else ("transform" if st.session_state.get(busy_key, False) else "line")

    # init(드래프트) 포함
    draft = st.session_state.get(init_key)
    if draft and isinstance(draft, dict):
        initial = {"objects": merged_objects + draft.get("objects", [])}
    else:
        initial = {"objects": merged_objects} if merged_objects else None

    canvas_result = st_canvas(
        fill_color="rgba(0, 0, 0, 0)",
        stroke_width=3,
        stroke_color=stroke_color,
        background_image=pil_img,
        height=disp_h,
        width=disp_w,
        drawing_mode=drawing_mode,
        key=f"canvas_{cam_id}_{area_key}",
        update_streamlit=True,
        initial_drawing=initial,
        display_toolbar=False  # 🔥 툴바 숨김
    )

    # (선 디버그 - 원하면 주석)
    if canvas_result.json_data is not None:
        objects = canvas_result.json_data.get("objects", [])
        for i, obj in enumerate(objects):
            if obj.get("type") == "line":
                x0 = obj.get("x1"); y0 = obj.get("y1")
                x1 = obj.get("x2"); y1 = obj.get("y2")
                color = obj.get("stroke")
                st.write(f"선 {i} 좌표: ({x0}, {y0}) - ({x1}, {y1}), 색상: {color}")

    # === 드래프트 → 스냅/닫힘 → 현재 모드 슬롯에만 확정 저장 ===
    if (not current_saved) and canvas_result.json_data:
        objs = canvas_result.json_data.get("objects", [])
        fixed_cnt = len(merged_objects)
        tail_objs = objs[fixed_cnt:]
        cur_cnt = len(tail_objs)
        prev_cnt = st.session_state.get(prev_cnt_key, 0)

        if cur_cnt > prev_cnt and cur_cnt >= 1 and tail_objs[-1].get("type") == "line":
            last = tail_objs[-1]
            prev_objs = tail_objs[:-1]

            # 1) 마지막 선 스냅
            candidate_endpoints = _extract_line_endpoints_abs(merged_objects + prev_objs)
            left, top = last.get("left", 0.0), last.get("top", 0.0)
            x1a = last.get("x1", 0.0) + left; y1a = last.get("y1", 0.0) + top
            x2a = last.get("x2", 0.0) + left; y2a = last.get("y2", 0.0) + top
            p1 = _snap_to_nearest((x1a, y1a), candidate_endpoints, SNAP_PX)
            p2 = _snap_to_nearest((x2a, y2a), candidate_endpoints, SNAP_PX)

            snapped = dict(last)
            snapped["x1"] = p1[0] - left; snapped["y1"] = p1[1] - top
            snapped["x2"] = p2[0] - left; snapped["y2"] = p2[1] - top

            # 2) 드래프트 비선택/고정
            draft_objs = []
            for o in prev_objs:
                draft_objs.append(_as_draft_line(o) if o.get("type") == "line" else o)
            draft_objs.append(_as_draft_line(snapped))

            # 3) 닫힘 인식(3~4각형)
            all_lines = _extract_lines_abs(merged_objects + draft_objs)
            reps = _cluster_points([pt for seg in all_lines for pt in seg], CLOSE_PX)
            remapped = _remap_lines_to_reps(all_lines, reps)
            poly_pts = _find_closed_polygon(remapped, min_v=3, max_v=4)

            if poly_pts:
                polygon = _fabric_polygon(poly_pts, color=stroke_color)
                handles = _vertex_handles(poly_pts)

                # ✅ 정규화 좌표 저장 (리사이즈 무관)
                norm_pts = [(x/disp_w, y/disp_h) for (x, y) in poly_pts]

                final_obj = {
                    "objects": [polygon] + handles,  # 즉시 표시용(에디터)
                    "norm_points": norm_pts,         # 🔥 리사이즈 무관 복원용
                    "color": stroke_color
                }

                st.session_state[saved_keys[detection_mode]] = final_obj

                st.session_state[init_key] = None
                st.session_state[prev_cnt_key] = 0
                st.experimental_rerun()
            else:
                st.session_state[init_key] = {"objects": draft_objs}
                st.session_state[prev_cnt_key] = len(draft_objs)
                st.experimental_rerun()

        st.session_state[prev_cnt_key] = cur_cnt
    else:
        st.session_state[prev_cnt_key] = 0
        st.session_state[init_key] = None
