"""Manual rotation and origin shift for step 1C."""

import numpy as np


def build_rotation_z(yaw_deg):
    """Build a 4x4 rotation around the z-axis."""

    yaw_rad = np.deg2rad(yaw_deg)
    cos_yaw = np.cos(yaw_rad)
    sin_yaw = np.sin(yaw_rad)

    transform = np.eye(4)
    transform[0, 0] = cos_yaw
    transform[0, 1] = -sin_yaw
    transform[1, 0] = sin_yaw
    transform[1, 1] = cos_yaw

    return transform


def build_floor_raw_to_sim_transform(yaw_deg, origin_x, origin_y):
    """Build transform from FloorRaw-KS to Sim-KS."""

    T_rotate_z = build_rotation_z(yaw_deg)

    T_origin = np.eye(4)
    T_origin[0, 3] = -origin_x
    T_origin[1, 3] = -origin_y

    return T_origin @ T_rotate_z


def build_sim_to_floor_raw_transform(yaw_deg, origin_x, origin_y):
    """Build inverse transform from Sim-KS to FloorRaw-KS."""

    T_floor_raw_to_sim = build_floor_raw_to_sim_transform(yaw_deg, origin_x, origin_y)

    return np.linalg.inv(T_floor_raw_to_sim)


def transform_points_2d(points_2d, yaw_deg, origin_x, origin_y):
    """Rotate 2D points and subtract the selected origin."""

    if len(points_2d) == 0:
        return np.empty((0, 2))

    yaw_rad = np.deg2rad(yaw_deg)
    cos_yaw = np.cos(yaw_rad)
    sin_yaw = np.sin(yaw_rad)

    x_values = points_2d[:, 0]
    y_values = points_2d[:, 1]

    rotated_x = cos_yaw * x_values - sin_yaw * y_values
    rotated_y = sin_yaw * x_values + cos_yaw * y_values

    sim_x = rotated_x - origin_x
    sim_y = rotated_y - origin_y

    return np.column_stack((sim_x, sim_y))
