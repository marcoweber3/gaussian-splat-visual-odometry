# Repo-Hinweise

### Git-Repo inklusive Submodule clonen
```bash
git clone --recurse-submodules https://github.com/marcoweber3/Monocular-Video-Odometery.git
```


---

Für die Paket- und Python-Umgebung wird Conda verwendet. Anaconda oder Miniconda wird empfolen, damit das Environment direkt über die `environment.yaml` erstellt werden kann.
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

## Repo-Struktur


- /src   -   Python-Code der Pipeline
- /extern   -   Submodule (Video Odometry)
- /splats   -   Aus spezifischem Splat generierte Daten


## Hinweise:

- Große Dateien wie z.B. Gaussian Splats werden nicht in Repo aufgenommen, sondern separat gespeichert.  
