"""
Authors: Paul Weigert & Marco Weber
"""

import os
from plyfile import PlyData


SPLAT_FILE = r"C:\Temp\PLY\point_cloud_2.ply"


def load_splat_file(file_path):
    """1.1: Load Gaussian Splat file in ply format"""

    if not os.path.exists(file_path):
        print("Datei wurde nicht gefunden:", file_path)
        return None

    splat_data = PlyData.read(file_path)
    return splat_data




def main():
    splat_data = load_splat_file(SPLAT_FILE)

    if splat_data is not None:
        print("Splatdatei wurde geladen")
        print(splat_data)


if __name__ == "__main__":
    main()
