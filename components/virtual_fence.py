import streamlit as st
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import math
import os
import pandas as pd  # CSV I/O

# ---------------- 설정 ----------------
SNAP_PX  = 16.0
CLOSE_PX = 18.0
# 초록 확정 시 내부 가이드 자동 생성 비율(노랑 > 빨강)
YELLOW_SCALE = 0.65
RED_SCALE    = 0.30
# ------------------------------------

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

def _find_closed_polygon(lines_snapped, min_v=3, max_v=10):
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

def _centroid(points):
    cx = sum(x for x,_ in points) / len(points)
    cy = sum(y for _,y in points) / len(points)
    return cx, cy

def _scale_polygon(points, center, scale):
    cx, cy = center
    return [(cx + (x - cx) * scale, cy + (y - cy) * scale) for (x, y) in points]

# ---------------- CSV I/O ----------------
def _csv_dir():
    d = os.path.join("data", "fences")
    os.makedirs(d, exist_ok=True)
    return d

def _csv_path(cam_id, area_key):
    safe_area_key = str(area_key).replace("/", "_")
    return os.path.join(_csv_dir(), f"{cam_id}_{safe_area_key}.csv")

def save_fence_csv(cam_id, area_key, disp_w, disp_h):
    modes = ["1차 감지", "2차 감지", "1차+2차 감지"]
    saved_keys = {m: f"vf_saved_{area_key}_{m}" for m in modes}
    rows = []
    for m in modes:
        data = st.session_state.get(saved_keys[m])
        if not isinstance(data, dict):
            continue
        pts = data.get("norm_points")
        if not pts:
            # objects에 절대좌표만 있는 경우 보정
            for o in data.get("objects", []):
                if o.get("type") == "polygon":
                    abs_pts = [(p["x"], p["y"]) for p in o.get("points", [])]
                    pts = [(x/disp_w, y/disp_h) for (x, y) in abs_pts]
                    break
        if not pts:
            continue
        for idx, (xn, yn) in enumerate(pts):
            rows.append({
                "cam_id": cam_id, "area_key": area_key,
                "mode": m, "idx": idx, "x_norm": float(xn), "y_norm": float(yn)
            })
    if not rows:
        return
    df = pd.DataFrame(rows).sort_values(["mode", "idx"])
    path = _csv_path(cam_id, area_key)
    df.to_csv(path, index=False)


def delete_fence_csv(cam_id: str, area_key: str) -> bool:
    """해당 영역의 가상펜스 CSV를 삭제합니다."""
    try:
        path = _csv_path(cam_id, area_key)
        if os.path.exists(path):
            os.remove(path)
            return True
    except Exception:
        pass
    return False


def load_fence_csv(cam_id, area_key):
    path = _csv_path(cam_id, area_key)
    if not os.path.exists(path):
        return False
    df = pd.read_csv(path)
    modes = ["1차 감지", "2차 감지", "1차+2차 감지"]
    color_map = {"1차 감지": "yellow", "2차 감지": "red", "1차+2차 감지": "lime"}
    saved_keys = {m: f"vf_saved_{area_key}_{m}" for m in modes}
    any_loaded = False
    for m in modes:
        sub = df[df["mode"] == m].sort_values("idx")
        if sub.empty:
            st.session_state[saved_keys[m]] = None
            continue
        pts = list(zip(sub["x_norm"].astype(float), sub["y_norm"].astype(float)))
        st.session_state[saved_keys[m]] = {
            "objects": [],               # 표시는 아래에서 재구성
            "norm_points": pts,
            "color": color_map[m]
        }
        any_loaded = True
    return any_loaded
# ----------------------------------------

def render_virtual_fence_editor(cam_id, img_path, area_key):
    # ===== 이미지 =====
    pil_img = Image.open(img_path).convert("RGB")
    max_width = 800
    if pil_img.width > max_width:
        new_height = int(max_width * pil_img.height / pil_img.width)
        pil_img = pil_img.resize((max_width, new_height))
    disp_w, disp_h = pil_img.width, pil_img.height

    # ===== 상태 키 =====
    init_key       = f"vf_init_{cam_id}_{area_key}"
    prev_cnt_key   = f"vf_prev_cnt_{cam_id}_{area_key}"
    loaded_flagkey = f"vf_csv_loaded_{cam_id}_{area_key}"

    # ===== 색상/모드 =====
    detection_mode = st.session_state.get(f"detection_radio_{area_key}", "1차 감지")
    color_map = {"1차 감지": "yellow", "2차 감지": "red", "1차+2차 감지": "lime"}
    stroke_color = color_map.get(detection_mode, "gray")

    modes = ["1차 감지", "2차 감지", "1차+2차 감지"]
    saved_keys = {m: f"vf_saved_{area_key}_{m}" for m in modes}

    # ===== 자동 로드: 영역 토글 ON일 때만(에디터 진입 시 1회) =====
    area_active = st.session_state.get(f"area_state_{area_key}", False)
    if area_active and not st.session_state.get(loaded_flagkey, False):
        if load_fence_csv(cam_id, area_key):
            st.session_state[loaded_flagkey] = True
            st.session_state[init_key] = None
            st.session_state[prev_cnt_key] = 0
            st.experimental_rerun()

    saved_objs_by_mode = {m: st.session_state.get(saved_keys[m]) for m in modes}

    # ===== 표시용 객체 병합(정규화 좌표 → 폴리곤 재구성) =====
    merged_objects = []
    for m in modes:
        data = saved_objs_by_mode[m]
        if not isinstance(data, dict):
            continue
        if data.get("norm_points"):
            pts = [{"x": x * disp_w, "y": y * disp_h} for (x, y) in data["norm_points"]]
            color = data.get("color", color_map.get(m, "yellow"))
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
            merged_objects.extend(data.get("objects", []))

    current_saved = saved_objs_by_mode[detection_mode]
    drawing_mode = "transform" if current_saved else "line"

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
        display_toolbar=False
    )

    # ===== 드로잉 처리 + 자동 저장 =====
    if (not current_saved) and canvas_result.json_data:
        objs = canvas_result.json_data.get("objects", [])
        fixed_cnt = len(merged_objects)
        tail_objs = objs[fixed_cnt:]
        cur_cnt = len(tail_objs)
        prev_cnt = st.session_state.get(prev_cnt_key, 0)

        if cur_cnt > prev_cnt and cur_cnt >= 1 and tail_objs[-1].get("type") == "line":
            last = tail_objs[-1]
            prev_objs = tail_objs[:-1]

            candidate_endpoints = _extract_line_endpoints_abs(merged_objects + prev_objs)
            left, top = last.get("left", 0.0), last.get("top", 0.0)
            x1a = last.get("x1", 0.0) + left; y1a = last.get("y1", 0.0) + top
            x2a = last.get("x2", 0.0) + left; y2a = last.get("y2", 0.0) + top
            p1 = _snap_to_nearest((x1a, y1a), candidate_endpoints, SNAP_PX)
            p2 = _snap_to_nearest((x2a, y2a), candidate_endpoints, SNAP_PX)

            snapped = dict(last)
            snapped["x1"] = p1[0] - left; snapped["y1"] = p1[1] - top
            snapped["x2"] = p2[0] - left; snapped["y2"] = p2[1] - top

            draft_objs = []
            for o in prev_objs:
                draft_objs.append(_as_draft_line(o) if o.get("type") == "line" else o)
            draft_objs.append(_as_draft_line(snapped))

            all_lines = _extract_lines_abs(merged_objects + draft_objs)
            reps = _cluster_points([pt for seg in all_lines for pt in seg], CLOSE_PX)
            remapped = _remap_lines_to_reps(all_lines, reps)
            poly_pts = _find_closed_polygon(remapped, min_v=3, max_v=10)

            if poly_pts:
                polygon = _fabric_polygon(poly_pts, color=stroke_color)
                handles = _vertex_handles(poly_pts)
                norm_pts = [(x/disp_w, y/disp_h) for (x, y) in poly_pts]
                st.session_state[saved_keys[detection_mode]] = {
                    "objects": [polygon] + handles,
                    "norm_points": norm_pts,
                    "color": stroke_color
                }

                # 1+2차(초록) 확정 시 내부 노랑→빨강 자동 생성(가이드)
                if detection_mode == "1차+2차 감지":
                    cx, cy = _centroid(poly_pts)
                    yellow_saved = st.session_state.get(saved_keys["1차 감지"])
                    red_saved    = st.session_state.get(saved_keys["2차 감지"])

                    if not yellow_saved:
                        yellow_pts = _scale_polygon(poly_pts, (cx, cy), YELLOW_SCALE)
                        yellow_poly = _fabric_polygon(yellow_pts, color="yellow")
                        yellow_norm = [(x/disp_w, y/disp_h) for (x, y) in yellow_pts]
                        st.session_state[saved_keys["1차 감지"]] = {
                            "objects": [yellow_poly],
                            "norm_points": yellow_norm,
                            "color": "yellow"
                        }

                    if not red_saved:
                        red_pts = _scale_polygon(poly_pts, (cx, cy), RED_SCALE)
                        red_poly = _fabric_polygon(red_pts, color="red")
                        red_norm = [(x/disp_w, y/disp_h) for (x, y) in red_pts]
                        st.session_state[saved_keys["2차 감지"]] = {
                            "objects": [red_poly],
                            "norm_points": red_norm,
                            "color": "red"
                        }

                # 자동 CSV 저장(완성 시)
                save_fence_csv(cam_id, area_key, disp_w, disp_h)

                st.session_state[init_key] = None
                st.session_state[prev_cnt_key] = 0
                st.experimental_rerun()
            else:
                st.session_state[init_key] = {"objects": draft_objs}
                st.session_state[prev_cnt_key] = len(draft_objs)

        st.session_state[prev_cnt_key] = cur_cnt
    else:
        st.session_state[prev_cnt_key] = 0
        st.session_state[init_key] = None
