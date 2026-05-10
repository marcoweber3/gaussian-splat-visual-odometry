"""
Authors: Paul Weigert & Marco Weber
"""

import os
import numpy as np
import open3d as o3d # https://www.open3d.org/docs/latest/tutorial/Basic/pointcloud.html
from plyfile import PlyData


SPLAT_FILE = r"C:\Temp\PLY\point_cloud_2.ply"

RANSAC_DISTANCE_THRESHOLD = 0.02 # max distance from plane to include a point as an inlier
RANSAC_N = 3 # number of initial points to test for ( 3 for a plane)
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

    point_cloud = np.vstack((x_points, y_points, z_points)).T # point_cloud = [x0, y0, z0], [x1, y1, z1], ...]

    return point_cloud


def find_plane_candidates(point_cloud, number_of_planes, distance_threshold, ransac_n, num_iterations):
    """1.3: Find multiple plane candidates with RANSAC"""

    open3d_point_cloud = o3d.geometry.PointCloud()
    open3d_point_cloud.points = o3d.utility.Vector3dVector(point_cloud)

    plane_candidates = []
    remaining_points = open3d_point_cloud

    for _ in range(number_of_planes):

        # https://www.open3d.org/docs/latest/python_api/open3d.geometry.PointCloud.html?utm=#:~:text=open3d.geometry.Geometry3D-,segment_plane,-(self%3A
        plane_model, inlier_points = remaining_points.segment_plane(distance_threshold, ransac_n, num_iterations)
        # return values: plane model (a, b, c, d) for plane equation ax + by + cz + d = 0, indices of inlier points to the plane
        
        plane_candidates.append((plane_model, inlier_points))

        remaining_points = remaining_points.select_by_index(inlier_points, invert=True) # remove inlier pioints from point cloud to get next plane candidates

    return plane_candidates



def main():
    splat_data = load_splat_file(SPLAT_FILE)

    if splat_data is not None:
        print("1.1: Splatdatei wurde geladen")
        print(splat_data)

        point_cloud = extract_splat_centers(splat_data)
        print("1.2: Punktwolke wurde extrahiert")
        print("Anzahl Punkte:", len(point_cloud))
        print("Erster Punkt:", point_cloud[0])

        plane_candidates = find_plane_candidates(
            point_cloud,
            NUMBER_OF_PLANES,
            RANSAC_DISTANCE_THRESHOLD,
            RANSAC_N,
            RANSAC_NUM_ITERATIONS
        )
        print("1.3: Ebenenkandidaten wurden gefunden")

        for i, plane_candidate in enumerate(plane_candidates):
            plane_model, inlier_points = plane_candidate
            print("Kandidat", i + 1, ":")
            print("\tEbenenmodell:", plane_model)
            print("\tAnzahl Inlier:", len(inlier_points))


if __name__ == "__main__":
    main()
