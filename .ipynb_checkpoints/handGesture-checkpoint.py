import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from cameraTest import cameraStart
from appLauncher import get_installed_apps, get_app_icon
import cv2
import math
import numpy as np
import pickle
import subprocess

# --- Load gesture model ---
with open('gesture_model.pkl', 'rb') as f:
    pipeline, le = pickle.load(f)

CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),
    (0,5),(5,6),(6,7),(7,8),
    (0,9),(9,10),(10,11),(11,12),
    (0,13),(13,14),(14,15),(15,16),
    (0,17),(17,18),(18,19),(19,20),
    (5,9),(9,13),(13,17)
]

base_options = python.BaseOptions(model_asset_path="hand_landmarker.task")
options = vision.HandLandmarkerOptions(base_options=base_options, num_hands=1)
detector = vision.HandLandmarker.create_from_options(options)

# --- Load apps ---
apps = get_installed_apps()
app_icons = []
for app in apps:
    icon, name = get_app_icon(app)
    if icon is None:
        continue
    app_icons.append((app, icon, name))

# --- State ---
current_page = 0
angle_buffer = []
gesture_armed = True
show_grid = False
cursor_x, cursor_y = 0, 0
hovered_idx = -1
pinch_armed = True

TILT_TRIGGER = 25
TILT_REARM = 10
BUFFER_SIZE = 5

# --- Layout constants ---
ICON_SIZE = 64
SPACING_X = 130
SPACING_Y = 90
START_X = 10
START_Y = 10


def get_relative(points):
    wrist = points[0]
    mid_mcp = points[9]
    ref_dist = math.dist(wrist, mid_mcp)
    if ref_dist == 0:
        return None
    return [
        (round((x - wrist[0]) / ref_dist, 4), round((y - wrist[1]) / ref_dist, 4))
        for x, y in points
    ]


def predict_gesture(relative):
    flat = [coord for point in relative for coord in point]
    pred = pipeline.predict([flat])[0]
    return le.inverse_transform([pred])[0]


def launch_app(lnk_path):
    try:
        subprocess.Popen(['cmd', '/c', 'start', '', lnk_path], shell=True)
    except Exception as e:
        print(f"Failed to launch: {e}")


def processFrame(frame):
    global current_page, angle_buffer, gesture_armed
    global show_grid, cursor_x, cursor_y, hovered_idx, pinch_armed

    h, w, _ = frame.shape
    icons_per_row = max(1, (w - START_X) // SPACING_X)
    rows_per_page = max(1, (h - START_Y) // SPACING_Y)
    apps_per_page = icons_per_row * rows_per_page
    max_page = max(0, (len(app_icons) - 1) // apps_per_page) if app_icons else 0
    page_apps = app_icons[current_page * apps_per_page:(current_page + 1) * apps_per_page]

    RGB_Frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    MP_Image = mp.Image(image_format=mp.ImageFormat.SRGB, data=RGB_Frame)
    results = detector.detect(MP_Image)

    gesture = None

    if results.hand_landmarks:
        for i, hand in enumerate(results.hand_landmarks):
            points = [(int(lm.x * w), int(lm.y * h)) for lm in hand]

            relative = get_relative(points)
            if relative is None:
                continue

            gesture = predict_gesture(relative)

            # Draw skeleton
            for start, end in CONNECTIONS:
                cv2.line(frame, points[start], points[end], (255, 255, 255), 2)
            for px, py in points:
                cv2.circle(frame, (px, py), 5, (0, 255, 0), -1)

            # --- open_palm: show grid + tilt to page ---
            if gesture == 'open_palm':
                show_grid = True
                pinch_armed = True

                hand_3d = results.hand_world_landmarks[i]
                dx = hand_3d[9].x - hand_3d[0].x
                dy = hand_3d[9].y - hand_3d[0].y
                angle = math.degrees(math.atan2(dx, -dy))
                angle_buffer.append(angle)
                if len(angle_buffer) > BUFFER_SIZE:
                    angle_buffer.pop(0)
                smoothed_angle = sum(angle_buffer) / len(angle_buffer)

                if gesture_armed:
                    if smoothed_angle > TILT_TRIGGER:
                        current_page = min(current_page + 1, max_page)
                        gesture_armed = False
                    elif smoothed_angle < -TILT_TRIGGER:
                        current_page = max(current_page - 1, 0)
                        gesture_armed = False
                else:
                    if abs(smoothed_angle) < TILT_REARM:
                        gesture_armed = True

            # --- fist: hide grid ---
            elif gesture == 'fist':
                show_grid = False
                angle_buffer.clear()
                hovered_idx = -1

            # --- point: move cursor using index fingertip (landmark 8) ---
            elif gesture == 'point':
                cursor_x, cursor_y = points[8]
                hovered_idx = -1
                if show_grid:
                    for idx, _ in enumerate(page_apps):
                        col = idx % icons_per_row
                        row = idx // icons_per_row
                        x_off = START_X + col * SPACING_X
                        y_off = START_Y + row * SPACING_Y
                        if x_off <= cursor_x <= x_off + ICON_SIZE and y_off <= cursor_y <= y_off + ICON_SIZE:
                            hovered_idx = idx
                            break

            # --- pinch: launch hovered app ---
            elif gesture == 'pinch':
                if pinch_armed and hovered_idx != -1 and show_grid:
                    app_path, _, app_name = page_apps[hovered_idx]
                    print(f"Launching: {app_name}")
                    launch_app(app_path)
                    pinch_armed = False
            
            # Re-arm pinch when not pinching
            if gesture != 'pinch':
                pinch_armed = True

            # Gesture label on screen
            cv2.putText(frame, f"Gesture: {gesture}", (10, h - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

    # --- Draw app grid ---
    if show_grid:
        for idx, (app, icon, name) in enumerate(page_apps):
            if not icon:
                continue
            col = idx % icons_per_row
            row = idx // icons_per_row
            x_off = START_X + col * SPACING_X
            y_off = START_Y + row * SPACING_Y

            if y_off + ICON_SIZE > h or x_off + ICON_SIZE > w:
                continue

            icon_rgba = np.array(icon.convert('RGBA'))
            icon_rgb = icon_rgba[:, :, :3]
            alpha = icon_rgba[:, :, 3:] / 255.0
            icon_cv = cv2.cvtColor(icon_rgb, cv2.COLOR_RGB2BGR)

            region = frame[y_off:y_off+ICON_SIZE, x_off:x_off+ICON_SIZE]
            frame[y_off:y_off+ICON_SIZE, x_off:x_off+ICON_SIZE] = (
                icon_cv * alpha + region * (1 - alpha)
            ).astype(np.uint8)

            # Highlight hovered app
            if idx == hovered_idx:
                cv2.rectangle(frame, (x_off, y_off),
                              (x_off + ICON_SIZE, y_off + ICON_SIZE), (0, 255, 255), 2)

            cv2.putText(frame, name, (x_off, y_off + ICON_SIZE + 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.3, (237, 214, 125), 1, cv2.LINE_AA)

        # Draw cursor
        if gesture == 'point':
            cv2.circle(frame, (cursor_x, cursor_y), 10, (0, 255, 255), 2)
            cv2.circle(frame, (cursor_x, cursor_y), 2, (0, 255, 255), -1)

        # Page indicator
        cv2.putText(frame, f"Page {current_page + 1}/{max_page + 1}", (w - 120, h - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    cv2.imshow("preview", frame)


cameraStart(processFrame)