# ROS 2 & Simulation Doosan

L'objectif était de mettre en place une architecture permettant de communiquer avec un robot Doosan via ROS 2, puis d'utiliser MATLAB comme interface de commande.

---

## Configuration utilisée

- **Système** : Ubuntu 24.04
- **ROS 2** : Jazzy
- **Driver robot** : doosan-robot2
- **Simulation** : Gazebo
- **Interface MATLAB** : ROS Toolbox

---

## Installation de ROS 2 Jazzy

L'installation de ROS 2 a d'abord été bloquée par un problème réseau lié au réseau de l'école. Le dépôt ROS était accessible, mais certains accès étaient filtrés. La solution a été d'utiliser un partage de connexion USB depuis un téléphone afin de récupérer correctement les paquets nécessaires.

### Correction du dépôt ROS

Une erreur de clé GPG apparaissait lors de `apt update`. Elle a été corrigée en installant correctement la clé ROS et en configurant le dépôt ROS 2 pour Ubuntu Noble.

---

## Installation et compilation du driver Doosan

Le dépôt officiel `doosan-robot2` a été cloné puis compilé avec `colcon build`.

La compilation s'est terminée correctement :

```
Summary: 29 packages finished
```

Les packages Doosan ont bien été détectés, notamment :

- `dsr_bringup2`
- `dsr_description2`
- `dsr_controller2`
- `dsr_hardware2`
- `dsr_msgs2`
- `dsr_gazebo2`

---

## Lancement de la simulation

La simulation Gazebo du robot M1013 a été lancée avec :

```bash
ros2 launch dsr_bringup2 dsr_bringup2_gazebo.launch.py model:=m1013
```

Le robot apparaît bien dans Gazebo. Les topics ROS associés sont visibles, notamment :

- `/dsr01/gz/joint_states`
- `/dsr01/gz/dsr_position_controller/commands`
- `/dsr01/robot_description`

---

## Tests ROS

Le topic `/dsr01/gz/joint_states` est bien visible, mais la récupération effective des messages n'a pas encore été stabilisée. Plusieurs conflits de nœuds ROS ont été observés, notamment des doublons de `gazebo_connection` et `virtual_node`, ce qui semble perturber la communication.

---

## Test MATLAB

MATLAB a été lancé avec ROS Toolbox. Un nœud ROS 2 MATLAB a été créé avec :

```matlab
node = ros2node("/matlab_doosan");
```

Cependant, MATLAB ne voyait que les topics `/parameter_events` et `/rosout`, mais pas les topics Doosan. Le problème semble lié à la configuration DDS / `ROS_DOMAIN_ID` ou au middleware ROS 2 utilisé entre MATLAB et ROS 2.

---

## État actuel

- ROS 2 Jazzy est installé et fonctionnel.
- Le driver Doosan est installé et compilé.
- Gazebo lance le modèle du robot M1013.
- Les topics Doosan apparaissent côté ROS 2.
- La connexion MATLAB - ROS 2 n'est pas encore opérationnelle.

Le problème restant concerne la communication DDS entre MATLAB et le réseau ROS 2 généré par la simulation Doosan.

---

## Prochaines étapes

1. Nettoyer l'environnement ROS avant chaque test :
   ```bash
   pkill -f ros2
   pkill -f gz
   ros2 daemon stop
   ros2 daemon start
   ```
2. Relancer uniquement Gazebo, sans lancer plusieurs simulations en parallèle.
3. Vérifier que `ROS_DOMAIN_ID` est identique dans Ubuntu et MATLAB.
4. Vérifier le middleware DDS utilisé par MATLAB et ROS 2.
5. Tester une communication ROS 2 simple entre MATLAB et Ubuntu avant de reprendre le pilotage Doosan.
