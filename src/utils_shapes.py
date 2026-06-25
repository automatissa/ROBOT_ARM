"""
Détection de formes géométriques via Canny + approximation polygonale.
Module partagé — NE PAS MODIFIER sans demande explicite.
"""
from typing import Any

import cv2
import numpy as np

from config import CANNY_THRESHOLDS, MIN_CONTOUR_AREA, POLYGON_EPSILON, SQUARE_AR_TOLERANCE


def detect_shapes_with_canny(mask: np.ndarray) -> list[dict[str, Any]]:
    """
    Détecte les formes (triangle, carré, cercle, etc.) dans un masque binaire
    et calcule leur centre via la bounding box.

    Args:
        mask: Masque binaire 8-bit (0 ou 255).

    Returns:
        Liste de dictionnaires avec clés:
            - 'type': str (triangle, square, rectangle, circle, polygon)
            - 'center': tuple[int, int] (cx, cy)
            - 'contour': np.ndarray (contour OpenCV)
    """
    low, high = CANNY_THRESHOLDS
    edges = cv2.Canny(mask, low, high)

    contours, _ = cv2.findContours(
        edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    detected: list[dict[str, Any]] = []

    for cnt in contours:
        if cv2.contourArea(cnt) < MIN_CONTOUR_AREA:
            continue

        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, POLYGON_EPSILON * peri, True)
        vertices = len(approx)

        x, y, w, h = cv2.boundingRect(approx)
        cx = x + w // 2
        cy = y + h // 2

        if vertices == 3:
            shape_type = "triangle"
        elif vertices == 4:
            ar = w / float(h)
            shape_type = "square" if (1.0 - SQUARE_AR_TOLERANCE) <= ar <= (1.0 + SQUARE_AR_TOLERANCE) else "rectangle"
        elif vertices > 6:
            shape_type = "circle"
        else:
            shape_type = "polygon"

        detected.append({
            "type": shape_type,
            "center": (cx, cy),
            "contour": cnt,
        })

    return detected
