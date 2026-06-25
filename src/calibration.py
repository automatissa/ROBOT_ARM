"""
Gestion de la calibration caméra (modèle pinhole standard, OpenCV).

Workflow du prof :
  capture.py  →  process.py  →  calibration.py  →  calibration.yaml
Ce module charge ce YAML et applique la correction à chaque frame.
"""
import logging
import os
from typing import Tuple

import cv2
import numpy as np
import yaml

logger = logging.getLogger(__name__)


class CalibrationManager:
    """
    Charge un fichier calibration.yaml et fournit la correction de distorsion.

    Modes disponibles :
      'none'   — pas de correction
      'radial' — correction radiale seule (p1=p2=0, distorsion tangentielle annulée)
      'full'   — correction complète (k1, k2, p1, p2, k3)
    """

    def __init__(self, yaml_path: str) -> None:
        self.K: np.ndarray | None = None
        self.D: np.ndarray | None = None
        self.calib_w: int = 1280
        self.calib_h: int = 720
        self.status: str = "Non chargee"
        self._cache: Tuple[int, int, str, np.ndarray, np.ndarray] | None = None
        self._cache_full: Tuple[int, int, str, np.ndarray, np.ndarray, Tuple[int, int, int, int]] | None = None
        self._load(yaml_path)

    # ----------------------------------------------------------------- load --
    def _load(self, path: str) -> None:
        path = os.path.normpath(path)
        if not os.path.exists(path):
            self.status = f"Non trouvee: {os.path.basename(path)}"
            logger.warning("Fichier de calibration introuvable: %s", path)
            return
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f)

            self.K = np.array(data["camera_matrix"], dtype=np.float64)
            self.D = np.array(data["dist_coeff"], dtype=np.float64).flatten()
            self.calib_w = int(data.get("image_width", 1280))
            self.calib_h = int(data.get("image_height", 720))
            self.status = f"OK  {self.calib_w}x{self.calib_h}"
            logger.info("Calibration chargée: %s", self.status)
        except KeyError as exc:
            self.status = f"Cle manquante: {exc}"
            logger.error("Clé manquante dans le YAML: %s", exc)
        except Exception as exc:
            self.status = f"Erreur: {exc}"
            logger.error("Erreur lecture calibration: %s", exc)

    @property
    def loaded(self) -> bool:
        """True si la matrice caméra a été chargée avec succès."""
        return self.K is not None

    # ------------------------------------------------------------- scale_K --
    def _scale_K(self, frame_w: int, frame_h: int) -> np.ndarray:
        """Redimensionne K si la résolution caméra ≠ résolution de calibration."""
        K = self.K.copy()
        sx = frame_w / self.calib_w
        sy = frame_h / self.calib_h
        K[0, 0] *= sx
        K[0, 2] *= sx
        K[1, 1] *= sy
        K[1, 2] *= sy
        return K

    # -------------------------------------------------------------- get_maps --
    def get_maps(
        self, h: int, w: int, mode: str
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Retourne (map1, map2) prêts pour cv2.remap.
        Résultat mis en cache — recalcul uniquement si h/w/mode changent.
        """
        if self._cache is not None:
            ch, cw, cm, m1, m2 = self._cache
            if ch == h and cw == w and cm == mode:
                return m1, m2

        K = self._scale_K(w, h)
        D = self.D.copy()
        if mode == "radial":
            D[2:4] = 0.0

        new_K, _ = cv2.getOptimalNewCameraMatrix(K, D, (w, h), 0, (w, h))
        m1, m2 = cv2.initUndistortRectifyMap(
            K, D, None, new_K, (w, h), cv2.CV_16SC2
        )
        self._cache = (h, w, mode, m1, m2)
        return m1, m2

    # --------------------------------------------------------------- apply --
    def apply(self, frame: np.ndarray, mode: str) -> np.ndarray:
        """
        Corrige la distorsion d'un frame BGR et retourne l'image corrigée.
        Si mode='none' ou calibration non chargée, retourne une copie brute.
        """
        if mode == "none" or not self.loaded:
            return frame.copy()
        h, w = frame.shape[:2]
        m1, m2 = self.get_maps(h, w, mode)
        return cv2.remap(
            frame, m1, m2,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
        )

    # -------------------------------------------------------- _get_maps_alpha1 --
    def _get_maps_alpha1(
        self, h: int, w: int, mode: str
    ) -> Tuple[np.ndarray, np.ndarray, Tuple[int, int, int, int]]:
        """Maps + ROI avec alpha=1 (tous les pixels source préservés)."""
        if self._cache_full is not None:
            ch, cw, cm, m1, m2, roi = self._cache_full
            if ch == h and cw == w and cm == mode:
                return m1, m2, roi

        K = self._scale_K(w, h)
        D = self.D.copy()
        if mode == "radial":
            D[2:4] = 0.0

        new_K, roi = cv2.getOptimalNewCameraMatrix(K, D, (w, h), 1, (w, h))
        m1, m2 = cv2.initUndistortRectifyMap(
            K, D, None, new_K, (w, h), cv2.CV_16SC2
        )
        self._cache_full = (h, w, mode, m1, m2, roi)
        return m1, m2, roi

    # ---------------------------------------------------------- apply_cropped --
    def apply_cropped(
        self, frame: np.ndarray, mode: str
    ) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
        """
        Undistort (alpha=1) puis crop au ROI valide.
        Retourne (crop_bgr, roi) où roi = (x, y, rw, rh).
        """
        if mode == "none" or not self.loaded:
            h, w = frame.shape[:2]
            return frame.copy(), (0, 0, w, h)
        h, w = frame.shape[:2]
        m1, m2, roi = self._get_maps_alpha1(h, w, mode)
        undist = cv2.remap(
            frame, m1, m2,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
        )
        x, y, rw, rh = roi
        return undist[y:y + rh, x:x + rw], roi

    def invalidate_cache(self) -> None:
        """Invalide le cache (à appeler quand le mode change depuis l'UI)."""
        self._cache = None
        self._cache_full = None
