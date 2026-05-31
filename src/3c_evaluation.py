import csv
import os

import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np

splat_data_yaml = __import__("1d_build_transform")


def get_column_index(header, column_name):
    """Find a required CSV column."""

    if column_name not in header:
        raise ValueError("Spalte '" + column_name + "' fehlt in vo_output.csv")

    return header.index(column_name)


def load_odometry_csv(csv_file):
    """Load the columns needed for the evaluation."""

    estimated_x = []
    estimated_y = []
    true_x = []
    true_y = []
    tracked_features = []
    true_steps = []
    estimated_steps = []
    has_tracked_features = False

    with open(csv_file, "r", newline="", encoding="utf-8") as file:
        reader = csv.reader(file)
        header = next(reader, None)

        if header is None:
            raise ValueError("vo_output.csv ist leer")

        x_index = get_column_index(header, "x")
        y_index = get_column_index(header, "y")
        true_x_index = get_column_index(header, "true_x")
        true_y_index = get_column_index(header, "true_y")
        true_step_index = get_column_index(header, "true_step")
        estimated_step_index = get_column_index(header, "estimated_step")

        tracked_features_index = None
        if "tracked_features" in header:
            tracked_features_index = header.index("tracked_features")
            has_tracked_features = True

        for row_number, row in enumerate(reader, start=2):
            try:
                estimated_x.append(float(row[x_index]))
                estimated_y.append(float(row[y_index]))
                true_x.append(float(row[true_x_index]))
                true_y.append(float(row[true_y_index]))

                if has_tracked_features:
                    tracked_features.append(float(row[tracked_features_index]))

                true_steps.append(float(row[true_step_index]))
                estimated_steps.append(float(row[estimated_step_index]))
            except (IndexError, ValueError):
                raise ValueError("Ungültiger Wert in vo_output.csv, Zeile " + str(row_number))

    if len(estimated_x) == 0:
        raise ValueError("Keine Daten in vo_output.csv gefunden")

    if not has_tracked_features:
        tracked_features = None
    else:
        tracked_features = np.array(tracked_features)

    return (
        np.array(estimated_x),
        np.array(estimated_y),
        np.array(true_x),
        np.array(true_y),
        tracked_features,
        np.array(true_steps),
        np.array(estimated_steps),
    )


def draw_occupancy_grid(ax, grid_file):
    """Draw the saved occupancy grid if it exists."""

    if not os.path.isfile(grid_file):
        ax.text(0.5, 0.5, "top_down_grid.npz nicht gefunden", ha="center", va="center")
        return

    data = np.load(grid_file)
    occupancy_grid = data["occupancy_grid"]
    cell_size = float(data["cell_size"])
    origin_xy = data["origin_xy"]

    height = occupancy_grid.shape[0] * cell_size
    width = occupancy_grid.shape[1] * cell_size
    x_min = origin_xy[0]
    y_min = origin_xy[1]

    ax.imshow(
        occupancy_grid,
        origin="lower",
        extent=[x_min, x_min + width, y_min, y_min + height],
        interpolation="nearest",
        cmap=ListedColormap(["white", "black"]),
        vmin=0,
        vmax=1,
    )

    data.close()


def format_text_value(value):
    if value is None:
        return "-"

    return str(value)


def format_number_value(value):
    if value is None:
        return "-"

    return format(float(value), ".3f").replace(".", ",")


def calculate_turn_angles(true_x, true_y):
    angles = np.zeros(len(true_x))

    for index in range(2, len(true_x)):
        old_vector = np.array([true_x[index - 1] - true_x[index - 2], true_y[index - 1] - true_y[index - 2]])
        new_vector = np.array([true_x[index] - true_x[index - 1], true_y[index] - true_y[index - 1]])
        old_length = np.linalg.norm(old_vector)
        new_length = np.linalg.norm(new_vector)

        if old_length > 0.000001 and new_length > 0.000001:
            cos_angle = np.dot(old_vector, new_vector) / (old_length * new_length)
            angles[index] = np.degrees(np.arccos(np.clip(cos_angle, -1.0, 1.0)))

    return angles


def add_text_section(ax, y_position, title, lines):
    ax.text(0.0, y_position, title, va="top", fontweight="bold")
    y_position -= 0.09

    for line in lines:
        ax.text(0.0, y_position, line, va="top")
        y_position -= 0.075

    return y_position - 0.04


def plot_odometry_csv(csv_file, grid_file):
    """Plot estimated and true trajectory from vo_output.csv."""

    (
        estimated_x,
        estimated_y,
        true_x,
        true_y,
        tracked_features,
        true_steps,
        estimated_steps,
    ) = load_odometry_csv(csv_file)

    error_2d = np.sqrt((estimated_x - true_x) ** 2 + (estimated_y - true_y) ** 2)

    mean_error = float(np.mean(error_2d))
    max_error = float(np.max(error_2d))
    final_error = float(error_2d[-1])
    true_path_length = float(np.sum(true_steps))
    estimated_path_length = float(np.sum(estimated_steps))

    if true_path_length > 0.0:
        path_length_ratio = estimated_path_length / true_path_length
    else:
        path_length_ratio = 0.0

    evaluation_data = {
        "mean_error_2d": mean_error,
        "max_error_2d": max_error,
        "final_error_2d": final_error,
        "true_path_length": true_path_length,
        "estimated_path_length": estimated_path_length,
        "path_length_ratio": path_length_ratio,
    }

    if tracked_features is not None:
        evaluation_data["mean_tracked_features"] = float(np.mean(tracked_features))
        evaluation_data["min_tracked_features"] = float(np.min(tracked_features))

    splat_folder = os.path.dirname(os.path.dirname(csv_file))
    splat_data_file = os.path.join(splat_folder, "splat_data.yaml")
    splat_data_yaml.update_splat_data_yaml(splat_data_file, "evaluation", evaluation_data)
    splat_data = splat_data_yaml.load_yaml_file(splat_data_file)

    frame_index = np.arange(len(error_2d))
    turn_angles = calculate_turn_angles(true_x, true_y)

    plt.figure("Evaluation")
    plt.clf()
    figure = plt.gcf()
    figure.set_size_inches(14, 8)

    layout = figure.add_gridspec(
        2,
        3,
        width_ratios=[1.4, 0.8, 0.8],
        height_ratios=[1.0, 0.75],
    )

    map_ax = figure.add_subplot(layout[:, 0])
    diagnosis_ax = figure.add_subplot(layout[0, 1:])
    metadata_ax = figure.add_subplot(layout[1, 1])
    evaluation_ax = figure.add_subplot(layout[1, 2])

    # left: top-down comparison in occupancy grid.
    draw_occupancy_grid(map_ax, grid_file)
    map_ax.plot(true_x, true_y, "r-", label="Echte Trajektorie")
    map_ax.plot(estimated_x, estimated_y, "g-", label="Geschätzte Trajektorie")
    map_ax.set_xlabel("x")
    map_ax.set_ylabel("y")
    map_ax.set_title("Top-Down-Vergleich")
    map_ax.axis("equal")
    map_ax.grid(True)
    map_ax.legend()

    # right top: graph over frame
    diagnosis_ax.plot(frame_index, error_2d, color="red", label="Positionsfehler")
    diagnosis_ax.set_xlabel("Frame")
    diagnosis_ax.set_ylabel("Positionsfehler")
    diagnosis_ax.tick_params(axis="y", colors="red")
    diagnosis_ax.yaxis.label.set_color("red")
    diagnosis_ax.grid(True)

    if tracked_features is not None:
        feature_ax = diagnosis_ax.twinx()
        feature_ax.plot(frame_index, tracked_features, color="blue", alpha=0.75, label="Getrackte Features")
        feature_ax.set_ylabel("Getrackte Features")
        feature_ax.tick_params(axis="y", colors="blue")
        feature_ax.yaxis.label.set_color("blue")
        turn_ax = diagnosis_ax.twinx()
        turn_ax.spines["right"].set_position(("axes", 1.16))
    else:
        feature_ax = None
        turn_ax = diagnosis_ax.twinx()

    turn_ax.plot(frame_index, turn_angles, color="orange", alpha=0.9, label="Richtungsänderung")
    turn_ax.set_ylabel("Richtungsänderung [Grad]")
    turn_ax.tick_params(axis="y", colors="orange")
    turn_ax.yaxis.label.set_color("orange")

    lines_1, labels_1 = diagnosis_ax.get_legend_handles_labels()
    lines_2, labels_2 = turn_ax.get_legend_handles_labels()
    all_lines = lines_1 + lines_2
    all_labels = labels_1 + labels_2

    if feature_ax is not None:
        lines_3, labels_3 = feature_ax.get_legend_handles_labels()
        all_lines = all_lines + lines_3
        all_labels = all_labels + labels_3

    diagnosis_ax.legend(all_lines, all_labels, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3)
    diagnosis_ax.set_title("Diagnose über Frames")

    files = splat_data.get("files", {})
    metadata = splat_data.get("metadata", {})
    trajectory_generation = splat_data.get("trajectory_generation", {})
    camera_pose_generation = splat_data.get("camera_pose_generation", {})
    evaluation = splat_data.get("evaluation", {})

    metadata_ax.axis("off")
    y_pos = 1.0
    y_pos = add_text_section(metadata_ax, y_pos, "Splat-Daten:", [
        "Splat-Dateiname: " + format_text_value(files.get("splat_file")),
        "Splats: " + format_text_value(metadata.get("splat_count")),
        "Projektordner: " + format_text_value(files.get("project_folder")),
    ])
    y_pos = add_text_section(metadata_ax, y_pos, "Trajektorie:", [
        "Wegpunkte: " + format_text_value(trajectory_generation.get("waypoint_count")),
    ])
    add_text_section(metadata_ax, y_pos, "Kameraposen:", [
        "Kameraposen: " + format_text_value(camera_pose_generation.get("camera_pose_count")),
        "Kamerahöhe: " + format_number_value(camera_pose_generation.get("camera_height")),
        "Posenabstand: " + format_number_value(camera_pose_generation.get("pose_distance")),
        "Look-Ahead-Schritte: " + format_text_value(camera_pose_generation.get("look_ahead_steps")),
        "Glättungsdurchläufe: " + format_text_value(camera_pose_generation.get("smoothing_passes")),
    ])

    evaluation_lines = [
        "Mittlerer Positionsfehler (2D): " + format_number_value(evaluation.get("mean_error_2d")),
        "Maximaler Positionsfehler (2D): " + format_number_value(evaluation.get("max_error_2d")),
        "Endabweichung (2D): " + format_number_value(evaluation.get("final_error_2d")),
        "Echte Pfadlänge: " + format_number_value(evaluation.get("true_path_length")),
        "Geschätzte Pfadlänge: " + format_number_value(evaluation.get("estimated_path_length")),
        "Pfadlängenverhältnis: " + format_number_value(evaluation.get("path_length_ratio")),
    ]

    if tracked_features is not None:
        evaluation_lines.extend([
            "Durchschn. getrackte Features: " + format_number_value(evaluation.get("mean_tracked_features")),
            "Min. getrackte Features: " + format_number_value(evaluation.get("min_tracked_features")),
        ])
    else:
        evaluation_lines.append("Getrackte Features: Spalte fehlt")

    evaluation_lines.extend([
        "Grafik: short-evaluation/vo_short_eval.png",
    ])

    if true_path_length == 0.0:
        evaluation_lines.append("Hinweis: echte Pfadlänge ist 0")

    evaluation_ax.axis("off")
    add_text_section(evaluation_ax, 1.0, "Evaluation:", evaluation_lines)

    figure.suptitle("Visual Odometry Evaluation")
    figure.tight_layout(rect=[0, 0.04, 0.88, 0.96])
    evaluation_folder = os.path.join(splat_folder, "short-evaluation")
    os.makedirs(evaluation_folder, exist_ok=True)
    figure.savefig(os.path.join(evaluation_folder, "vo_short_eval.png"), dpi=150)

    top_down_figure, top_down_ax = plt.subplots(figsize=(8, 8))
    draw_occupancy_grid(top_down_ax, grid_file)
    top_down_ax.plot(true_x, true_y, "r-", label="Echte Trajektorie")
    top_down_ax.plot(estimated_x, estimated_y, "g-", label="Geschätzte Trajektorie")
    top_down_ax.set_xlabel("x")
    top_down_ax.set_ylabel("y")
    top_down_ax.set_title("Top-Down-Vergleich")
    top_down_ax.axis("equal")
    top_down_ax.grid(True)
    top_down_ax.legend()
    top_down_figure.tight_layout()
    top_down_figure.savefig(os.path.join(evaluation_folder, "vo_top_down_eval.png"), dpi=150)
    plt.close(top_down_figure)

def show_evaluation_window():
    plt.show()
