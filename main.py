import cv2
import numpy as np
from PIL import ImageTk
from appLauncher import get_installed_apps, get_app_icon, launch_app
from handGesture import detect
from cameraTest import cameraStart
import math
import time
from windowManager import show_all_windows, select_choose_window, open_selected_window, hide_all_windows, close_focused_window

# --- Layout constants ---
COLS = 5
ROWS = 4
ICON_SIZE = 64
SPACING_X = 130
SPACING_Y = 100
START_X = 10
START_Y = 10

# --- State ---
app_icons = []
hovered_idx = -1
pinch_armed = True
current_page = 0

# --- Page turn (tilt) state ---
gesture_armed = True
tilt_angle_buffer = []
TILT_TRIGGER = 25
TILT_REARM = 10
BUFFER_SIZE = 5

# --- Task View (3-finger) state ---
task_view_open = False
switch_armed = True
last_switch_time = 0.0
SWITCH_COOLDOWN = 1.0

close_sign = True
last_close_time = 0.0
CLOSE_COOLDOWN = 1.0


def load_apps():
    apps = get_installed_apps()
    for app in apps:
        icon, name = get_app_icon(app)
        if icon is None:
            continue
        app_icons.append((app, icon, name))


def get_apps_per_page():
    return COLS * ROWS


def get_max_page():
    aps = get_apps_per_page()
    return max(0, (len(app_icons) - 1) // aps) if app_icons else 0


def get_page_apps():
    aps = get_apps_per_page()
    return app_icons[current_page * aps:(current_page + 1) * aps]


def icon_rect(idx):
    """Return (x, y) top-left corner of icon at index on current page."""
    col = idx % COLS
    row = idx // COLS
    x = START_X + col * SPACING_X
    y = START_Y + row * SPACING_Y
    return x, y


def get_hovered(cursor_x, cursor_y):
    for idx, _ in enumerate(get_page_apps()):
        x, y = icon_rect(idx)
        if x <= cursor_x <= x + ICON_SIZE and y <= cursor_y <= y + ICON_SIZE:
            return idx
    return -1


def draw_icons(frame):
    for idx, (app, icon, name) in enumerate(get_page_apps()):
        if icon is None:
            continue
        x, y = icon_rect(idx)
        if y + ICON_SIZE > frame.shape[0] or x + ICON_SIZE > frame.shape[1]:
            continue

        icon_rgba = np.array(icon.convert('RGBA'))
        icon_rgb = icon_rgba[:, :, :3]
        alpha = icon_rgba[:, :, 3:] / 255.0
        icon_cv = cv2.cvtColor(icon_rgb, cv2.COLOR_RGB2BGR)

        region = frame[y:y + ICON_SIZE, x:x + ICON_SIZE]
        blended = (icon_cv * alpha + region * (1 - alpha)).astype(np.uint8)
        frame[y:y + ICON_SIZE, x:x + ICON_SIZE] = blended

        cv2.putText(frame, name, (x, y + ICON_SIZE + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, (237, 214, 125), 1, cv2.LINE_AA)


def draw_hover(frame, idx):
    if idx == -1:
        return
    x, y = icon_rect(idx)
    cv2.rectangle(frame, (x - 3, y - 3), (x + ICON_SIZE + 3, y + ICON_SIZE + 3),
                  (0, 255, 255), 2)


def draw_cursor(frame, cx, cy):
    cv2.circle(frame, (cx, cy), 10, (0, 255, 255), 2)
    cv2.circle(frame, (cx, cy), 2, (0, 255, 255), -1)


def draw_page_indicator(frame):
    max_page = get_max_page()
    text = f"Page {current_page + 1} / {max_page + 1}"
    cv2.putText(frame, text, (10, frame.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)


def draw_task_view_indicator(frame):
    cv2.putText(frame, "TASK VIEW: tilt = left/right, pinch = open, fist = close",
                (10, frame.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)


def get_tilt_angle_from_results(results):
    """Extract tilt angle from already-detected hand world landmarks.
    Reuses the results returned by detect() — no second detector needed.
    """
    if results is None:
        return None
    # Support both attribute-style (MediaPipe Tasks) and index-style results
    world_landmarks = getattr(results, 'hand_world_landmarks', None)
    if not world_landmarks:
        return None
    hand_3d = world_landmarks[0]
    dx = hand_3d[9].x - hand_3d[0].x
    dy = hand_3d[9].y - hand_3d[0].y
    return math.degrees(math.atan2(dx, -dy))


def processFrame(frame):
    global hovered_idx, pinch_armed, current_page, gesture_armed, tilt_angle_buffer
    global task_view_open, switch_armed, last_switch_time, close_sign, last_close_time

    frame_h, frame_w = frame.shape[:2]
    gesture, points, results, frame = detect(frame)

    # --- Open palm: show app grid + handle page turning ---
    if gesture == 'open_palm':
        draw_icons(frame)
        draw_hover(frame, hovered_idx)
        draw_page_indicator(frame)

        # Tilt-based page turning using results already returned by detect()
        angle = get_tilt_angle_from_results(results)
        if angle is not None:
            tilt_angle_buffer.append(angle)
            if len(tilt_angle_buffer) > BUFFER_SIZE:
                tilt_angle_buffer.pop(0)
            smoothed = sum(tilt_angle_buffer) / len(tilt_angle_buffer)
            max_page = get_max_page()

            if gesture_armed:
                if smoothed > TILT_TRIGGER:
                    current_page = min(current_page + 1, max_page)
                    gesture_armed = False
                elif smoothed < -TILT_TRIGGER:
                    current_page = max(current_page - 1, 0)
                    gesture_armed = False
            else:
                if abs(smoothed) < TILT_REARM:
                    gesture_armed = True

    # --- Point: move cursor and highlight hovered icon ---
    elif gesture == 'point' and points:
        draw_icons(frame)
        cursor_x = int(points[8][0])
        cursor_y = int(points[8][1])
        hovered_idx = get_hovered(cursor_x, cursor_y)
        draw_hover(frame, hovered_idx)
        draw_cursor(frame, cursor_x, cursor_y)
        draw_page_indicator(frame)

    # --- Pinch: launch hovered app OR confirm Task View selection ---
    elif gesture == 'pinch':
        if task_view_open:
            draw_task_view_indicator(frame)
            if pinch_armed:
                open_selected_window()
                task_view_open = False
                pinch_armed = False
        else:
            draw_icons(frame)
            draw_hover(frame, hovered_idx)
            draw_page_indicator(frame)
            if pinch_armed and hovered_idx != -1:
                aps = get_apps_per_page()
                app_path, _, app_name = app_icons[current_page * aps + hovered_idx]
                print(f"Launching: {app_name}")
                launch_app(app_path)
                pinch_armed = False

    # --- Fist: clear hover OR close Task View ---
    elif gesture == 'fist':
        hovered_idx = -1
        if task_view_open:
            hide_all_windows()
            task_view_open = False

    # --- Three fingers: open Task View + tilt to navigate left/right ---
    elif gesture == 'three_Fingers':
        if not task_view_open:
            show_all_windows()
            task_view_open = True

        draw_task_view_indicator(frame)

        angle = get_tilt_angle_from_results(results)
        if angle is not None:
            tilt_angle_buffer.append(angle)
            if len(tilt_angle_buffer) > BUFFER_SIZE:
                tilt_angle_buffer.pop(0)
            smoothed = sum(tilt_angle_buffer) / len(tilt_angle_buffer)

            now = time.time()
            cooldown_ok = (now - last_switch_time) >= SWITCH_COOLDOWN

            if switch_armed and cooldown_ok:
                if smoothed > TILT_TRIGGER:
                    select_choose_window('right')
                    switch_armed = False
                    last_switch_time = now
                elif smoothed < -TILT_TRIGGER:
                    select_choose_window('left')
                    switch_armed = False
                    last_switch_time = now
            else:
                if abs(smoothed) < TILT_REARM:
                    switch_armed = True
    elif gesture == 'four_Fingers':
        now = time.time()
        if close_sign and (now - last_close_time) >= CLOSE_COOLDOWN:
            print('attempting alt f4')
            close_focused_window()
            last_close_time = now
            close_sign = False
    else:
        close_sign = True

    # Re-arm pinch when not pinching
    if gesture != 'pinch':
        pinch_armed = True

    # Re-arm tilt-switch when not showing three fingers
    if gesture != 'three_Fingers':
        switch_armed = True

    cv2.imshow("preview", frame)


load_apps()
cameraStart(processFrame)