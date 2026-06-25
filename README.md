# ARM Vision - Tri robotisé Doosan

Projet académique ISTY / UVSQ / Paris-Saclay.

On filme des pièces colorées posées sur une table, le programme détecte leur forme, leur position XY et leur orientation. Ces coordonnées sont ensuite envoyées au bras robotique Doosan qui vient les ramasser et les trier.

---

## Démo


[![Voir la vidéo](https://img.youtube.com/vi/c958nuAUyGM/maxresdefault.jpg)](https://www.youtube.com/watch?v=c958nuAUyGM)

---

## De quoi on a besoin

- Python 3.10 ou plus récent
- Une webcam USB (idéalement 1280x720)
- Le fichier de calibration `calibration_data/calibration.yaml` (expliqué plus bas)
- Un bras Doosan (pour le pick and place physique)

---

## Comment ça marche, en gros

Le projet a trois parties :

1. **La calibration de la caméra** : on corrige la distorsion de l'objectif pour avoir des coordonnées précises, même sur les bords de l'image.

2. **La vision** (dossier `src/`) : on filme la table, on isole les pièces par couleur, on détecte leur forme (cercle, carré, triangle...), on calcule leur centre et leur angle.

3. **La calibration de la table** (dans l'appli) : on dit au programme où se trouve la zone de travail dans l'image, pour transformer les pixels en coordonnées exploitables par le robot.

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

## Calibrer la caméra

Cette étape est à faire une seule fois (sauf si on change de caméra ou d'objectif). Elle nécessite un damier imprimé de 8x11 cases (7x10 coins intérieurs), carreaux de 20 mm.

Le but est de générer un fichier YAML contenant la matrice intrinsèque de la caméra (focale, centre optique) et ses coefficients de distorsion. Ce fichier est ensuite chargé par l'application de vision.

Le format attendu du YAML :

```yaml
camera_matrix:
  - [fx, 0, cx]
  - [0, fy, cy]
  - [0, 0, 1]
dist_coeff:
  - [k1, k2, p1, p2, k3]
image_width: 1280
image_height: 720
```

Le fichier doit être placé à l'emplacement configuré dans `src/config.py` (par défaut : `../scripts/calibration_data_save/calibration.yaml`). Si le chemin change, modifier la constante `CALIB_YAML` dans `config.py`.

---

## Lancer l'appli de vision

```bash
cd src
python main.py
```

### Ce qu'on voit à l'écran

À gauche, les contrôles. À droite, quatre vues en mode détection, ou une seule grande vue en mode preview.

**À gauche :**

- Bouton DETECTION : lance ou arrête le pipeline. Raccourci : `Espace`
- Bouton Détecter : scanne les caméras USB dispo (indices 0 à 5)
- Menu déroulant Caméra : pour choisir la webcam
- Case Flip horizontal : cochée par défaut, à décocher si la caméra n'est pas montée à l'envers
- Distorsion : Aucune / Radiale / Complète (garder Complète)
- Bouton CALIBRER TABLE : pour définir la zone de travail (voir plus bas)
- 11 couleurs : sélectionnables à la souris ou avec les touches `0` à `9`
- 6 sliders HSV : pour affiner le filtrage de la couleur en temps réel

**À droite** (quand la détection tourne) :

- En haut à gauche, la vue Brut : l'image corrigée avec le mode choisi
- En haut à droite, la vue Radiale : toujours la correction radiale, pour comparer
- En bas à gauche, le Masque : les pixels gardés après filtrage couleur (blanc = pièce, noir = fond)
- En bas à droite, la Détection : l'image annotée avec le contour, le centre, les axes X/Y, et un label du type "cercle@(320,240) 5.2 degrés"

En bas de la fenêtre, une barre de texte affiche les coordonnées de tous les objets détectés. Exemple :

```
cercle@(320,240) 0°  |  carré@(150,400) -12.5°
```

### Les 4 vues en détail

Chaque vue fait 380x285 pixels. En mode preview (avant d'appuyer sur DETECTION), une grande vue de 760x570 remplit tout le panneau droit.

La vue Détection affiche un repère image en haut à gauche (flèche rouge X vers la droite, flèche verte Y vers le bas) et les dimensions de l'image. Pratique pour savoir dans quel repère on travaille.

On peut cliquer sur la vue Détection pour poser un marqueur magenta à un endroit précis et vérifier les coordonnées. Un deuxième clic l'efface.

### Les 11 couleurs

Clic ou touches `0` à `9` :

`0` rouge, `1` vert, `2` bleu, `3` jaune, `4` orange, `5` cyan, `6` violet, `7` rose, `8` blanc, `9` marron. Le gris est accessible uniquement à la souris.

Quand on change de couleur, les 6 sliders HSV se calent automatiquement sur le preset.

### Ajuster les sliders HSV

Les 6 sliders contrôlent le seuillage de la couleur :

- **H min / H max** : la teinte (0 à 180 dans le modèle HSV d'OpenCV)
- **S min / S max** : la saturation, autrement dit l'intensité de la couleur (0 à 255)
- **V min / V max** : la luminosité (0 à 255)

Le but : que la pièce apparaisse en blanc sur le masque, et tout le reste en noir. Les modifications sont appliquées en direct.

Cas particulier du rouge : comme le rouge est à cheval sur 0 et 180 degrés dans le cercle des teintes, le programme combine automatiquement deux plages (proche de 0 et proche de 180). Pas besoin de s'en occuper.

### Sauvegarder ses réglages

Une fois qu'on est content du filtrage : `Ctrl+S`. Ça écrit tous les presets dans `hsv_presets.json`. Au prochain lancement, les valeurs seront restaurées.

---

## Calibrer la zone de travail (homographie)

Si la caméra n'est pas parfaitement perpendiculaire à la table, les coordonnées pixel ne correspondent pas à une vue de dessus. La calibration table corrige ça.

1. Cliquer sur **CALIBRER TABLE**
2. La preview passe en mode calibration
3. Cliquer les 4 coins de la zone de travail dans l'ordre : haut-gauche, haut-droite, bas-droite, bas-gauche
4. Au 4e clic, l'homographie est calculée automatiquement et sauvegardée dans `table_corners.json`
5. Le statut affiche "Table calibrée : L x H px"

Une fois calibrée, tous les centroïdes sont transformés dans le repère de la table via `PerspectiveManager.transform_point()`.

---

## Ce qui se passe dans le pipeline

Voilà l'enchaînement complet à chaque image :

1. La frame est lissée (flip horizontal si coché)
2. Correction de distorsion (mode choisi : aucune, radiale ou complète)
3. Si la table est calibrée, homographie pour remettre à plat
4. Création du masque : flou gaussien, conversion HSV, seuillage, ouverture/fermeture/dilatation morphologique
5. Détection des formes : Canny, recherche de contours, approximation polygonale
6. Classification : 3 sommets = triangle, 4 sommets = carré ou rectangle selon le ratio, plus de 6 = cercle
7. Calcul du centre de masse précis avec `cv2.moments()`
8. Calcul du repère local (axe X rouge, axe Y vert, angle theta) avec `cv2.minAreaRect()`
9. Annotation : cercle coloré au centre, croix cyan, flèches X/Y, label avec type, coordonnées et angle
10. Trackers : lissage des positions (moyenne mobile exponentielle), stabilisation du type par vote majoritaire, suppression des trackers fantômes

---

## À propos des trackers

Sans trackers, les coordonnées et le type de forme peuvent changer d'une image à l'autre à cause du bruit ou des variations de luminosité. Le système de trackers lisse tout ça :

- Chaque objet détecté est associé à un tracker existant s'il est à moins de 80 pixels de sa position précédente
- Les positions sont lissées avec une moyenne mobile (alpha = 0.35, donc 65% de l'historique, 35% de la nouvelle valeur)
- Le type de forme est stabilisé par vote majoritaire sur les 8 dernières images (minimum 2 votes)
- Un tracker est supprimé s'il perd sa pièce pendant 5 images ou s'il existe depuis plus de 120 images
- Maximum 20 trackers simultanés

En cas d'égalité de votes sur le type, priorité : cercle > carré > rectangle > triangle > polygone.

---

## Raccourcis clavier

| Touche | Action |
|---|---|
| `Espace` ou `Entrée` | Démarrer / arrêter la détection |
| `F1` / `F2` | Changer le mode de distorsion (cycle avant/arrière) |
| `0` à `9` | Choisir une couleur par son index |
| `Ctrl+S` | Sauvegarder les presets HSV |

---

## Format des coordonnées

La barre XY en bas de la fenêtre affiche :

```
cercle@(320,240) 0°  |  carré@(150,400) -12.5°
```

Pour le robot, la classe `DetectionFrame` a une méthode `to_ros_dict()` qui sort un dictionnaire prêt à être publié :

```json
{
  "timestamp": 1719234567.890,
  "camera": 0,
  "resolution": [1280, 720],
  "detections": [
    {
      "type": "cercle",
      "x_px": 320.5,
      "y_px": 240.3,
      "theta_deg": 0.0,
      "color": "rouge",
      "confidence": 1.0
    }
  ]
}
```

L'envoi au robot via ROS2 ou TCP/IP n'est pas encore implémenté, le format est prêt.

---

## Les fichiers dans src/

| Fichier | Contenu |
|---|---|
| `main.py` | L'interface graphique, la gestion des caméras, la boucle de détection, les trackers |
| `config.py` | Tous les réglages : caméra, HSV, Canny, morphologie, trackers, couleurs, tailles |
| `calibration.py` | Charge le YAML de calibration, corrige la distorsion (3 modes) |
| `vision.py` | Crée le masque HSV, détecte et annote les formes |
| `utils_shapes.py` | Module verrouillé. Classification des formes depuis les contours |
| `perspective.py` | Homographie table : calibrage 4 coins, warp, transformation de points |
| `detection_result.py` | Classes de données pour les résultats de détection |
| `hsv_presets.json` | Presets des 11 couleurs, modifiable à la main ou via Ctrl+S |
| `table_corners.json` | Coins de la table, généré par la calibration table |
| `requirements.txt` | opencv-python, numpy, Pillow, PyYAML |

---

## Réglages avancés (dans config.py)

Tout est modifiable avant de lancer l'appli.

**Détection de formes :**

- `CANNY_THRESHOLDS = (50, 150)` : seuils du détecteur de contours. Baisser le premier pour détecter plus de bords, monter le deuxième pour filtrer plus
- `MIN_CONTOUR_AREA = 200` : taille minimum d'un objet en pixels carrés. Augmenter si des petits trucs parasites sont détectés
- `POLYGON_EPSILON = 0.03` : précision de l'approximation polygonale. Plus c'est bas, plus on aura de sommets. 0.03 = 3% du périmètre
- `SQUARE_AR_TOLERANCE = 0.10` : tolérance pour différencier un carré d'un rectangle. Ratio largeur/hauteur entre 0.90 et 1.10

**Morphologie :**

- `MORPH_OPEN_KERNEL = 3` : taille du noyau d'ouverture, supprime les petits points isolés
- `MORPH_CLOSE_KERNEL = 7` : taille du noyau de fermeture, bouche les trous dans le masque
- `MORPH_DILATE_ITERATIONS = 2` : dilate le masque pour gonfler les blobs

**Trackers :**

- `TRACKER_EMA_ALPHA = 0.35` : inertie du lissage. 0 = aucune réactivité, 1 = pas de lissage du tout
- `TRACKER_MATCH_DIST = 80.0` : distance max en pixels pour associer une nouvelle détection à un tracker existant

---

## Jour de compétition

Check-list :

1. Brancher la webcam, allumer le contrôleur Doosan
2. Vérifier que le fichier de calibration YAML est présent et que le chemin dans `config.py` est correct
3. Lancer `python main.py` dans `src/`
4. Cliquer **Détecter** pour scanner les caméras, sélectionner la bonne
5. Vérifier que Flip horizontal est coché si la caméra est à l'envers
6. Mode distorsion : **Complète**
7. Cliquer **CALIBRER TABLE** et définir les 4 coins
8. Choisir la couleur des pièces à trier
9. Cliquer **DETECTION**, poser une pièce, ajuster les sliders HSV
10. Vérifier que le masque est propre (pièce en blanc, fond en noir)
11. Vérifier que les coordonnées dans la barre XY sont stables
12. `Ctrl+S` pour sauver

En cas de souci :

| Problème | Solution probable |
|---|---|
| Caméra pas trouvée | Recliquer Détecter, changer de port USB |
| Image noire | Décocher/recocher Flip |
| Le masque reste noir | Élargir les plages H, baisser S_min, baisser V_min |
| Plein de faux positifs | Monter V_min, monter S_min, baisser V_max |
| Contour mal dessiné | Réduire MORPH_CLOSE_KERNEL dans config.py |
| Coordonnées qui sautent | Réduire TRACKER_EMA_ALPHA dans config.py |

---

## Ce qui reste à faire

- La transformation pixel vers millimètres robot (calibration main-œil)
- La communication réseau avec le bras (ROS2 ou TCP/IP)
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
├── .gitignore
└── src/                      # Application de vision
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
