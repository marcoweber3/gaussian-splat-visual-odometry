# Pipeline zur Simulation und Evaluation visueller Lokalisierung in 3D-Gaussian-Splat-Umgebungen

## Projektübersicht

Ziel ist es, aus einer 3D-Gaussian-Splat-Umgebung simulierte Kamerabilder aus sicht eines Roboters zu erzeugen.  
Diese Bilddaten sollen anscließend genutzt werden, um visuelle Lokalisierungs- bzw. Odometrie-Algorithmen zu testen und mit der ursprünglichen simulierten Fahrtrajektorie zu vergleichen.

Der Gaussian Splat selbst soll erstmal unverändert bleiben, weil ein direktes Umschreiben der Datei fehleranfällig wäre. Typische Splat-Dateien besitzen keine einfache globale Achsen- oder Ursprungseinstellung, daher müssten einzelne Splat-Parameter wie Mittelpunkt, Rotation und Skalierung korrekt angepasst werden. Statdessen wird eine Transformation zwischen Simulations- und Splat-Koordinatensystem berrechnet und gespeichert, mit der Trajektorien und Kameraposen entsprechend transformiert werden können.

**Abkürzungsverzeichnis:**  
- Spat-KS: Splat-Koordinatensystem
- Sim-KS: Simulations-Koordinatensystem

---

## Pipeline

### 1. Zusätzliche Daten aus dem Gaussian Splat gewinnen, Koordinaten-Transformation berechnen

- **1.1: Gaussian Splat einlesen**  
  **Output:** geladene Splat-Daten

- **Mittelpunkte der Splats extrahieren**  
  **Output:** 3D-Punktwolke aus Splat-Zentren

- **Ebenenkandidaten mit RANSAC bestimmen**  
  **Output:** Liste mit Ebenenkandidaten für Bodenebene, z.B. mit Boden, Wände, Decke

- **(Ebenenkandidaten über Metriken bewerten)**  
  **Mögliche Metriken:** Inlier-Anzahl, Flächengröße...  
  **Output:** vorsortierte Ebenenkandidaten

- **Bodenebene interaktiv visualisieren und validieren**  
  Ebenenkandidaten werden in einer Top-Down-View dargestellt, damit der Nutzer die tatsächliche Bodenebene und die passende Ausrichtung auswählen kann.  
  **Herausforderung:** Boden und Decke müssen visuell unterscheidbar sein. Dafür wird eine Art Occupancy Map aus den Splat-Mittelpunkten abzüglich der Ebenen Inlier erzeugt, wobei nur ein einstellbarer Höhenbereich angezeigt wird, damit z.B. Deckenpunkte die Raumstruktur nicht verdecken.  
  **Mögliche Funktionen:** Ebenenkandidat wechseln, Ebene um 180° flippen, Anzuzeigender Höhenbereich per Slider anpassen, (Höhenhistogramm anzeigen)  
  **Output:** validierte Bodenebene mit passender Ausrichtung im ursprünglichen Splat-Koordinatensystem

- **Transformation für Bodenebene berechnen**  
  Aus der validierten Bodenebene wird berechnet, wie diese auf z = 0 gelegt werden kann.  
  **Output:** Transformation für die Bodenausrichtung

- **Rotation um die Z-Achse manuell festlegen**  
  Raum manuell möglichst parallel zur X- und Y-Achse ausrichten.  
  **Output:** Korrektur für Raumorientierung

- **XY-Ursprung manuell setzen**  
  Nullpunkt von X und Y manell in einer Raumecke plazieren.  
  **Output:** Verschiebung des Koordinatenursprungs

- **(Skalierung festlegen)**  
  Referenzpunkte in Occupancy-Map angeben und über Angabe der tatsächlichen Länge im Raum, Skalierungsfaktor berechnen.  
  **Output:** Skalierungsfaktor

- **Gesamttransformation zusammensetzen**  
  Bodenausrchtung, Rotation, Ursprung und Skalierung werden zu einer Gesamttransformation kombiniert.  
  **Output:** Gesamttransformation und inverse Transformation zwischen Splat-KS und Sim-KS

---

### 2. Fahrweg festlegen und Bilddaten generieren

- **Fahrweg auswählen**  
  Mögliche Varianten:
  - Trajektorie in Top-Down-View einzeichnen
  - manuelle Steuerung mit W, A, S, D 
  (**Herausforderung:** "Glätten" der Trajektorie zur Simulation einer Fahrphysik)  
  **Output:** Geplante oder aufgezeichnete Fahrtrajektorie im 

- **Kamerapositionen entlang des Fahrwegs bestimmen**  
  **Parameter:** z-Höhe, Spacing, "Kameraintrinsik", ...  
  **Output:** Folge von Kameraposen im Sim-KS

- **Kameraposen für das Rendering transformieren**  
  Die Kameraposen werden passend zum ursprünglichen Gaussian Splat transformiert.  
  **Output:** Koordinaten der Kameraposen im ursprünglichen Splat-KS

- **Simulierte Kamerabilder im Gaussian Splat erzeugen**  
  Bilder aus sicht des Roboters entlang der Trajektorie.  
  **Output:** Bildsequenz für den Lokalisierungsalgorithmus

---

### 3. Lokalisierung auswerten

- **Lokalisierungsalgorithmus auf Bildsequenz anwenden**  
  Visuelle Odometrie oder SLAM.  
  **Output:** geschätzte Kameraposen / geschätzte Trajektorie

- **Geschätzte Trajektorie mit echter Trajektorie vergleichen**  
  **Output:** Abweichung und Top-Down visualisierung zwischen Ursprünglicher Trajektorie und Schätzung durch Algo

- **Bewertung der Lokalisierungsqualität**  
  **Output:** Fehlermaße

---

## Offene Fragen

- Welche Grenzwerte / Metriken für sinnvolle Ebenenauswahl?
- Top-Down-Trajektorie oder WASD-Steuerung?
- Konvertierung von gewählter Trajektorie zu Kameraposen?
- Welche Lokalisierungsalgorithmen sollen getestet werden?

