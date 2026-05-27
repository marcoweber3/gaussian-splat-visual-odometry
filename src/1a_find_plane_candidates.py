"""
Authors: Paul Weigert & Marco Weber
"""

import os
import numpy as np
import open3d as o3d # https://www.open3d.org/docs/latest/tutorial/Basic/pointcloud.html
from plyfile import PlyData


SPLAT_FILE = r"C:\Temp\PLY\point_cloud_2.ply"

RANSAC_DISTANCE_THRESHOLD = 0.05 # max distance from plane to include a point as an inlier
RANSAC_N = 3 # number of initial points to test for (3 for a plane)
RANSAC_NUM_ITERATIONS = 1000 # iterations to test different planes
NUMBER_OF_PLANES = 5 # how many plane candidates should be found


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

    x_points = splats["x"] # [x0, x1, x2, ...]
    y_points = splats["y"]
    z_points = splats["z"]

    point_cloud = np.vstack((x_points, y_points, z_points)).T # point_cloud = [[x0, y0, z0], [x1, y1, z1], ...]

    return point_cloud


def find_plane_candidates(point_cloud, number_of_planes, distance_threshold, ransac_n, num_iterations):
    """1.3: Find multiple plane candidates with RANSAC"""

    open3d_point_cloud = o3d.geometry.PointCloud()
    open3d_point_cloud.points = o3d.utility.Vector3dVector(point_cloud)

    plane_candidates = []
    remaining_points = open3d_point_cloud
    remaining_indices = np.arange(len(point_cloud))

    for _ in range(number_of_planes):

        # https://www.open3d.org/docs/latest/python_api/open3d.geometry.PointCloud.html?utm=#:~:text=open3d.geometry.Geometry3D-,segment_plane,-(self%3A
        plane_model, inlier_points = remaining_points.segment_plane(distance_threshold, ransac_n, num_iterations)
        # return values: plane model (a, b, c, d) for plane equation ax + by + cz + d = 0, indices of inlier points to the plane

        original_inlier_points = remaining_indices[inlier_points]
        plane_candidates.append((plane_model, original_inlier_points))

        remaining_points = remaining_points.select_by_index(inlier_points, invert=True) # remove inlier points from point cloud to get next plane candidates
        remaining_indices = np.delete(remaining_indices, inlier_points)

    return plane_candidates



def run_step_1a(splat_file, status_callback):
    """1A: Load splat file and find plane candidates"""

    status_callback("1.1: Lade Splatdatei...\n")
    splat_data = load_splat_file(splat_file)

    if splat_data is None:
        status_callback("\tSplatdatei konnte nicht geladen werden\n")
        return None

    status_callback("\tSplatdatei wurde geladen\n\n")

    status_callback("1.2: Extrahiere Splat-Mittelpunkte...\n")
    point_cloud = extract_splat_centers(splat_data)
    status_callback("\tPunktwolke wurde extrahiert\n")
    status_callback("\tAnzahl Punkte: " + str(len(point_cloud)) + "\n\n")

    status_callback("1.3: Suche Kandidaten fuer Bodenebene...\n")
    plane_candidates = find_plane_candidates(
        point_cloud,
        NUMBER_OF_PLANES,
        RANSAC_DISTANCE_THRESHOLD,
        RANSAC_N,
        RANSAC_NUM_ITERATIONS
    )

    status_callback("\tEbenenkandidaten gefunden\n")

    for i, plane_candidate in enumerate(plane_candidates):
        plane_model, inlier_points = plane_candidate
        status_callback("\t\tKandidat " + str(i + 1) + ":\n")
        status_callback("\t\t\tEbenenmodell: " + str(plane_model) + "\n")
        status_callback("\t\t\tAnzahl Inlier: " + str(len(inlier_points)) + "\n")

    return splat_data, point_cloud, plane_candidates


def main():
    run_step_1a(SPLAT_FILE, print)


if __name__ == "__main__":
    main()
