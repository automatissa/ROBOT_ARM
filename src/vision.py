"""
Pipeline de vision : filtrage HSV, morphologie, détection, repère local.
Règle : toute détection de formes passe par utils_shapes.detect_shapes_with_canny.
"""
import logging
import math
import time
from typing import Tuple

import cv2
import numpy as np

from config import (
    DRAW_COLORS_BGR,
    GAUSSIAN_KERNEL,
    GAUSSIAN_SIGMA,
    MORPH_OPEN_KERNEL,
    MORPH_CLOSE_KERNEL,
    MORPH_DILATE_KERNEL,
    MORPH_DILATE_ITERATIONS,
    ANNOTATION_FONT_SIZE,
    ANNOTATION_FONT_THICKNESS,
)
from utils_shapes import detect_shapes_with_canny
from detection_result import ShapeDetection, DetectionFrame

logger = logging.getLogger(__name__)

_CYAN: Tuple[int, int, int] = (0, 255, 255)
_RED: Tuple[int, int, int] = (0, 0, 255)
_GREEN: Tuple[int, int, int] = (0, 255, 0)


def build_mask(
    frame_bgr: np.ndarray,
    color: str,
    h_min: int, h_max: int,
    s_min: int, s_max: int,
    v_min: int, v_max: int,
) -> np.ndarray:
    """
    Crée un masque binaire à partir d'un frame BGR et de seuils HSV.

    Étapes :
      1. Gaussien (réduit bruit)
      2. BGR → HSV
      3. inRange (double plage pour le rouge)
      4. MORPH_OPEN  (supprime bruit résiduel)
      5. MORPH_CLOSE (comble les trous internes)
      6. dilate      (gonfle les petits blobs)
    """
    work = cv2.GaussianBlur(
        frame_bgr, (GAUSSIAN_KERNEL, GAUSSIAN_KERNEL), GAUSSIAN_SIGMA
    )
    hsv = cv2.cvtColor(work, cv2.COLOR_BGR2HSV)

    if color == "rouge":
        mask = (
            cv2.inRange(hsv, np.array([0,   s_min, v_min]),
                             np.array([h_max, s_max, v_max]))
            |
            cv2.inRange(hsv, np.array([h_min, s_min, v_min]),
                             np.array([180,  s_max, v_max]))
        )
    else:
        mask = cv2.inRange(
            hsv,
            np.array([h_min, s_min, v_min]),
            np.array([h_max, s_max, v_max]),
        )

    refined = cv2.morphologyEx(
        mask, cv2.MORPH_OPEN,
        np.ones((MORPH_OPEN_KERNEL, MORPH_OPEN_KERNEL), np.uint8),
    )
    refined = cv2.morphologyEx(
        refined, cv2.MORPH_CLOSE,
        np.ones((MORPH_CLOSE_KERNEL, MORPH_CLOSE_KERNEL), np.uint8),
    )
    refined = cv2.dilate(
        refined,
        np.ones((MORPH_DILATE_KERNEL, MORPH_DILATE_KERNEL), np.uint8),
        iterations=MORPH_DILATE_ITERATIONS,
    )
    return refined


def _compute_frame(
    cnt: np.ndarray,
) -> Tuple[Tuple[float, float], Tuple[float, float], float, float, float]:
    """
    Construit le repère local via minAreaRect.

    Retourne (x_dir, y_dir, half_short, half_long, theta_deg) où :
      - X (rouge)  = axe court
      - Y (vert)   = axe long
      - theta      = angle de X depuis l'horizontal image, normalisé [-90, 90]°
    """
    (_, _), (w, h), angle = cv2.minAreaRect(cnt)
    a = math.radians(angle)
    cos_a, sin_a = math.cos(a), math.sin(a)

    dir_w = (cos_a, sin_a)
    dir_h = (-sin_a, cos_a)

    if w <= h:
        x_dir, y_dir = dir_w, dir_h
        half_short, half_long = w / 2, h / 2
        theta = angle
    else:
        x_dir, y_dir = dir_h, dir_w
        half_short, half_long = h / 2, w / 2
        theta = angle + 90.0

    theta = ((theta + 90.0) % 180.0) - 90.0
    return x_dir, y_dir, half_short, half_long, round(theta, 1)


def _draw_frame(
    img: np.ndarray,
    cx: int, cy: int,
    x_dir: Tuple[float, float],
    y_dir: Tuple[float, float],
    half_short: float,
    half_long: float,
) -> None:
    """Dessine les axes X (rouge) et Y (vert) depuis le centroïde."""
    tip_x = (int(cx + x_dir[0] * half_short), int(cy + x_dir[1] * half_short))
    tip_y = (int(cx + y_dir[0] * half_long),  int(cy + y_dir[1] * half_long))

    cv2.arrowedLine(img, (cx, cy), tip_x, _RED,   2, tipLength=0.25)
    cv2.arrowedLine(img, (cx, cy), tip_y, _GREEN, 2, tipLength=0.25)

    cv2.putText(img, "X", (tip_x[0] + 4, tip_x[1] - 4),
                cv2.FONT_HERSHEY_SIMPLEX, ANNOTATION_FONT_SIZE, _RED, ANNOTATION_FONT_THICKNESS)
    cv2.putText(img, "Y", (tip_y[0] + 4, tip_y[1] - 4),
                cv2.FONT_HERSHEY_SIMPLEX, ANNOTATION_FONT_SIZE, _GREEN, ANNOTATION_FONT_THICKNESS)


def _draw_image_frame(img: np.ndarray) -> None:
    """Dessine le repère image (origine pixel, axes X→/Y↓, dimensions max)."""
    h, w = img.shape[:2]
    # Origine en haut-gauche (l'image reçue est déjà croppée, (0,0) = coin visible)
    ox, oy = int(w * 0.012), int(h * 0.018)
    length = 48

    # Axe X (rouge) → droite
    cv2.arrowedLine(img, (ox, oy), (ox + length, oy),
                    _RED, 2, tipLength=0.35)
    cv2.putText(img, "X", (ox + length + 4, oy + 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, _RED, 2)

    # Axe Y (vert) → bas
    cv2.arrowedLine(img, (ox, oy), (ox, oy + length),
                    _GREEN, 2, tipLength=0.35)
    cv2.putText(img, "Y", (ox + 6, oy + length + 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, _GREEN, 2)

    # Point origine
    cv2.circle(img, (ox, oy), 4, (255, 255, 255), -1)
    cv2.circle(img, (ox, oy), 5, (0, 0, 0), 1)
    cv2.putText(img, "O(0,0)", (ox - 4, oy - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)

    # Dimensions image (coin haut-droite)
    dim_text = f"{w} x {h} px"
    (tw, th), _ = cv2.getTextSize(dim_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
    # Fond noir derrière le texte pour lisibilité
    cv2.rectangle(img, (w - tw - 14, 2), (w - 4, th + 8), (0, 0, 0), -1)
    cv2.putText(img, dim_text, (w - tw - 10, th + 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, _CYAN, 2)


def detect_and_annotate(
    undist: np.ndarray,
    refined: np.ndarray,
    color: str,
) -> Tuple[np.ndarray, list[str], DetectionFrame]:
    """
    Détecte les formes, ajuste géométriquement,
    calcule le centroïde (moments d'inertie) et trace le repère local.

    Retourne (image_annotée, logs_texte, DetectionFrame).
    """
    shapes = detect_shapes_with_canny(refined)
    result = undist.copy()
    dc = DRAW_COLORS_BGR.get(color, (0, 255, 0))
    logs: list[str] = []
    detections: list[ShapeDetection] = []

    for s in shapes:
        cx, cy = s["center"]
        stype = s["type"]
        cnt = s["contour"]
        h, w = result.shape[:2]

        M = cv2.moments(cnt)
        if M["m00"] > 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])

        x_dir, y_dir, half_short, half_long, theta = _compute_frame(cnt)

        if stype == "circle":
            if len(cnt) >= 5:
                cv2.ellipse(result, cv2.fitEllipse(cnt), dc, 2)
            else:
                (ex, ey), er = cv2.minEnclosingCircle(cnt)
                cv2.circle(result, (int(ex), int(ey)), int(er), dc, 2)
        else:
            box = cv2.boxPoints(cv2.minAreaRect(cnt)).astype(np.int32)
            cv2.drawContours(result, [box], 0, dc, 2)

        _draw_frame(result, cx, cy, x_dir, y_dir, half_short, half_long)

        cv2.line(result, (cx - 12, cy), (cx + 12, cy), _CYAN, 1)
        cv2.line(result, (cx, cy - 12), (cx, cy + 12), _CYAN, 1)
        cv2.circle(result, (cx, cy), 5, dc, -1)
        cv2.circle(result, (cx, cy), 8, (255, 255, 255), 1)

        label = f"{stype} ({cx},{cy}) {theta}\u00b0"
        (tw, th), bl = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2
        )
        # Au-dessus du centroïde, centré horizontalement, avec fond opaque
        tx = max(4, min(cx - tw // 2, w - tw - 4))
        ty = max(cy - 28, th + 8)
        cv2.rectangle(result, (tx - 3, ty - th - 3),
                      (tx + tw + 3, ty + bl + 2), (0, 0, 0), -1)
        cv2.putText(result, label, (tx, ty),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        logs.append(f"{stype}@({cx},{cy},{theta})")
        detections.append(ShapeDetection(
            shape_type=stype,
            cx=float(cx),
            cy=float(cy),
            theta=theta,
            color=color,
        ))

    h, w = result.shape[:2]
    frame_result = DetectionFrame(
        detections=detections,
        timestamp=time.time(),
        frame_width=w,
        frame_height=h,
    )

    return result, logs, frame_result
