# Calibration

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

## Calibrer la zone de travail (homographie)

Si la caméra n'est pas parfaitement perpendiculaire à la table, les coordonnées pixel ne correspondent pas à une vue de dessus. La calibration table corrige ça.

1. Cliquer sur **CALIBRER TABLE**
2. La preview passe en mode calibration
3. Cliquer les 4 coins de la zone de travail dans l'ordre : haut-gauche, haut-droite, bas-droite, bas-gauche
4. Au 4e clic, l'homographie est calculée automatiquement et sauvegardée dans `table_corners.json`
5. Le statut affiche "Table calibrée : L x H px"

Une fois calibrée, tous les centroïdes sont transformés dans le repère de la table via `PerspectiveManager.transform_point()`.
