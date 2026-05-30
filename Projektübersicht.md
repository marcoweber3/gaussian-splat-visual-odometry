# Pipeline zur Simulation und Evaluation visueller Lokalisierung in 3D-Gaussian-Splat-Umgebungen

## Projektübersicht

Ziel ist es, aus einer 3D-Gaussian-Splat-Umgebung simulierte Kamerabilder aus sicht eines Roboters zu erzeugen.  
Diese Bilddaten sollen anscließend genutzt werden, um visuelle Lokalisierungs- bzw. Odometrie-Algorithmen zu testen und mit der ursprünglichen simulierten Fahrtrajektorie zu vergleichen.

Der Gaussian Splat selbst soll erstmal unverändert bleiben, weil ein direktes Umschreiben der Datei fehleranfällig wäre. Typische Splat-Dateien besitzen keine einfache globale Achsen- oder Ursprungseinstellung, daher müssten einzelne Splat-Parameter wie Mittelpunkt, Rotation und Skalierung korrekt angepasst werden. Statdessen wird eine Transformation zwischen Simulations- und Splat-Koordinatensystem berrechnet und gespeichert, mit der Trajektorien und Kameraposen entsprechend transformiert werden können.

**Abkürzungsverzeichnis:**  
- Spat-KS: Splat-Koordinatensystem
- FloorRaw-KS: Lokales Boden-Koordinatensystem direkt nach der Bodenvalidierung
- Sim-KS: Simulations-Koordinatensystem

---

## Pipeline

### Schritt 1: Bodenebene bestimmen und Koordinatentransformation erzeugen

#### 1A: Ebenen finden - Splatdatei auswählen und Boden-Ebenenkandidaten suchen

- **1.1: Gaussian Splat einlesen**  
  **Output:** geladene Splat-Daten, keine Datei

- **1.2: Mittelpunkte der Splats extrahieren**  
  **Output:** 3D-Punktwolke aus Splat-Zentren, keine Datei

- **1.3: Ebenenkandidaten mit RANSAC bestimmen**  
  **Schritte:**  
  1. Mit RANSAC eine Ebene aus (reduzierter) Punktwolke bestimmen -> Ebenengleichung + Inlier Indices  
  2. Inlier der gefundenen Ebene aus der Punktwolke entfernen -> Reduzierte Punktwolke  
  3. n-mal wiederholen, um n Ebenenkandidaten zu finden
  **Output:** Liste mit Ebenenkandidaten für Bodenebene, z.B. mit Boden, Wände, Decke, keine Datei

#### 1B: Boden wählen - Ebenenkandidaten anzeigen und richtige Bodenebene auswählen

- **1.4: Bodenebene interaktiv visualisieren und validieren**  
      Ebenenkandidaten werden in einer Top-Down-View dargestellt, damit der Nutzer die tatsächliche Bodenebene und die passende Ausrichtung auswählen kann.  
      **Herausforderung:** Boden und Decke müssen visuell unterscheidbar sein. Dafür wird eine Art Occupancy Map aus den Splat-Mittelpunkten abzüglich der Ebenen Inlier erzeugt, wobei nur ein einstellbarer Höhenbereich angezeigt wird, damit z.B. Deckenpunkte die Raumstruktur nicht verdecken.  
      **Mögliche Funktionen:** Ebenenkandidat wechseln, Ebene um 180° flippen, Anzuzeigender Höhenbereich per Slider anpassen 
      **Output:** validierte Bodenebene mit passender Ausrichtung im ursprünglichen Splat-Koordinatensystem, gewählter Höhenfilter, keine Datei

- **1.4: Lokales Boden-Koordinatensystem vorbereiten**  
      Aus der validierten Bodenebene wird ein FloorRaw-KS erzeugt. Darin liegt die Bodenebene auf z = 0, Punkte oberhalb der Ebene haben positive z-Werte und x/y bilden die Top-Down-Ansicht.  
      **Output:** normalisierte Bodenebene, Ebenenmittelpunkt, Basisvektoren und Transformation zwischen Splat-KS und FloorRaw-KS, keine Datei

#### 1C: Ausrichten - Raumrotation und XY-Ursprung manuell anpassen

- **1.5: Rotation um die Z-Achse manuell festlegen**  
      Die validierte Draufsicht aus dem FloorRaw-KS wird manuell so rotiert, dass der Raum möglichst parallel zur X- und Y-Achse im Sim-KS liegt. 
      Die Rotation um den Ursprung des FloorRaw-KS, der zunächst im Mittelpunkt der validierten Bodenebene liegt.
      **Output:** Rotationswinkel um die Z-Achse, keine Datei

- **1.5: XY-Ursprung manuell setzen**
      Ursprung von X und Y wird manuell in eine sinnvolle Raumecke verschoben.  
      **Output:** Verschiebung des Koordinatenursprungs und Transformation zwischen FloorRaw-KS und Sim-KS, keine Datei

- **(Skalierung festlegen)**  
  Referenzpunkte in Occupancy-Map angeben und über Angabe der tatsächlichen Länge im Raum, Skalierungsfaktor berechnen.  

#### 1D: Transformation - Gesamttransformation prüfen und speichern

- **1.6: Gesamttransformation zusammensetzen**  
  Bodenausrichtung, Rotation und XY-Ursprung werden zu einer Gesamttransformation kombiniert. Zusätzlich wird die inverse Transformation berechnet.  
  **Output:** `splats/<Splat-Name>/transform.yaml` mit Gesamttransformation und inverser Transformation zwischen Splat-KS und Sim-KS; 1.6b: + Transformation für SuperSplatEditor

- **1.6: Top-Down-Grid aus Sim-Koordinaten erzeugen**  
  Die Splat-Mittelpunkte werden mit der Gesamttransformation ins Sim-KS transformiert und innerhalb des gewählten Höhenbereichs als Occupancy Grid gespeichert.  
  **Output:** `splats/<Splat-Name>/top_down_grid.npz` mit Occupancy Grid, Zellengröße, Ursprung, Höhenbereich und Transformationsmatrizen

---

### Schritt 2. Trajektorie festlegen und Bilddaten generieren

#### 2A: Trajektorie - Trajektorie festlegen
- **2.1: Trajektorie auswählen**  
  - Trajektorie in Top-Down-View einzeichnen
  **Output:** Wegpunkte der geplanten Trajektorie in `splats/<Splat-Name>/trajectory.csv`

#### 2B: Kameraposen - Kameraposen generieren
- **2.2: Kamerapositionen entlang der Trajektorie generieren**  
  **Parameter:** z-Höhe, Spacing, Lookahead-Schritte, Glättungs-Durchläufe
  **Output:** `splats/<Splat-Name>/camera_poses_sim.csv` mit Kameraposen im Format x,y,z,yaw_deg im Sim-KS

#### 2C: SuperSplat-Export - Datei generieren um Kameraposen in SuperSplat Editor zu importieren und Video zu rendern
- **2.3: SuperSplat-Export vorbereiten**
  Aus `camera_poses_sim.csv` wird eine COLMAP-`images.txt` für den Import in SuperSplat erzeugt.  
  **Output:** `splats/<Splat-Name>/supersplat_camera_poses/images.txt` und Ordner `splats/<Splat-Name>/supersplat_video/` für die in SuperSplat gerenderte Videodatei.

---

### Schritt 3. Visuelle Lokalisierung und Evaluation
#### 3A: Daten vorbereiten - Daten für visuelle Odometrie vorbereiten
- **3.1: Datenformate für Visual Odometry generieren**
  **Input:** Videodatei (.mp4) aus Ordner `supersplat_video/`, `camera_poses_sim.csv`
  **Output:** `splats/<Splat-Name>/odometry_input/images/*.png` und `splats/<Splat-Name>/odometry_input/poses.txt`

#### 3B: Odometrie ausführen - Visuelle Odometrie ausführen
- **3.2: Lokalisierungsalgorithmus auf Bildsequenz anwenden**
  Visuelle Odometrie über OpenCV basierend auf: https://github.com/alishobeiri/Monocular-Video-Odometery/tree/master
  **Output:** `splats/<Splat-Name>/odometry_output/vo_output.csv` mit geschätzten und tatsächlichen Positionen uvm.

#### 3C: Evaluation - Evaluation der Ausgeführten Odometrie
- **3.3: Geschätzte Trajektorie mit echter Trajektorie vergleichen**  
  **Output:** Top-Down visualisierung zwischen Ursprünglicher Trajektorie und Schätzung durch Visual Odometry, keine Datei

---

## Offene Fragen



## ToDo's


### Optionale ToDo's
- Datenbasiertere Evaluation
