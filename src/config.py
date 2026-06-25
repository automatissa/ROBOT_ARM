# -*- coding: utf-8 -*-
"""
Constantes globales du projet Doosan Vision.
Importées depuis tous les modules pour éviter toute duplication.
"""
import os

# --- Paramètres de la caméra ---
CAMERA_INDEX: int = 0  # caméra présélectionnée
CAMERA_SCAN_RANGE: int = 6
CAMERA_PREVIEW_FPS: float = 30.0
CAMERA_PREVIEW_INTERVAL: float = 1.0 / CAMERA_PREVIEW_FPS
CAMERA_PROCESS_FPS: float = 30.0
CAMERA_PROCESS_INTERVAL: float = 1.0 / CAMERA_PROCESS_FPS

# --- Affichage par vue (px) ---
DISPLAY_W: int = 380
DISPLAY_H: int = 285
PREVIEW_W: int = DISPLAY_W * 2
PREVIEW_H: int = DISPLAY_H * 2

# --- Chemin calibration (YAML produit par les scripts du prof) ---
_HERE: str = os.path.dirname(os.path.abspath(__file__))
CALIB_YAML: str = os.path.normpath(
    os.path.join(_HERE, "..", "scripts", "calibration_data_save", "calibration.yaml")
)

# --- Chemin HSV presets JSON ---
HSV_PRESETS_JSON: str = os.path.normpath(os.path.join(_HERE, "hsv_presets.json"))

# --- Chemin calibration table (homographie) ---
PERSPECTIVE_JSON: str = os.path.normpath(os.path.join(_HERE, "table_corners.json"))
PERSPECTIVE_TARGET_W: int = 0  # 0 = auto (max des bords), >0 = forcé
PERSPECTIVE_TARGET_H: int = 0

# --- Thème UI clair ---
BG: str = "#f0f0f0"
BG_PANEL: str = "#e4e4e4"
BG_CELL: str = "#d8d8d8"
BG_SEP: str = "#aaaaaa"
FG: str = "#1a1a1a"
FG_TITLE: str = "#000000"
FG_VAL: str = "#000000"
FG_DIM: str = "#555555"
BG_BTN_ON: str = "#c8c8c8"
BG_BTN_OFF: str = "#b0b0b0"
TROUGH: str = "#bbbbbb"

# --- Préréglages HSV par couleur [H_min, H_max, S_min, S_max, V_min, V_max] ---
HSV_PRESETS: dict[str, list[int]] = {
    "rouge":  [0,   10,  120, 255,  70, 255],
    "vert":   [35,  85,  100, 255,  50, 255],
    "bleu":   [100, 130, 150, 255,  50, 255],
    "jaune":  [20,  40,  100, 255, 100, 255],
    "orange": [11,  22,  150, 255, 100, 255],
    "cyan":   [85, 100,  100, 255,  80, 255],
    "violet": [130, 160,  50, 255,  50, 255],
    "rose":   [145, 175,  60, 255, 150, 255],
    "blanc":  [0,  180,   0,  40,  200, 255],
    "marron": [5,   18,  80, 200,  30, 130],
    "gris":   [0,  180,   0,  50,   80, 200],
}

# --- Couleurs de dessin OpenCV (BGR) ---
DRAW_COLORS_BGR: dict[str, tuple[int, int, int]] = {
    "rouge":  (0,     0,   255),
    "vert":   (0,   255,     0),
    "bleu":   (255,   0,     0),
    "jaune":  (0,   255,   255),
    "orange": (0,   165,   255),
    "cyan":   (255, 255,     0),
    "violet": (255,   0,   255),
    "rose":   (203, 192,   255),
    "blanc":  (200, 200,   200),
    "marron": (19,   69,   139),
    "gris":   (150, 150,   150),
}

# --- Paramètres de détection de formes ---
CANNY_THRESHOLDS: tuple[int, int] = (50, 150)
MIN_CONTOUR_AREA: int = 200
POLYGON_EPSILON: float = 0.03
SQUARE_AR_TOLERANCE: float = 0.10

# --- Paramètres du filtre HSV (morphologie) ---
GAUSSIAN_KERNEL: int = 5
GAUSSIAN_SIGMA: float = 1.5
MORPH_OPEN_KERNEL: int = 3
MORPH_CLOSE_KERNEL: int = 7
MORPH_DILATE_KERNEL: int = 3
MORPH_DILATE_ITERATIONS: int = 2

# --- Paramètres du tracker spatial ---
TRACKER_EMA_ALPHA: float = 0.35
TRACKER_MATCH_DIST: float = 80.0
TRACKER_HISTORY_LEN: int = 8
TRACKER_MIN_VOTES: int = 2
TRACKER_MAX_MISSED: int = 5
TRACKER_MAX_COUNT: int = 20
TRACKER_MAX_AGE_FRAMES: int = 120

# --- Priorité des formes (plus bas = plus spécifique) ---
SHAPE_PRIORITY: dict[str, int] = {
    "circle": 0,
    "square": 1,
    "rectangle": 2,
    "triangle": 3,
    "polygon": 4,
}



# --- Crop asymétrique (fraction de l'image par côté) ---
CROP_LEFT:   float = 0.08
CROP_TOP:    float = 0.08
CROP_RIGHT:  float = 0.00
CROP_BOTTOM: float = 0.00

# --- Taille de police pour les annotations ---
ANNOTATION_FONT_SIZE: float = 0.45
ANNOTATION_FONT_THICKNESS: int = 1

# --- Logging ---
LOG_LEVEL: str = "INFO"
LOG_FORMAT: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
