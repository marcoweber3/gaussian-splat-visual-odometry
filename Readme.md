# Pipeline zur Simulation und Evaluation visueller Lokalisierung in 3D-Gaussian-Splat-Umgebungen

## Hinweise zur Nutzung

Dieses Tool ist ein Python-basiertes GUI-Tool, mit dem eine Pipeline Schritt für Schritt durchlaufen werden kann. Aus einer 3D-Gaussian-Splat-Umgebung werden simulierte Kamerabilder und Referenzdaten erzeugt, um Verfahren zur visuellen Lokalisierung unter kontrollierten Bedingungen untersuchen und evaluieren zu können.

Aus einer Gaussian-Splat-Datei im `.ply`-Format werden zunächst eine Bodenebene und eine passende Ausrichtung des Raums bestimmt. Daraus werden eine Transformation sowie ein Occupancy Grid erzeugt, das als Grundlage für die weitere Simulation dient.

Auf dem Occupancy Grid kann anschließend eine Fahrtrajektorie eingezeichnet werden. Entlang dieser Trajektorie werden Kameraposen aus Sicht eines Roboters berechnet und für den Import in den [SuperSplat Editor](https://superspl.at/editor) vorbereitet, um dort Bilddaten bzw. ein Video zu rendern.

Die erzeugten Bilddaten werden anschließend zusammen mit der bekannten Referenztrajektorie von einer Visual Odometry verarbeitet.  
Die verwendete Visual Odometry basiert auf der OpenCV-basierten Monocular Visual Odometry von [Avi Singh](https://github.com/avisingh599/mono-vo). Als Python-Implementierung wurde das Repository „[Monocular-Video-Odometry](https://github.com/alishobeiri/Monocular-Video-Odometery/tree/master)“ von Ali Shobeiri als Grundlage verwendet und im Rahmen dieses Projekts um zusätzliche Auswertungsmetriken sowie die automatische Speicherung relevanter Evaluationsdaten erweitert.

Dadurch können die geschätzte Trajektorie und die Ground Truth verglichen und die Ergebnisse visualisiert werden. Nach einem Visual-Odometry-Lauf kann eine kurze Evaluation des ausgeführten Laufs angezeigt werden. Zusätzlich kann über ein R-Skript eine ausführlichere PDF-Evaluation erstellt werden.

### Einschränkungen

Das Tool wurde mit Gaussian Splats unterschiedlicher Auflösungsstufen des Vorlesungsraums T1.1.08 der Hochschule Pforzheim validiert.  
Die Nutzung mit anderen Gaussian-Splat-Umgebungen ist grundsätzlich möglich. Für gute Ergebnisse sollte die Szene jedoch über eine ausreichend ebene Bodenfläche und einen klar abgegrenzten Raumbereich verfügen. Da aktuell keine automatische Filterung entfernter Splat-Mittelpunkte erfolgt, können weit außerhalb des relevanten Bereichs liegende Punkte die Darstellung beeinflussen. Dadurch kann der eigentliche Raum in den Visualisierungen sehr klein erscheinen, was die manuelle Ausrichtung erschwert.


## Grundprinzip

Die Pipeline besteht aus drei Hauptschritten:

1. **Bodenebene bestimmen und Koordinatentransformation erzeugen**
2. **Trajektorie festlegen, Kameraposen generieren und Bilddaten generieren**
3. **Visual Odometry vorbereiten, ausführen und Ergebnisse evaluieren**

Die Hauptschritte 1, 2 und 3 sowie die Zwischenschritte (z. B. 1A, 1B usw.) bauen aufeinander auf. 


## Typischer Ablauf

1A. Splat-Datei auswählen und Kandidaten für die Bodenebene suchen  
1B. Bodenebene validieren und relevanten Bereich für Occupancy Grid einstellen  
1C. Raum ausrichten und Ursprung setzen  
1D. Transformation zuwischen ausgerichtetem Simulations- und Splat-Koordinatensystem und Occupancy-Grid generieren  
2A. Trajektorie einzeichnen  
2B. Kameraposen mit gewünschten Parametern generieren  
2C. Kameraposen im Format für SuperSplat generieren und Video im SuperSplat Editor rendern  
3A. Bilder und Ground-Truth für Visual Odometry vorbereiten  
3B. Visual Odometry ausführen und Ausgabe speichern  
3C. Kompakte Evaluation anzeigen und Evaluationsdaten speichern  
3D. Ausführliche PDF-Evaluation vorbereiten, generieren und anzeigen

## Projektordner

Für jede in 1A ausgewählte Splat-Datei wird nach der Transformationsberechnung in Schritt 1D ein eigener Splat-Ordner unter `splats/<splat file name>` angelegt.

In diesem Ordner werden die Ergebnisse und Daten der einzelnen Schritte gespeichert, ergänzt und abgerufen. Dadurch kann nach einem Neustart oder Programmabsturz an einem späteren Schritt weitergearbeitet werden.

Hierzu wird in Schritt 2A bzw. Schritt 3A der passende Splat-Ordner ausgewählt, um vorhandene Daten zu lesen und neue Daten zu schreiben.

Ein Schritt kann beliebig erneut ausgeführt werden, dann werden bereits vorhandene Ergebnisse im zugehörigen Ordner überschrieben.

Beispielsweise können aus derselben gespeicherten Transformation und Trajektorie mehrfach Kameraposen mit unterschiedlichen Parametern für eine vergleichbare Evaluation generiert werden. Sollen die zuvor generierten Daten bestehen bleiben, kann der entsprechende Splat-Ordner kopiert und umbenannt werden.

### OK-Markierungen

Die Tabs der einzelnen Zwischenschritte werden mit `[OK]` markiert, sobald die jeweils benötigten Ausgabedaten vorhanden sind. Das kann direkt nach dem Ausführen eines Schritts passieren oder beim erneuten Öffnen bzw. Auswählen eines vorhandenen Splat-Ordners, wenn die passenden Dateien bereits vorhanden sind.  
Die OK-Anzeige bedeutet also: Die Daten für diesen Schritt liegen vor und der nächste Schritt kann darauf aufbauen. Fehlen Dateien oder wurde ein Schritt noch nicht ausgeführt, bleibt der Tab offen markiert.


## Setup

Für die Paket- und Python-Umgebung wird Conda verwendet. Anaconda oder Miniconda wird empfohlen, damit das Environment direkt über die `environment.yaml` erstellt und mit weiteren Abhängigkeiten installiert werden kann.

### Environment erstellen

```bash
conda env create -f environment.yaml
```

### Environment aktivieren

```bash
conda activate splat-loc-sim-Env
```

## Starten

Die GUI der Pipeline wird aus dem Repository-Hauptverzeichnis gestartet über:

```powershell
python start_pipeline.py
```


Die ausführliche PDF-Evaluation aus Schritt 3D kann auch direkt über R erzeugt werden, sofern im zentralen Ordner `evaluation/` bereits gespeicherte Trajektorienordner liegen:

```powershell
Rscript render_evaluation_pdf.R
```

Die PDF wird unter `evaluation/Benchmarking_Gaussian_Splatting.pdf` gespeichert.  
Für die PDF-Erzeugung muss eine LaTeX-Engine verfügbar sein. Im Conda-Environment ist dafür `tectonic` vorgesehen.


---
TODO: Detailierter Ablauf 
## Detailierter Ablauf 

---
