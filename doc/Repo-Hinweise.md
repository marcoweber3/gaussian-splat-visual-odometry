# Repo-Hinweise

### Git-Repo inklusive Submodule clonen
```bash
git clone --recurse-submodules https://github.com/marcoweber3/gaussian-splat-visual-localization.git
```


---

Für die Paket- und Python-Umgebung wird Conda verwendet. Anaconda oder Miniconda wird empfolen, damit das Environment direkt über die `environment.yaml` erstellt und mit weiteren Abhängigkeiten installiert werden kann.

### Environment erstellen

```bash
conda env create -f environment.yaml
```

### Environment aktivieren

```bash
conda activate splat-loc-sim-Env
```

### Environment aktualisieren
```bash
conda env update --file environment.yaml --prune
```

## Python Pipeline starten

Aus dem Repository-Hauptverzeichnis:

```powershell
python start_pipeline.py
```


### Detail-Evaluation ohne GUI starten

Wenn unter `evaluation/` bereits gespeicherte Trajektorienordner vorhanden sind, kann die PDF-Auswertung direkt per R erzeugt werden:

```powershell
Rscript render_evaluation_pdf.R
```

Ausgabe:

```text
evaluation/Benchmarking_Gaussian_Splatting.pdf
```

Für die PDF-Erzeugung muss eine LaTeX-Engine verfügbar sein. Im Conda-Environment ist dafür `tectonic` vorgesehen.

## Repo-Struktur


- /src   -   Python-Code und R-Code der Pipeline
- /extern   -   Submodule: Monocular-Video-Odometery
- /splats   -   Aus spezifischem Splat generierte Daten
- /evaluation   -   Evaluationsdaten zum rendern einer Detailevaluation

## Hinweise:

- Große Dateien wie z.B. Gaussian Splats werden nicht in Repo aufgenommen, sondern separat gespeichert.  
