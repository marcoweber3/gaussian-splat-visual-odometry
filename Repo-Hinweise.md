# Repo-Hinweise

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


## Hinweise:

- Große Dateien wie z.B. Gaussian Splats werden nicht in Repo aufgenammen, sondern separat gespeichert.  
