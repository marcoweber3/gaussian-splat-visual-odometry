"""Build and format the final step 1 transformation."""

import os

import numpy as np
import yaml


def build_final_transform(validated_floor_data, alignment_data):
    """Combine the 1B and 1C transforms"""

    T_splat_to_floor_raw = validated_floor_data["view_data"]["T_splat_to_floor_raw"]
    T_floor_raw_to_sim = alignment_data["T_floor_raw_to_sim"]

    T_splat_to_sim = T_floor_raw_to_sim @ T_splat_to_floor_raw
    T_sim_to_splat = np.linalg.inv(T_splat_to_sim)

    return {
        "T_splat_to_floor_raw": T_splat_to_floor_raw,
        "T_floor_raw_to_sim": T_floor_raw_to_sim,
        "T_splat_to_sim": T_splat_to_sim,
        "T_sim_to_splat": T_sim_to_splat,
    }


def matrix_to_euler_xyz_deg(rotation_matrix):
    """Convert rotation matrix to x/y/z angles in degrees for SuperSplat"""

    r = rotation_matrix

    # This value is near zero if the y-rotation is close to 90 degrees.
    # In that case x and z rotation cannot be separated clearly.
    sy = np.sqrt(r[0, 0] ** 2 + r[1, 0] ** 2)

    if sy > 0.000001:
        # normal case
        rotation_x = np.arctan2(r[2, 1], r[2, 2])
        rotation_y = np.arctan2(-r[2, 0], sy)
        rotation_z = np.arctan2(r[1, 0], r[0, 0])
    else:
        # fallback for nearly vertical rotation
        rotation_x = np.arctan2(-r[1, 2], r[1, 1])
        rotation_y = np.arctan2(-r[2, 0], sy)
        rotation_z = 0.0

    return np.degrees([rotation_x, rotation_y, rotation_z])


def build_sim_to_supersplat_transform():
    """Build transform from our z-up sim system to SuperSplat y-up system."""

    # SuperSplat uses y as up axis
    # Our sim system uses z as up axis
    return np.array([
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, -1.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ])


def transform_points(points, transform_matrix):
    """Apply a 4x4 transform to 3D points"""

    if len(points) == 0:
        return np.empty((0, 3))

    homogeneous_points = np.ones((len(points), 4))
    homogeneous_points[:, :3] = points

    transformed_points = homogeneous_points @ transform_matrix.T

    return transformed_points[:, :3]


def build_top_down_grid(points_sim, min_height, max_height, cell_size):
    """Build a top-down occupancy grid"""

    height_range = np.array([min_height, max_height])

    if len(points_sim) == 0:
        return np.zeros((0, 0), dtype=np.uint8), np.array([0.0, 0.0]), height_range, 0

    height_mask = (
        (points_sim[:, 2] >= min_height)
        & (points_sim[:, 2] <= max_height)
    )
    visible_points = points_sim[height_mask]

    if len(visible_points) == 0:
        return np.zeros((0, 0), dtype=np.uint8), np.array([0.0, 0.0]), height_range, 0

    x_values = visible_points[:, 0]
    y_values = visible_points[:, 1]

    x_min = x_values.min()
    x_max = x_values.max()
    y_min = y_values.min()
    y_max = y_values.max()

    origin_xy = np.array([x_min, y_min])

    index_epsilon = 1e-9

    cols = int(np.floor((x_max - x_min) / cell_size + index_epsilon)) + 1
    rows = int(np.floor((y_max - y_min) / cell_size + index_epsilon)) + 1

    col_indices = np.floor((x_values - x_min) / cell_size + index_epsilon).astype(int)
    row_indices = np.floor((y_values - y_min) / cell_size + index_epsilon).astype(int)

    col_indices = np.clip(col_indices, 0, cols - 1)
    row_indices = np.clip(row_indices, 0, rows - 1)

    occupancy_grid = np.zeros((rows, cols), dtype=np.uint8)
    occupancy_grid[row_indices, col_indices] = 1

    return occupancy_grid, origin_xy, height_range, len(visible_points)


def load_yaml_file(file_path):
    """Load YAML data, or return an empty dict."""

    if not os.path.isfile(file_path):
        return {}

    with open(file_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if data is None:
        data = {}

    return data


def save_yaml_file(file_path, data):
    """Save YAML data in readable order."""

    with open(file_path, "w", encoding="utf-8") as file:
        yaml.safe_dump(data, file, sort_keys=False, allow_unicode=True)


def update_splat_data_yaml(file_path, section_name, section_data):
    """Update one section of splat_data.yaml."""

    data = load_yaml_file(file_path)

    if section_name not in data or data[section_name] is None:
        data[section_name] = {}

    data[section_name].update(section_data)
    save_yaml_file(file_path, data)


def matrix_to_yaml_list(matrix):
    rows = []

    for row in matrix:
        rows.append([float(value) for value in row])

    return rows


def vector_to_yaml_list(values):
    return [float(value) for value in values]


def write_splat_data_yaml(
    file_path,
    splat_file_name,
    splat_file_path,
    project_folder,
    splat_count,
    T_splat_to_sim,
    T_sim_to_splat,
    T_splat_to_supersplat,
    supersplat_position,
    supersplat_rotation_deg,
):
    """Write basic splat data and transformations."""

    data = {
        "files": {
            "splat_file": splat_file_name,
            "original_splat_file_path": splat_file_path,
            "project_folder": project_folder,
            "splat_data_file_path": file_path,
        },
        "metadata": {
            "splat_count": int(splat_count),
        },
        "transforms": {
            "T_splat_to_supersplat": matrix_to_yaml_list(T_splat_to_supersplat),
            "supersplat_transform": {
                "coordinate_system_note": "SuperSplat uses y-up, sim uses z-up",
                "position_xyz": vector_to_yaml_list(supersplat_position),
                "rotation_xyz_deg": vector_to_yaml_list(supersplat_rotation_deg),
                "scale": 1.0,
            },
            "T_splat_to_sim": matrix_to_yaml_list(T_splat_to_sim),
            "T_sim_to_splat": matrix_to_yaml_list(T_sim_to_splat),
        },
    }

    save_yaml_file(file_path, data)


def write_top_down_grid(file_path, occupancy_grid, cell_size, origin_xy, height_range, T_splat_to_sim, T_sim_to_splat):
    """Write the top-down grid and metadata as compessed npz"""

    np.savez_compressed(
        file_path,
        occupancy_grid=occupancy_grid,
        cell_size=cell_size,
        origin_xy=origin_xy,
        height_range=height_range,
        T_splat_to_sim=T_splat_to_sim,
        T_sim_to_splat=T_sim_to_splat,
    )


def show_top_down_grid(grid_file_path):
    """Show a saved top-down grid in a Matplotlib window"""

    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    data = np.load(grid_file_path)
    occupancy_grid = data["occupancy_grid"]
    cell_size = float(data["cell_size"])
    origin_xy = data["origin_xy"]

    height = occupancy_grid.shape[0] * cell_size
    width = occupancy_grid.shape[1] * cell_size

    x_min = origin_xy[0]
    y_min = origin_xy[1]
    x_max = x_min + width
    y_max = y_min + height

    plt.figure("Occupancy Grid")
    plt.imshow(
        occupancy_grid,
        origin="lower",
        extent=[x_min, x_max, y_min, y_max],
        interpolation="nearest",
        cmap=ListedColormap(["white", "black"]),
        vmin=0,
        vmax=1,
    )
    plt.xlabel("x im Sim-KS")
    plt.ylabel("y im Sim-KS")
    plt.title("Occupancy Grid")
    plt.show()


def format_matrix(matrix):
    """Format a 4x4 matrix for UI output"""

    lines = []

    for row in matrix:
        formatted_values = []

        for value in row:
            formatted_values.append(format(value, "9.4f"))

        lines.append("[ " + " ".join(formatted_values) + " ]")

    return "\n".join(lines)
