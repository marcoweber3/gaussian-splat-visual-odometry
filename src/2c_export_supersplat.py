"""Export camera poses as COLMAP images.txt for SuperSplat."""

import csv

import numpy as np
import yaml


def load_camera_poses_csv(file_path):
    """Load frame, x, y, z, yaw_deg from csv"""

    camera_poses = []

    # load camera poses
    with open(file_path, "r", newline="", encoding="utf-8") as file:
        reader = csv.reader(file)
        next(reader, None)

        for row in reader:
            frame = int(row[0])
            x = float(row[1])
            y = float(row[2])
            z = float(row[3])
            yaw_deg = float(row[4])
            camera_poses.append([frame, x, y, z, yaw_deg])

    return camera_poses


def sim_position_to_supersplat(position_sim):
    """Convert position from sim z-up to SuperSplat y-up."""

    # SuperSplat uses y as up axis
    # Our sim system uses z as up axis
    x = position_sim[0]
    y = position_sim[1]
    z = position_sim[2]

    return np.array([x, z, -y], dtype=float)


def sim_yaw_to_supersplat_forward(yaw_deg):
    """Convert sim yaw angle to SuperSplat forward vector."""

    yaw_rad = np.radians(yaw_deg)

    forward_sim = np.array([
        np.cos(yaw_rad),
        np.sin(yaw_rad),
        0.0,
    ])

    # convert sim coordinates to supersplat coordinates
    forward_super = np.array([
        forward_sim[0],
        forward_sim[2],
        -forward_sim[1],
    ])

    return forward_super


def supersplat_position_to_colmap_position(position_super):
    """Convert SuperSplat position to COLMAP import position."""

    # SuperSplat flips x and y when importing colmap poses
    return np.array([
        -position_super[0],
        -position_super[1],
        position_super[2],
    ], dtype=float)


def supersplat_forward_to_colmap_forward(forward_super):
    """Convert SuperSplat forward vector to COLMAP import forward vector."""

    # SuperSplat flips x and y when importing colmap poses
    return np.array([
        -forward_super[0],
        -forward_super[1],
        forward_super[2],
    ], dtype=float)


def build_colmap_pose(position_sim, yaw_deg):
    """Build one COLMAP world to camera pose."""

    position_super = sim_position_to_supersplat(position_sim)
    forward_super = sim_yaw_to_supersplat_forward(yaw_deg)

    camera_position_colmap = supersplat_position_to_colmap_position(position_super)
    forward_colmap = supersplat_forward_to_colmap_forward(forward_super)
    forward_colmap = forward_colmap / np.linalg.norm(forward_colmap)

    down_colmap = np.array([0.0, 1.0, 0.0])
    right_colmap = np.cross(down_colmap, forward_colmap)
    right_colmap = right_colmap / np.linalg.norm(right_colmap)

    down_colmap = np.cross(forward_colmap, right_colmap)
    down_colmap = down_colmap / np.linalg.norm(down_colmap)

    # columns are camera x, y and z axes in world coordinates
    R_c2w = np.column_stack((
        right_colmap,
        down_colmap,
        forward_colmap,
    ))

    # colmap stores world to camera transform
    R_w2c = R_c2w.T
    t_w2c = -R_w2c @ camera_position_colmap

    q = rotation_matrix_to_quaternion(R_w2c)

    return q, t_w2c


def rotation_matrix_to_quaternion(rotation_matrix):
    """Convert rotation matrix to quaternion qw, qx, qy, qz."""

    r = rotation_matrix
    trace = r[0, 0] + r[1, 1] + r[2, 2]

    if trace > 0:
        s = np.sqrt(trace + 1.0) * 2.0
        qw = 0.25 * s
        qx = (r[2, 1] - r[1, 2]) / s
        qy = (r[0, 2] - r[2, 0]) / s
        qz = (r[1, 0] - r[0, 1]) / s
    elif r[0, 0] > r[1, 1] and r[0, 0] > r[2, 2]:
        s = np.sqrt(1.0 + r[0, 0] - r[1, 1] - r[2, 2]) * 2.0
        qw = (r[2, 1] - r[1, 2]) / s
        qx = 0.25 * s
        qy = (r[0, 1] + r[1, 0]) / s
        qz = (r[0, 2] + r[2, 0]) / s
    elif r[1, 1] > r[2, 2]:
        s = np.sqrt(1.0 + r[1, 1] - r[0, 0] - r[2, 2]) * 2.0
        qw = (r[0, 2] - r[2, 0]) / s
        qx = (r[0, 1] + r[1, 0]) / s
        qy = 0.25 * s
        qz = (r[1, 2] + r[2, 1]) / s
    else:
        s = np.sqrt(1.0 + r[2, 2] - r[0, 0] - r[1, 1]) * 2.0
        qw = (r[1, 0] - r[0, 1]) / s
        qx = (r[0, 2] + r[2, 0]) / s
        qy = (r[1, 2] + r[2, 1]) / s
        qz = 0.25 * s

    q = np.array([qw, qx, qy, qz], dtype=float)

    # normalize quaternion
    q = q / np.linalg.norm(q)

    return q


def write_images_txt(camera_poses, output_file):
    """Write COLMAP images.txt."""

    camera_id = 1

    # write images.txt
    with open(output_file, "w", encoding="utf-8") as file:
        for image_id, pose in enumerate(camera_poses, start=1):
            frame = pose[0]
            position_sim = np.array([pose[1], pose[2], pose[3]], dtype=float)
            yaw_deg = pose[4]

            q, t = build_colmap_pose(position_sim, yaw_deg)
            image_name = f"frame_{frame:06d}.png"

            line = (
                str(image_id)
                + " "
                + format(q[0], ".6f")
                + " "
                + format(q[1], ".6f")
                + " "
                + format(q[2], ".6f")
                + " "
                + format(q[3], ".6f")
                + " "
                + format(t[0], ".6f")
                + " "
                + format(t[1], ".6f")
                + " "
                + format(t[2], ".6f")
                + " "
                + str(camera_id)
                + " "
                + image_name
            )

            file.write(line + "\n\n")


def load_supersplat_values_from_splat_data(file_path):
    """Read SuperSplat values from splat_data.yaml."""

    with open(file_path, "r", encoding="utf-8") as file:
        splat_data = yaml.safe_load(file)

    if splat_data is None:
        splat_data = {}

    transform_data = splat_data.get("transforms", {}).get("supersplat_transform", {})

    return transform_data.get("position_xyz"), transform_data.get("rotation_xyz_deg")
