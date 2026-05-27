"""
Generate view data for interactive floor validation.

Convert one plane candidate into a simple 2D top-down view
to help the user visually validate the floor candidate and select a height range.

"""

import numpy as np


def prepare_floor_candidate_view_data(points, plane_model, inlier_indices):
    """Prepare all data needed by the GUI for one plane candidate"""

    points = np.asarray(points, dtype=float)
    inlier_indices = np.asarray(inlier_indices, dtype=int)

    normal_vector, d = normalize_plane_model(plane_model)

    plane_points = get_points_by_indices(points, inlier_indices)
    other_points = get_points_without_indices(points, inlier_indices)

    normal_vector, d = choose_plane_orientation(other_points, normal_vector, d)

    plane_center = compute_center_point(plane_points)

    # Project the center onto the fitted plane so z=0 is exact.
    center_height = np.dot(plane_center, normal_vector) + d
    plane_center = plane_center - center_height * normal_vector

    basis_x, basis_y, basis_z = build_plane_basis(normal_vector)

    T_splat_to_floor_raw = build_splat_to_floor_raw_transform(
        plane_center,
        basis_x,
        basis_y,
        basis_z,
    )
    T_floor_raw_to_splat = build_floor_raw_to_splat_transform(
        plane_center,
        basis_x,
        basis_y,
        basis_z,
    )

    points_floor_raw = transform_points(points, T_splat_to_floor_raw)
    plane_points_floor_raw = get_points_by_indices(points_floor_raw, inlier_indices)
    other_points_floor_raw = get_points_without_indices(points_floor_raw, inlier_indices)

    plane_view_points = plane_points_floor_raw[:, :2]
    other_view_points = other_points_floor_raw[:, :2]
    other_heights = other_points_floor_raw[:, 2]

    positive_ratio = compute_positive_height_ratio(other_heights)

    return {
        "plane_model_splat": np.array([normal_vector[0], normal_vector[1], normal_vector[2], d]),
        "normal_vector": normal_vector,
        "d": d,
        "plane_center_splat": plane_center,
        "basis_x_splat": basis_x,
        "basis_y_splat": basis_y,
        "basis_z_splat": basis_z,
        "T_splat_to_floor_raw": T_splat_to_floor_raw,
        "T_floor_raw_to_splat": T_floor_raw_to_splat,
        "plane_view_points": plane_view_points,
        "other_view_points": other_view_points,
        "other_heights": other_heights,
        "orientation_info": {
            "positive_ratio": positive_ratio,
        },
    }


def normalize_plane_model(plane_model):
    """Normalize plane model ax + by + cz + d = 0"""

    plane_model = np.asarray(plane_model, dtype=float)

    normal_vector = plane_model[:3]
    normal_length = np.linalg.norm(normal_vector)

    if normal_length == 0:
        raise ValueError("Plane normal vector must not have length 0")

    normal_vector = normal_vector / normal_length
    d = plane_model[3] / normal_length

    return normal_vector, d


def get_points_by_indices(points, indices):
    """Return all points with the given indices"""

    if len(indices) == 0:
        return np.empty((0, 3))

    return points[indices]


def get_points_without_indices(points, indices_to_exclude):
    """Return all points except the points with the given indices"""

    if len(indices_to_exclude) == 0:
        return points

    all_indices = np.arange(len(points))
    remaining_indices = np.setdiff1d(all_indices, indices_to_exclude)

    return points[remaining_indices]


def compute_center_point(points):
    """Compute the center point of a point set"""

    if len(points) == 0:
        return np.zeros(3)

    return points.mean(axis=0)


def compute_signed_heights(points, normal_vector, d):
    """Compute signed distances of points to the plane"""

    if len(points) == 0:
        return np.empty(0)

    return points @ normal_vector + d


def choose_plane_orientation(points, normal_vector, d):
    """Flip the plane normal if most points are below the plane"""

    heights = compute_signed_heights(points, normal_vector, d)

    positive_count = np.sum(heights > 0)
    negative_count = np.sum(heights < 0)

    if negative_count > positive_count:
        normal_vector = -normal_vector
        d = -d

    return normal_vector, d


def build_plane_basis(normal_vector):
    """Build an orthonormal FloorRaw basis in Splat coordinates"""

    helper_vector = np.array([0.0, 0.0, 1.0])

    # If the plane normal is almost parallel to the z-axis,
    # the z-axis is not a good helper vector.
    if abs(np.dot(normal_vector, helper_vector)) > 0.9:
        helper_vector = np.array([1.0, 0.0, 0.0])

    basis_z = normal_vector

    basis_x = np.cross(helper_vector, basis_z)
    basis_x = basis_x / np.linalg.norm(basis_x)

    basis_y = np.cross(basis_z, basis_x)
    basis_y = basis_y / np.linalg.norm(basis_y)

    return basis_x, basis_y, basis_z


def build_splat_to_floor_raw_transform(origin_splat, basis_x, basis_y, basis_z):
    """Build transform from Splat-KS to FloorRaw-KS"""

    transform = np.eye(4)

    transform[0, :3] = basis_x
    transform[1, :3] = basis_y
    transform[2, :3] = basis_z

    transform[0, 3] = -np.dot(basis_x, origin_splat)
    transform[1, 3] = -np.dot(basis_y, origin_splat)
    transform[2, 3] = -np.dot(basis_z, origin_splat)

    return transform


def build_floor_raw_to_splat_transform(origin_splat, basis_x, basis_y, basis_z):
    """Build transform from FloorRaw-KS back to Splat-KS"""

    transform = np.eye(4)

    transform[:3, 0] = basis_x
    transform[:3, 1] = basis_y
    transform[:3, 2] = basis_z
    transform[:3, 3] = origin_splat

    return transform


def transform_points(points, transform):
    """Apply a 4x4 transform to 3D points"""

    if len(points) == 0:
        return np.empty((0, 3))

    homogeneous_points = np.ones((len(points), 4))
    homogeneous_points[:, :3] = points

    transformed_points = homogeneous_points @ transform.T

    return transformed_points[:, :3]


def compute_positive_height_ratio(heights):
    """Compute how many points lie on the positive side of the plane"""

    if len(heights) == 0:
        return 0.0

    positive_count = np.sum(heights > 0)
    positive_ratio = positive_count / len(heights)

    return positive_ratio


def filter_points_by_height(view_data, min_height, max_height):
    """Return all visible points within the selected height range"""

    heights = view_data["other_heights"]
    view_points = view_data["other_view_points"]

    lower_height = min(min_height, max_height)
    upper_height = max(min_height, max_height)
    lower_height = max(lower_height, 0.000001)

    visible_indices = []

    for index, height in enumerate(heights):
        if lower_height <= height <= upper_height:
            visible_indices.append(index)

    visible_indices = np.asarray(visible_indices, dtype=int)

    return view_points[visible_indices], heights[visible_indices]


def sample_points_for_drawing(points, max_points):
    """Reduce the number of points for faster drawing in the GUI"""

    if len(points) <= max_points:
        return points

    step_size = max(1, len(points) // max_points)

    return points[::step_size]
