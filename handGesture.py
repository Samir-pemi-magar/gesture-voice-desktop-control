import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import cv2
import math
import numpy as np
import pickle

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


def detect(frame):
    h, w, _ = frame.shape
    RGB_Frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    MP_Image = mp.Image(image_format=mp.ImageFormat.SRGB, data=RGB_Frame)
    results = detector.detect(MP_Image)

    gesture = None
    points = None
    
    if results.hand_landmarks:
        hand = results.hand_landmarks[0]
        points = [(int(lm.x * w), int(lm.y * h)) for lm in hand]

        relative = get_relative(points)
        if relative is not None:
            gesture = predict_gesture(relative)

            # Draw skeleton
            for start, end in CONNECTIONS:
                cv2.line(frame, points[start], points[end], (255, 255, 255), 2)
            for px, py in points:
                cv2.circle(frame, (px, py), 5, (0, 255, 0), -1)

            # Gesture label
            cv2.putText(frame, f"Gesture: {gesture}", (10, h - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

    return gesture, points, results, frame