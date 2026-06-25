"""
Structures de données pour les résultats de détection.
Prêtes pour intégration ROS2 — ces dataclasses peuvent être converties en messages.
"""
from dataclasses import dataclass, field


@dataclass
class ShapeDetection:
    """Une seule forme détectée avec ses métadonnées."""
    shape_type: str
    cx: float
    cy: float
    theta: float
    color: str
    confidence: float = 1.0


@dataclass
class DetectionFrame:
    """Résultat complet d'une frame de détection."""
    detections: list[ShapeDetection] = field(default_factory=list)
    timestamp: float = 0.0
    camera_index: int = 0
    frame_width: int = 0
    frame_height: int = 0

    @property
    def has_objects(self) -> bool:
        """True si au moins une détection est présente."""
        return len(self.detections) > 0

    def to_log_text(self) -> str:
        """Format pour affichage UI: 'type@(cx,cy,θ)'."""
        if not self.detections:
            return "-- aucun objet --"
        parts: list[str] = []
        for d in self.detections:
            parts.append(f"{d.shape_type}@({int(d.cx)},{int(d.cy)},{d.theta:.1f})")
        return "  |  ".join(parts)

    def to_ros_dict(self) -> dict:
        """
        Dictionnaire sérialisable pour publication ROS2.
        À convertir en message custom (ShapeDetectionArray, etc.).
        """
        return {
            "timestamp": self.timestamp,
            "camera": self.camera_index,
            "resolution": [self.frame_width, self.frame_height],
            "detections": [
                {
                    "type": d.shape_type,
                    "x_px": d.cx,
                    "y_px": d.cy,
                    "theta_deg": d.theta,
                    "color": d.color,
                    "confidence": d.confidence,
                }
                for d in self.detections
            ],
        }
