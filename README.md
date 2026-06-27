# ARM Vision - Tri robotisé Doosan

Projet académique ISTY / UVSQ / Paris-Saclay.

**Équipe :** Valentin VAUTIER, Raphaël RENARD, Mahamane BAH, Issa DIOUF

On filme des pièces colorées posées sur une table, le programme détecte leur forme, leur position XY et leur orientation. Ces coordonnées sont ensuite envoyées au bras robotique Doosan qui vient les ramasser et les trier.

---

## Démo

[![Voir la vidéo](https://img.youtube.com/vi/c958nuAUyGM/maxresdefault.jpg)](https://www.youtube.com/watch?v=c958nuAUyGM)

---

## De quoi on a besoin

- Python 3.10 ou plus récent
- Une webcam USB (idéalement 1280x720)
- Le fichier de calibration `calibration_data/calibration.yaml`
- Un bras Doosan (pour le pick and place physique)

---

## Installation

Ouvrir un terminal dans `src/` :

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate # Linux
pip install -r requirements.txt
```

Les dépendances : opencv-python, numpy, Pillow, PyYAML.

---

## Lancer l'appli

```bash
cd src
python main.py
```

> Le dossier `src/` contient uniquement le code de l'application de vision. Les tests ROS 2, Gazebo et MATLAB ont été réalisés sur le PC de la salle de projet ARM.

---

## Documentation

| Fichier | Contenu |
|---|---|
| [CALIBRATION.md](./CALIBRATION.md) | Calibration caméra + calibration table (homographie) |
| [GUIDE.md](./GUIDE.md) | Interface, couleurs, pipeline, trackers, réglages, check-list compétition |
| [ROS2.md](./ROS2.md) | Installation ROS2, driver Doosan, simulation Gazebo, interface MATLAB |

---

## Ce qui reste à faire

- La transformation pixel vers millimètres robot (calibration main-œil)
- La communication réseau avec le bras (ROS2 ou TCP/IP)
- La communication par MATLAB
- La partie mécanique du robot
- Des tests unitaires
- La détection de plusieurs couleurs en même temps
- Un export CSV des coordonnées
- Un mode lecture de fichier vidéo pour tester sans caméra

---

## Structure du projet

```
Doosan/
├── Demo_Vision_Robot_ARM.mp4
├── README.md
├── CALIBRATION.md
├── GUIDE.md
├── ROS2.md
├── .gitignore
└── src/                      # Application de vision (uniquement)
    ├── main.py
    ├── config.py
    ├── calibration.py
    ├── vision.py
    ├── utils_shapes.py
    ├── perspective.py
    ├── detection_result.py
    ├── hsv_presets.json
    ├── table_corners.json
    └── requirements.txt
```
