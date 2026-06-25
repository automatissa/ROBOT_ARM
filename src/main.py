"""
Point d'entrée — Doosan Vision.
Mode : caméra live uniquement.
"""
import json
import logging
import os
import threading
import time
from collections import Counter, deque
from typing import Any

import cv2
import numpy as np
import tkinter as tk
import tkinter.ttk as ttk
from PIL import Image, ImageTk

from config import (
    DISPLAY_W, DISPLAY_H, PREVIEW_W, PREVIEW_H, CALIB_YAML,
    BG, BG_PANEL, BG_CELL, BG_SEP,
    FG, FG_TITLE, FG_VAL, FG_DIM, BG_BTN_ON, BG_BTN_OFF, TROUGH,
    HSV_PRESETS, HSV_PRESETS_JSON,
    TRACKER_EMA_ALPHA, TRACKER_MATCH_DIST, TRACKER_HISTORY_LEN,
    TRACKER_MIN_VOTES, TRACKER_MAX_MISSED, TRACKER_MAX_COUNT, TRACKER_MAX_AGE_FRAMES,
    SHAPE_PRIORITY,
    CAMERA_SCAN_RANGE, CAMERA_PREVIEW_INTERVAL, CAMERA_PROCESS_INTERVAL,
    CAMERA_INDEX,
    CROP_LEFT, CROP_TOP, CROP_RIGHT, CROP_BOTTOM,
    PERSPECTIVE_JSON, PERSPECTIVE_TARGET_W, PERSPECTIVE_TARGET_H,
)
from calibration import CalibrationManager
from vision import build_mask, detect_and_annotate, _draw_image_frame
from perspective import PerspectiveManager

logger = logging.getLogger(__name__)


class DoosanVisionApp:
    """Application principale de vision pour robot Doosan."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("ARM Vision — ISTY · UVSQ · Paris-Saclay")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)

        self.running: bool = False
        self._preview_mode: bool = True  # démarre en mode preview simple
        self.cap: cv2.VideoCapture | None = None
        self.calib = CalibrationManager(CALIB_YAML)
        self.perspective = PerspectiveManager(
            PERSPECTIVE_JSON, PERSPECTIVE_TARGET_W, PERSPECTIVE_TARGET_H
        )  # homographie table
        self._calib_table: bool = False  # mode clic 4 coins actif
        self._calib_clicks: list[tuple[float, float]] = []  # clics accumulés
        self._cameras: list[int] = []
        self._cells: list[tk.Frame] = []  # refs cellules 4 vues pour hide/show
        self._preview_cap: cv2.VideoCapture | None = None
        self._preview_on: bool = False
        self._preview_pending: bool = False
        self._preview_lock = threading.Lock()

        self._trackers: list[dict[str, Any]] = []
        self._trackers_lock = threading.Lock()
        self._last_detection: Any = None

        self._frame_count: int = 0

        # --- marqueur clic (coordonnées pixel sur vue Detection) ---
        self._marker_visible: bool = False
        self._marker_cx: float = 0.0
        self._marker_cy: float = 0.0
        self._crop_w: int = 0
        self._crop_h: int = 0

        self._load_hsv_presets()

        self.cam_index: tk.IntVar = tk.IntVar(value=CAMERA_INDEX)
        self.flip_var: tk.BooleanVar = tk.BooleanVar(value=True)
        self.undist_mode: tk.StringVar = tk.StringVar(value="full")
        self.color_var: tk.StringVar = tk.StringVar(value="rouge")
        self.h_min: tk.IntVar = tk.IntVar(value=0)
        self.h_max: tk.IntVar = tk.IntVar(value=10)
        self.s_min: tk.IntVar = tk.IntVar(value=120)
        self.s_max: tk.IntVar = tk.IntVar(value=255)
        self.v_min: tk.IntVar = tk.IntVar(value=70)
        self.v_max: tk.IntVar = tk.IntVar(value=255)

        self._build_ui()
        self._set_ui_preview()  # affiche le mode preview par défaut
        self._detect_cameras()
        self._bind_shortcuts()

    # ------------------------------------------------------------ HSV presets --
    def _load_hsv_presets(self) -> None:
        """Charge les presets HSV depuis JSON si disponible, sinon utilise les valeurs par défaut."""
        if os.path.exists(HSV_PRESETS_JSON):
            try:
                with open(HSV_PRESETS_JSON, "r") as f:
                    presets = json.load(f)
                HSV_PRESETS.clear()
                HSV_PRESETS.update(presets)
                logger.info("Presets HSV chargés depuis %s", HSV_PRESETS_JSON)
            except Exception as exc:
                logger.warning("Erreur lecture HSV JSON, valeurs par défaut: %s", exc)

    def _save_hsv_presets(self) -> None:
        """Sauvegarde les presets HSV actuels dans le JSON."""
        try:
            with open(HSV_PRESETS_JSON, "w") as f:
                json.dump(HSV_PRESETS, f, indent=2)
            logger.info("Presets HSV sauvegardés dans %s", HSV_PRESETS_JSON)
        except Exception as exc:
            logger.error("Erreur sauvegarde HSV JSON: %s", exc)

    # --------------------------------------------------------------- shortcuts --
    def _bind_shortcuts(self) -> None:
        self.root.bind("<space>", lambda e: self.toggle())
        self.root.bind("<Return>", lambda e: self.toggle())
        self.root.bind("<F1>", lambda e: self._cycle_undist_mode(-1))
        self.root.bind("<F2>", lambda e: self._cycle_undist_mode(1))
        self.root.bind("<Control-s>", lambda e: self._save_hsv_presets())
        for i in range(10):
            self.root.bind(f"<Key-{i}>", lambda e, idx=i: self._set_color_by_index(idx))

    def _cycle_undist_mode(self, direction: int) -> None:
        modes = ["none", "radial", "full"]
        current = modes.index(self.undist_mode.get())
        next_mode = modes[(current + direction) % len(modes)]
        self.undist_mode.set(next_mode)
        self.calib.invalidate_cache()

    def _set_color_by_index(self, index: int) -> None:
        colors = list(HSV_PRESETS.keys())
        if index < len(colors):
            self.color_var.set(colors[index])
            self._on_color_change()

    # ================================================================ UI ===
    def _build_ui(self) -> None:
        paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL,
                               bg=BG, sashwidth=4, sashrelief=tk.FLAT, bd=0)
        paned.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(paned, bg=BG_PANEL, width=240)
        left.pack_propagate(False)
        paned.add(left, minsize=220)
        self._build_controls(left)

        right = tk.Frame(paned, bg=BG)
        paned.add(right, minsize=500)
        self.img_labels: dict[str, tk.Label] = {}
        self._cells: list[tk.Frame] = []
        for title, row, col in [("Brut", 0, 0), ("Radiale", 0, 1),
                                ("Masque", 1, 0), ("Detection", 1, 1)]:
            cell = tk.Frame(right, bg=BG_CELL, bd=1, relief=tk.FLAT)
            cell.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
            tk.Label(cell, text=title, bg=BG_CELL, fg=FG_DIM,
                     font=("Courier", 8)).pack(side=tk.TOP, anchor="w", padx=4)
            lbl = tk.Label(cell, bg="#000000")
            lbl.pack()
            self.img_labels[title] = lbl
            self._cells.append(cell)
        self.img_labels["Detection"].bind("<Button-1>", self._on_detection_click)
        for i in range(2):
            right.grid_rowconfigure(i, weight=1)
            right.grid_columnconfigure(i, weight=1)

        # --- label preview plein cadre (mode preview simple) ---
        self._preview_lbl = tk.Label(right, bg="#000000")
        self._preview_lbl.grid(row=0, column=0, rowspan=2, columnspan=2,
                               padx=2, pady=2, sticky="nsew")
        self._preview_lbl.bind("<Button-1>", self._on_preview_click)

        bar = tk.Frame(right, bg=BG_PANEL, pady=2)
        bar.grid(row=2, column=0, columnspan=2, sticky="ew")
        tk.Label(bar, text="XY:", bg=BG_PANEL, fg=FG_DIM,
                 font=("Courier", 8, "bold")).pack(side=tk.LEFT, padx=6)
        self.log_lbl = tk.Label(bar, text="-- aucun objet --",
                                bg=BG_PANEL, fg=FG, font=("Courier", 9))
        self.log_lbl.pack(side=tk.LEFT)

    def _section(self, parent: tk.Frame, text: str) -> None:
        tk.Frame(parent, bg=BG_SEP, height=1).pack(fill=tk.X, pady=(8, 0))
        tk.Label(parent, text=text, bg=BG_PANEL, fg=FG_TITLE,
                 font=("Courier", 8, "bold")).pack(anchor="w", padx=6, pady=(2, 0))

    def _slider(self, parent: tk.Frame, text: str, var: tk.IntVar,
                lo: int, hi: int, step: int = 1) -> None:
        row = tk.Frame(parent, bg=BG_PANEL)
        row.pack(fill=tk.X, padx=6, pady=1)
        tk.Label(row, text=f"{text:<9}", bg=BG_PANEL, fg=FG,
                 font=("Courier", 7), width=9, anchor="w").pack(side=tk.LEFT)
        tk.Label(row, textvariable=var, bg=BG_PANEL, fg=FG_VAL,
                 font=("Courier", 7), width=4).pack(side=tk.RIGHT)
        tk.Scale(row, variable=var, from_=lo, to=hi, resolution=step,
                 orient=tk.HORIZONTAL, bg=BG_PANEL, fg=FG,
                 troughcolor=TROUGH, highlightthickness=0,
                 activebackground=BG_SEP, showvalue=False,
                 length=130).pack(side=tk.LEFT, expand=True, fill=tk.X)

    def _build_controls(self, parent: tk.Frame) -> None:
        canvas = tk.Canvas(parent, bg=BG_PANEL, highlightthickness=0)
        sb = tk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        sf = tk.Frame(canvas, bg=BG_PANEL)
        sf.bind("<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=sf, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        self._section(sf, "CAMERA")
        self.start_btn = tk.Button(sf, text="DETECTION", bg=BG_BTN_ON, fg=FG_TITLE,
                                   font=("Courier", 9, "bold"), relief=tk.FLAT,
                                   padx=8, pady=4, command=self.toggle)
        self.start_btn.pack(fill=tk.X, padx=6, pady=4)

        cam_row = tk.Frame(sf, bg=BG_PANEL)
        cam_row.pack(fill=tk.X, padx=6, pady=2)
        self.cam_combo = ttk.Combobox(cam_row, width=13, state="readonly",
                                      font=("Courier", 8))
        self.cam_combo.pack(side=tk.LEFT)
        self.cam_combo.bind("<<ComboboxSelected>>", self._on_cam_selected)
        tk.Button(cam_row, text="Detecter", bg=BG_BTN_ON, fg=FG_TITLE,
                  font=("Courier", 7), relief=tk.FLAT, padx=4,
                  command=self._detect_cameras).pack(side=tk.LEFT, padx=4)
        self.cam_status_lbl = tk.Label(sf, text="Scan...",
                                       bg=BG_PANEL, fg=FG_DIM, font=("Courier", 6))
        self.cam_status_lbl.pack(anchor="w", padx=8)
        tk.Checkbutton(sf, text="Flip horizontal", variable=self.flip_var,
                       bg=BG_PANEL, fg=FG, selectcolor=BG_SEP,
                       activebackground=BG_PANEL,
                       font=("Courier", 8)).pack(anchor="w", padx=8, pady=(2, 0))

        self._section(sf, "DISTORSION")
        for label, val in [("Aucune", "none"), ("Radiale seule", "radial"),
                           ("Complete", "full")]:
            tk.Radiobutton(sf, text=label, variable=self.undist_mode, value=val,
                           bg=BG_PANEL, fg=FG, selectcolor=BG_SEP,
                           activebackground=BG_PANEL, font=("Courier", 8),
                           command=self.calib.invalidate_cache
                           ).pack(anchor="w", padx=10, pady=1)
        tk.Label(sf, text=f"Calibration: {self.calib.status}",
                 bg=BG_PANEL, fg=(FG if self.calib.loaded else "#cc2222"),
                 font=("Courier", 6), wraplength=210,
                 justify=tk.LEFT).pack(anchor="w", padx=10, pady=(2, 0))

        self._section(sf, "TABLE (HOMOGRAPHIE)")
        self._table_btn = tk.Button(
            sf, text="CALIBRER TABLE", bg=BG_BTN_ON, fg=FG_TITLE,
            font=("Courier", 9, "bold"), relief=tk.FLAT,
            padx=8, pady=4, command=self._start_table_calib,
        )
        self._table_btn.pack(fill=tk.X, padx=6, pady=4)
        self._table_lbl = tk.Label(
            sf, text=self._table_status(), bg=BG_PANEL,
            fg=(FG if self.perspective.calibrated else FG_DIM),
            font=("Courier", 6), wraplength=210, justify=tk.LEFT,
        )
        self._table_lbl.pack(anchor="w", padx=10, pady=(0, 2))

        self._section(sf, "COULEUR")
        cf = tk.Frame(sf, bg=BG_PANEL)
        cf.pack(fill=tk.X, padx=6, pady=2)
        for i, name in enumerate(HSV_PRESETS):
            tk.Radiobutton(cf, text=name, variable=self.color_var, value=name,
                           bg=BG_PANEL, fg=FG, selectcolor=BG_SEP,
                           activebackground=BG_PANEL, font=("Courier", 8),
                           command=self._on_color_change
                           ).grid(row=i // 3, column=i % 3,
                                  sticky="w", padx=2, pady=1)

        self._section(sf, "FILTRE HSV")
        for text, var, lo, hi in [("H min", self.h_min, 0, 180),
                                  ("H max", self.h_max, 0, 180),
                                  ("S min", self.s_min, 0, 255),
                                  ("S max", self.s_max, 0, 255),
                                  ("V min", self.v_min, 0, 255),
                                  ("V max", self.v_max, 0, 255)]:
            self._slider(sf, text, var, lo, hi)

        tk.Frame(sf, bg=BG_PANEL, height=16).pack()

    # =========================================================== cameras ===
    def _detect_cameras(self) -> None:
        self.cam_status_lbl.config(text="Scan en cours...")
        logger.info("Détection des caméras...")

        def _scan() -> None:
            found: list[int] = []
            for i in range(CAMERA_SCAN_RANGE):
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    found.append(i)
                    cap.release()
            self._cameras = found
            self.root.after(0, self._update_cam_combo)

        threading.Thread(target=_scan, daemon=True).start()

    def _update_cam_combo(self) -> None:
        if self._cameras:
            values = [f"Camera {i}" for i in self._cameras]
            self.cam_combo["values"] = values
            cur = self.cam_index.get()
            if cur in self._cameras:
                self.cam_combo.set(f"Camera {cur}")
            else:
                self.cam_combo.set(values[0])
                self.cam_index.set(self._cameras[0])
            self.cam_status_lbl.config(
                text=f"{len(self._cameras)} camera(s) detectee(s)")
            logger.info("%d caméra(s) détectée(s)", len(self._cameras))
            if not self.running:
                self._start_preview(self.cam_index.get())
        else:
            self.cam_combo["values"] = ["Aucune"]
            self.cam_combo.set("Aucune")
            self.cam_status_lbl.config(text="Aucune camera detectee")
            logger.warning("Aucune caméra détectée")

    def _on_cam_selected(self, _: Any = None) -> None:
        sel = self.cam_combo.get()
        if sel.startswith("Camera "):
            self.cam_index.set(int(sel.split()[-1]))
        if not self.running:
            self._start_preview(self.cam_index.get())

    # ======================================================== modes UI ===
    def _set_ui_preview(self) -> None:
        """Affiche la vue preview grand format, masque les 4 cellules."""
        for cell in self._cells:
            cell.grid_remove()
        self._preview_lbl.grid()
        self.log_lbl.config(text="Preview — Reglez vos parametres")

    def _set_ui_detection(self) -> None:
        """Affiche la grille 4 vues, masque la preview grand format."""
        self._preview_lbl.grid_remove()
        for cell in self._cells:
            cell.grid()

    # ================================================ calib table (homographie) --
    def _table_status(self) -> str:
        if self.perspective.calibrated:
            return f"Table: OK {self.perspective.table_w}x{self.perspective.table_h} px"
        return "Table: non calibree (4 coins)"

    def _update_table_ui(self) -> None:
        self._table_lbl.config(
            text=self._table_status(),
            fg=(FG if self.perspective.calibrated else FG_DIM),
        )
        self._table_btn.config(
            text="RECALIBRER" if self.perspective.calibrated else "CALIBRER TABLE"
        )

    def _start_table_calib(self) -> None:
        """Active le mode clic 4 coins sur la preview."""
        if not self._preview_mode:
            return
        self._calib_table = True
        self._calib_clicks = []
        self._table_btn.config(text="CLIQUEZ 1/4 (haut-gauche)", bg="#cc8800")
        self.log_lbl.config(text="Calibration table — cliquez le coin 1/4 (haut-gauche)")

    def _on_preview_click(self, event: tk.Event) -> None:
        """Clic sur la preview : si mode calib table actif, enregistre le coin."""
        if not self._calib_table or not self._preview_mode:
            return
        if self._preview_cap is None:
            return
        lw = self._preview_lbl.winfo_width()
        lh = self._preview_lbl.winfo_height()
        if lw <= 1 or lh <= 1:
            return

        # l'image PREVIEW_W×PREVIEW_H est centrée dans le label
        ox = (lw - PREVIEW_W) // 2
        oy = (lh - PREVIEW_H) // 2
        ix = event.x - ox
        iy = event.y - oy
        if ix < 0 or iy < 0 or ix >= PREVIEW_W or iy >= PREVIEW_H:
            return  # clic hors image

        # conversion preview (760×570) → frame caméra (ex: 1280×720)
        cap = self._preview_cap
        fw = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        fh = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        if fw <= 0 or fh <= 0:
            fw, fh = 1280.0, 720.0
        px = ix * (fw / PREVIEW_W)
        py = iy * (fh / PREVIEW_H)
        self._calib_clicks.append((px, py))

        n = len(self._calib_clicks)
        labels = ["haut-gauche", "haut-droite", "bas-droite", "bas-gauche"]
        if n < 4:
            self._table_btn.config(text=f"CLIQUEZ {n+1}/4 ({labels[n]})", bg="#cc8800")
            self.log_lbl.config(text=f"Calibration table — cliquez le coin {n+1}/4 ({labels[n]})")
        if n == 4:
            self.perspective.set_corners(self._calib_clicks)
            self._calib_table = False
            self._calib_clicks = []
            self._update_table_ui()
            self.log_lbl.config(text=f"Table calibree — {self.perspective.table_w}x{self.perspective.table_h} px")

    # =========================================================== preview ===
    def _start_preview(self, idx: int) -> None:
        self._stop_preview()
        cap = cv2.VideoCapture(idx)
        if not cap.isOpened():
            cap.release()
            logger.warning("Impossible d'ouvrir la caméra %d pour la preview", idx)
            return
        with self._preview_lock:
            self._preview_cap = cap
            self._preview_on = True
            self._preview_pending = False
        threading.Thread(target=self._preview_worker, daemon=True).start()
        logger.info("Preview démarrée sur caméra %d", idx)

    def _stop_preview(self) -> None:
        with self._preview_lock:
            self._preview_on = False
            if self._preview_cap:
                self._preview_cap.release()
                self._preview_cap = None

    def _preview_worker(self) -> None:
        """Thread dédié — lit les frames à ~30 fps et les pousse vers le thread UI."""
        while True:
            with self._preview_lock:
                if not self._preview_on or self.running:
                    break
                cap = self._preview_cap
            if cap is None:
                break
            ret, frame = cap.read()
            if ret:
                with self._preview_lock:
                    if self._preview_pending or not self._preview_on or self.running:
                        continue
                    self._preview_pending = True
                f = cv2.flip(frame, 1) if self.flip_var.get() else frame.copy()
                self.root.after(0, lambda img=f: self._show_preview_frame(img))
            time.sleep(CAMERA_PREVIEW_INTERVAL)
        logger.debug("Thread preview terminé")

    def _show_preview_frame(self, frame: np.ndarray) -> None:
        """Appelé sur le thread UI — affiche la frame (grand format ou coin Brut)."""
        with self._preview_lock:
            self._preview_pending = False
            if not self._preview_on or self.running:
                return
        if self._preview_mode:
            # dessiner les coins de calibration table si mode actif
            if self._calib_table or self.perspective.calibrated:
                frame = frame.copy()
                for i, (px, py) in enumerate(self._calib_clicks):
                    cv2.circle(frame, (int(px), int(py)), 10, (255, 0, 255), 2)
                    cv2.circle(frame, (int(px), int(py)), 6, (255, 0, 255), -1)
                    cv2.putText(frame, str(i + 1), (int(px) + 14, int(py) - 8),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 255), 2)
                if not self._calib_table and self.perspective.calibrated:
                    self.perspective.draw_corners(frame)
            ph = self._to_tk_size(frame, PREVIEW_W, PREVIEW_H)
            lbl = self._preview_lbl
        else:
            ph = self._to_tk(frame)
            lbl = self.img_labels["Brut"]
        lbl.configure(image=ph)
        lbl._photo = ph

    # =========================================================== trackers ===
    def _update_trackers(self, logs: list[str]) -> list[str]:
        """
        Tracker spatial par objet avec lissage EMA et stabilisation du type par vote.

        Nettoyage automatique :
          - Supprime les trackers après TRACKER_MAX_MISSED frames manquées
          - Limite à TRACKER_MAX_COUNT trackers
          - Supprime les trackers plus anciens que TRACKER_MAX_AGE_FRAMES
        """
        detections: list[tuple[str, float, float, float]] = []
        for entry in logs:
            stype, raw = entry.split("@")
            parts = raw.strip("()").split(",")
            cx, cy, theta = float(parts[0]), float(parts[1]), float(parts[2])
            detections.append((stype, cx, cy, theta))

        with self._trackers_lock:
            matched_tr: set[int] = set()
            matched_det: set[int] = set()

            for di, (stype, cx, cy, theta) in enumerate(detections):
                best_ti, best_d = -1, float("inf")
                for ti, tr in enumerate(self._trackers):
                    if ti in matched_tr:
                        continue
                    d = ((tr["cx"] - cx) ** 2 + (tr["cy"] - cy) ** 2) ** 0.5
                    if d < best_d and d < TRACKER_MATCH_DIST:
                        best_d, best_ti = d, ti

                a = TRACKER_EMA_ALPHA
                if best_ti >= 0:
                    tr = self._trackers[best_ti]
                    tr["cx"] = a * cx + (1 - a) * tr["cx"]
                    tr["cy"] = a * cy + (1 - a) * tr["cy"]
                    tr["theta"] = a * theta + (1 - a) * tr["theta"]
                    tr["history"].append(stype)
                    tr["missed"] = 0
                    tr["age"] = tr.get("age", 0) + 1
                    matched_tr.add(best_ti)
                    matched_det.add(di)
                else:
                    self._trackers.append({
                        "cx": cx, "cy": cy, "theta": theta,
                        "history": deque([stype], maxlen=TRACKER_HISTORY_LEN),
                        "missed": 0,
                        "age": 0,
                    })
                    matched_tr.add(len(self._trackers) - 1)
                    matched_det.add(di)

            for ti in range(len(self._trackers)):
                if ti not in matched_tr:
                    self._trackers[ti]["missed"] += 1
                    self._trackers[ti]["age"] = self._trackers[ti].get("age", 0) + 1

            self._trackers = [
                tr for tr in self._trackers
                if tr["missed"] <= TRACKER_MAX_MISSED
                and tr.get("age", 0) <= TRACKER_MAX_AGE_FRAMES
            ]

            if len(self._trackers) > TRACKER_MAX_COUNT:
                self._trackers = self._trackers[-TRACKER_MAX_COUNT:]

            out: list[str] = []
            for ti in sorted(matched_tr):
                if ti >= len(self._trackers):
                    continue
                tr = self._trackers[ti]
                counts = Counter(tr["history"])
                candidates = [
                    (SHAPE_PRIORITY.get(t, 99), t)
                    for t, c in counts.items() if c >= TRACKER_MIN_VOTES
                ]
                stype = min(candidates)[1] if candidates else tr["history"][-1]
                out.append(f"{stype}@({int(tr['cx'])},{int(tr['cy'])},{tr['theta']:.1f})")

        return out

    # =========================================================== logique ===
    def _on_color_change(self) -> None:
        name = self.color_var.get()
        if name in HSV_PRESETS:
            h_mn, h_mx, s_mn, s_mx, v_mn, v_mx = HSV_PRESETS[name]
            self.h_min.set(h_mn)
            self.h_max.set(h_mx)
            self.s_min.set(s_mn)
            self.s_max.set(s_mx)
            self.v_min.set(v_mn)
            self.v_max.set(v_mx)

    def _process(self, frame: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, str]:
        """
        Pipeline complet : flip → undistort → perspective → masque → détection.
        Retourne (brut, radial_display, mask_bgr, result_disp, log_text).
        """
        if self.flip_var.get():
            frame = cv2.flip(frame, 1)

        undist = self.calib.apply(frame, self.undist_mode.get())
        undist_display = self.calib.apply(frame, "radial")

        # --- perspective warp (homographie table) ---
        if self.perspective.calibrated:
            work = self.perspective.warp(undist)
        else:
            work = undist

        refined = build_mask(
            work, self.color_var.get(),
            self.h_min.get(), self.h_max.get(),
            self.s_min.get(), self.s_max.get(),
            self.v_min.get(), self.v_max.get(),
        )
        result, logs, det_frame = detect_and_annotate(
            work, refined, self.color_var.get()
        )

        # --- transformer les centroïdes via perspective ---
        if self.perspective.calibrated:
            for det in det_frame.detections:
                det.cx, det.cy = self.perspective.transform_point(det.cx, det.cy)
            logs = [f"{d.shape_type}@({int(d.cx)},{int(d.cy)},{d.theta:.1f})"
                    for d in det_frame.detections]

        mask_bgr = cv2.cvtColor(refined, cv2.COLOR_GRAY2BGR)
        result_disp = self._crop_asym(result, CROP_LEFT, CROP_TOP, CROP_RIGHT, CROP_BOTTOM)
        mask_disp = self._crop_asym(mask_bgr, CROP_LEFT, CROP_TOP, CROP_RIGHT, CROP_BOTTOM)

        # --- repère image + labels ajustés au crop (0,0 = coin haut-gauche visible) ---
        h_full, w_full = result.shape[:2]
        dx = int(w_full * CROP_LEFT)
        dy = int(h_full * CROP_TOP)
        for det in det_frame.detections:
            cx_c = int(det.cx) - dx
            cy_c = int(det.cy) - dy
            if 0 <= cx_c < result_disp.shape[1] and 0 <= cy_c < result_disp.shape[0]:
                label = f"{det.shape_type} ({cx_c},{cy_c}) {det.theta:.1f}\u00b0"
                (tw, th), bl = cv2.getTextSize(
                    label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2
                )
                tx = max(4, min(cx_c - tw // 2, result_disp.shape[1] - tw - 4))
                ty = max(cy_c - 28, th + 8)
                cv2.rectangle(result_disp, (tx - 3, ty - th - 3),
                              (tx + tw + 3, ty + bl + 2), (0, 0, 0), -1)
                cv2.putText(result_disp, label, (tx, ty),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        _draw_image_frame(result_disp)

        # --- overlay perspective : bordure + dimensions sur la vue Detection ---
        if self.perspective.calibrated:
            _GREEN_BGR = (0, 255, 0)
            rd_h, rd_w = result_disp.shape[:2]
            cv2.rectangle(result_disp, (1, 1), (rd_w - 2, rd_h - 2), _GREEN_BGR, 3)
            tdim = f"TABLE: {self.perspective.table_w}x{self.perspective.table_h} px"
            (tw, th), _ = cv2.getTextSize(tdim, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            tx = rd_w - tw - 10
            ty = rd_h - 12
            cv2.rectangle(result_disp, (tx - 4, ty - th - 4),
                          (tx + tw + 4, ty + 4), (0, 0, 0), -1)
            cv2.putText(result_disp, tdim, (tx, ty),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, _GREEN_BGR, 2)

        # --- dessiner le quadrilatère source sur la vue Brut ---
        if self.perspective.calibrated:
            self.perspective.draw_corners(frame)

        smoothed = self._update_trackers(logs)
        log_text = "  |  ".join(smoothed) if smoothed else "-- aucun objet --"
        self._last_detection = det_frame

        # dimensions image croppée pour conversion clic → pixels
        self._crop_w = result_disp.shape[1]
        self._crop_h = result_disp.shape[0]

        return frame, undist_display, mask_disp, result_disp, log_text

    def _crop_asym(self, img: np.ndarray,
                   left: float, top: float, right: float, bottom: float,
                   ) -> np.ndarray:
        h, w = img.shape[:2]
        x1 = int(w * left)
        y1 = int(h * top)
        x2 = w - int(w * right)
        y2 = h - int(h * bottom)
        return img[y1:y2, x1:x2]

    def _to_tk(self, frame: np.ndarray) -> ImageTk.PhotoImage:
        return self._to_tk_size(frame, DISPLAY_W, DISPLAY_H)

    def _to_tk_size(self, frame: np.ndarray, w: int, h: int) -> ImageTk.PhotoImage:
        rgb = cv2.cvtColor(cv2.resize(frame, (w, h)), cv2.COLOR_BGR2RGB)
        return ImageTk.PhotoImage(Image.fromarray(rgb))

    def _update_display(
        self, raw: np.ndarray, undist: np.ndarray,
        mask_bgr: np.ndarray, result: np.ndarray, log: str,
    ) -> None:
        _MAGENTA = (255, 0, 255)  # BGR
        for name, img in zip(("Brut", "Radiale", "Masque", "Detection"),
                              (raw, undist, mask_bgr, result)):
            if name == "Detection" and self._marker_visible and self._crop_w > 0:
                img = img.copy()
                cx, cy = int(self._marker_cx), int(self._marker_cy)
                h_c, w_c = img.shape[:2]
                size = max(14, int(min(w_c, h_c) * 0.025))
                cv2.line(img, (cx - size, cy), (cx + size, cy), _MAGENTA, 2)
                cv2.line(img, (cx, cy - size), (cx, cy + size), _MAGENTA, 2)
                cv2.circle(img, (cx, cy), 6, _MAGENTA, 2)
                cv2.circle(img, (cx, cy), 3, _MAGENTA, -1)
                tlabel = f"({cx},{cy})"
                (tw, th), bl = cv2.getTextSize(
                    tlabel, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2
                )
                tx = max(4, min(cx + size + 8, w_c - tw - 4))
                ty = min(cy + th + 8, h_c - 4)
                cv2.rectangle(img, (tx - 3, ty - th - 3),
                              (tx + tw + 3, ty + bl + 2), (0, 0, 0), -1)
                cv2.putText(img, tlabel, (tx, ty),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, _MAGENTA, 2)
            ph = self._to_tk(img)
            lbl = self.img_labels[name]
            lbl.configure(image=ph)
            lbl._photo = ph
        self.log_lbl.config(text=log)

    # ============================================================ control ===
    def _on_detection_click(self, event: tk.Event) -> None:
        """Clic sur la vue Detection : 1er clic = marqueur, 2e = efface, etc."""
        if not self.running or self._crop_w <= 0:
            return
        if self._marker_visible:
            self._marker_visible = False
            return
        # conversion coordonnées display (380×285) → crop (pleine résolution)
        scale_x = self._crop_w / DISPLAY_W
        scale_y = self._crop_h / DISPLAY_H
        self._marker_cx = event.x * scale_x
        self._marker_cy = event.y * scale_y
        self._marker_visible = True

    def toggle(self) -> None:
        if self._preview_mode:
            # passer en mode détection
            self._stop_preview()
            self._preview_mode = False
            self._set_ui_detection()
            idx = self.cam_index.get()
            self.cap = cv2.VideoCapture(idx)
            if not self.cap.isOpened():
                self.cap.release()
                self.cap = None
                self.log_lbl.config(text=f"[ERR] Camera {idx} introuvable")
                logger.error("Caméra %d introuvable", idx)
                self._preview_mode = True
                self._set_ui_preview()
                self._start_preview(idx)
                return
            self.running = True
            self._frame_count = 0
            self._last_frame_time = 0.0
            self._frame_interval = CAMERA_PROCESS_INTERVAL
            self.start_btn.config(text="ARRETER", bg=BG_BTN_OFF)
            logger.info("Pipeline démarré sur caméra %d", idx)
            self._loop()
        else:
            # arrêter la détection, retour au mode preview
            self.running = False
            if self.cap:
                self.cap.release()
                self.cap = None
            self._preview_mode = True
            self._set_ui_preview()
            self.start_btn.config(text="DETECTION", bg=BG_BTN_ON)
            self.log_lbl.config(text="Preview — Reglez vos parametres")
            logger.info("Retour au mode preview")
            self._start_preview(self.cam_index.get())

    def _loop(self) -> None:
        """Boucle principale cadencée à ~30 fps via root.after."""
        if not self.running:
            return
        now = time.time()
        elapsed = now - self._last_frame_time
        if self._last_frame_time > 0 and elapsed < self._frame_interval:
            delay_ms = int((self._frame_interval - elapsed) * 1000)
            self.root.after(max(1, delay_ms), self._loop)
            return
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                self._frame_count += 1
                self._last_frame_time = time.time()
                try:
                    raw, undist, mask_bgr, result, log = self._process(frame)
                    self._update_display(raw, undist, mask_bgr, result, log)
                except Exception as exc:
                    logger.error("Erreur traitement frame: %s", exc)
                    self.log_lbl.config(text=f"[ERR] {exc}")
            else:
                logger.warning("Échec de lecture caméra")
                self.log_lbl.config(text="[ERR] Lecture caméra échouée")
        self.root.after(1, self._loop)

    def on_close(self) -> None:
        """Nettoyage avant fermeture de l'application."""
        logger.info("Fermeture de l'application")
        self.running = False
        self._stop_preview()
        if self.cap:
            self.cap.release()
        self.root.destroy()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    root = tk.Tk()
    app = DoosanVisionApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
