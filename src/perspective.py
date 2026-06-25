"""
Correction de perspective par homographie (table plane).
    4 coins cliqués → cv2.getPerspectiveTransform → warp + transform centroïdes.
"""
import json
import logging
import math
import os
from typing import Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class PerspectiveManager:
    """
    Gère l'homographie table : calibrage 4 coins, warp image, transform points.

    JSON stocke : "corners" (4× [x,y]), "table_w", "table_h".
    """

    def __init__(self, json_path: str,
                 target_w: int = 0, target_h: int = 0) -> None:
        self.json_path: str = json_path
        self.target_w: int = target_w
        self.target_h: int = target_h
        self.corners: list[list[float]] = []
        self.H: np.ndarray | None = None
        self.H_inv: np.ndarray | None = None
        self.table_w: int = 0
        self.table_h: int = 0
        self._load()

    # ----------------------------------------------------------------- load/save --
    def _load(self) -> None:
        path = os.path.normpath(self.json_path)
        if not os.path.exists(path):
            logger.info("Pas de calibration table trouvée (%s)", os.path.basename(path))
            return
        try:
            with open(path, "r") as f:
                data = json.load(f)
            self.corners = data["corners"]
            self.table_w = data.get("table_w", 0)
            self.table_h = data.get("table_h", 0)
            self._compute()
            logger.info("Calibration table chargée: %dx%d px", self.table_w, self.table_h)
        except Exception as exc:
            logger.warning("Erreur lecture calibration table: %s", exc)

    def save(self) -> None:
        try:
            with open(self.json_path, "w") as f:
                json.dump({
                    "corners": self.corners,
                    "table_w": self.table_w,
                    "table_h": self.table_h,
                }, f, indent=2)
            logger.info("Calibration table sauvegardée: %dx%d px", self.table_w, self.table_h)
        except Exception as exc:
            logger.error("Erreur sauvegarde calibration table: %s", exc)

    # ---------------------------------------------------------------- compute --
    def set_corners(self, corners: list[Tuple[float, float]]) -> None:
        """Définit les 4 coins dans l'ordre TL, TR, BR, BL."""
        self.corners = [[float(x), float(y)] for (x, y) in corners]
        self.table_w = 0  # force recalcul dimensions
        self.table_h = 0
        self._compute()
        self.save()

    def _compute(self) -> None:
        """Calcule H à partir des 4 coins source vers un rectangle destination."""
        if len(self.corners) != 4:
            return

        src = np.array(self.corners, dtype=np.float32)

        if self.table_w <= 0 or self.table_h <= 0:
            # distances des 4 bords
            w_top = math.hypot(src[1][0] - src[0][0], src[1][1] - src[0][1])
            w_bot = math.hypot(src[2][0] - src[3][0], src[2][1] - src[3][1])
            h_lef = math.hypot(src[3][0] - src[0][0], src[3][1] - src[0][1])
            h_rig = math.hypot(src[2][0] - src[1][0], src[2][1] - src[1][1])
            # dimensions cibles forcées ou auto (max pour englober toute la surface)
            if self.target_w > 0 and self.target_h > 0:
                self.table_w = self.target_w
                self.table_h = self.target_h
            else:
                self.table_w = int(max(w_top, w_bot))
                self.table_h = int(max(h_lef, h_rig))

        dst = np.array([
            [0, 0],
            [self.table_w - 1, 0],
            [self.table_w - 1, self.table_h - 1],
            [0, self.table_h - 1],
        ], dtype=np.float32)

        self.H = cv2.getPerspectiveTransform(src, dst)
        self.H_inv = cv2.getPerspectiveTransform(dst, src)

    # ----------------------------------------------------------------- apply --
    @property
    def calibrated(self) -> bool:
        return self.H is not None

    def warp(self, frame: np.ndarray) -> np.ndarray:
        """Applique la perspective → retourne l'image rectifiée."""
        if not self.calibrated:
            return frame.copy()
        return cv2.warpPerspective(
            frame, self.H, (self.table_w, self.table_h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
        )

    def transform_point(self, cx: float, cy: float) -> Tuple[float, float]:
        """Transforme un centroïde image → coordonnées table rectifiée."""
        if not self.calibrated:
            return cx, cy
        pt = np.array([[[cx, cy]]], dtype=np.float32)
        result = cv2.perspectiveTransform(pt, self.H)
        return float(result[0][0][0]), float(result[0][0][1])

    def draw_corners(self, img: np.ndarray) -> None:
        """Dessine les 4 coins + quadrilatère sur l'image (feedback visuel)."""
        if len(self.corners) < 1:
            return
        _MAGENTA = (255, 0, 255)
        _YELLOW = (0, 255, 255)
        pts = [(int(x), int(y)) for (x, y) in self.corners]

        for i, (x, y) in enumerate(pts):
            cv2.circle(img, (x, y), 8, _MAGENTA, 2)
            cv2.circle(img, (x, y), 5, _MAGENTA, -1)
            cv2.putText(img, str(i + 1), (x + 12, y - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, _MAGENTA, 2)

        if len(pts) >= 2:
            for i in range(len(pts) - 1):
                cv2.line(img, pts[i], pts[i + 1], _YELLOW, 2)
        if len(pts) == 4:
            cv2.line(img, pts[3], pts[0], _YELLOW, 2)
