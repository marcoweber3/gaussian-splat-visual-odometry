"""
Authors: Paul Weigert & Marco Weber
"""

import os
import numpy as np
from plyfile import PlyData


SPLAT_FILE = r"C:\Temp\PLY\point_cloud_2.ply"


def load_splat_file(file_path):
    """1.1: Load Gaussian Splat file in ply format"""

    if not os.path.exists(file_path):
        print("Datei wurde nicht gefunden:", file_path)
        return None

    splat_data = PlyData.read(file_path)
    return splat_data


def extract_splat_centers(splat_data):
    """1.2: Extract x, y, z position of every splat center"""

    splats = splat_data["vertex"]
    print("Splats geladen:")
    print(splats)

    x_points = splats["x"] # [x0, x1, x2, ...]
    y_points = splats["y"]
    z_points = splats["z"]

    point_cloud = np.vstack((x_points, y_points, z_points)).T # point_cloud = [x0, y0, z0], [x1, y1, z1], ...]

    return point_cloud



def main():
    splat_data = load_splat_file(SPLAT_FILE)

    if splat_data is not None:
        print("1.1: Splatdatei wurde geladen")
        print(splat_data)

        point_cloud = extract_splat_centers(splat_data)
        print("1.2: Punktwolke wurde extrahiert")
        print("Anzahl Punkte:", len(point_cloud))
        print("Erster Punkt:", point_cloud[0])


if __name__ == "__main__":
    main()
