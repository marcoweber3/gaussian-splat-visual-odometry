import csv
import os
import shutil
import subprocess
import sys
import threading
import dearpygui.dearpygui as dpg
from pathlib import Path
from tkinter import Tk
from tkinter import filedialog

step1 = __import__("1a_find_plane_candidates")
floor_view = __import__("1b_interactive_floor_validation")
floor_alignment = __import__("1c_manual_floor_alignment")
final_transform = __import__("1d_build_transform")
camera_pose_generator = __import__("2b_generate_camera_poses")
supersplat_export = __import__("2c_export_supersplat")
visual_odometry_prepare = __import__("3a_prepare_visual_odometry_data")
odometry_evaluation = __import__("3c_evaluation")


STEP_OPEN = "[  ]"
STEP_DONE = "[OK]"
STEP3_OUTPUT_FOLDER_NAME = "odometry_input"
STEP3_ODOM_OUTPUT_FOLDER_NAME = "odometry_output"
STEP3_IMAGES_FOLDER_NAME = "images"
STEP3_POSES_FILE_NAME = "poses.txt"
SPLAT_DATA_FILE_NAME = "splat_data.yaml"
SHORT_EVALUATION_FOLDER_NAME = "short-evaluation"
SHORT_EVALUATION_IMAGE_NAME = "vo_short_eval.png"
TOP_DOWN_EVALUATION_IMAGE_NAME = "vo_top_down_eval.png"
EVALUATION_METADATA_FILE_NAME = "metadata.csv"

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

HEADING_COLOR = (34*2, 83*2, 118*2)
INSTRUCTION_COLOR = (248, 236, 185)
OUTPUT_COLOR = (180, 180, 180)
BUTTON_COLOR = (68, 64, 50, 255)
BUTTON_HOVER_COLOR = (86, 80, 60, 255)
BUTTON_ACTIVE_COLOR = (52, 49, 39, 255)
PREVIEW_MAX_POINTS = 10000

step1_point_cloud = None
step1_plane_candidates = None
step1_floor_view_cache = {}
step1_validated_floor_data = None
step1_alignment_data = None
step1_final_transform_data = None
step2_splat_output_dir = None
step2_camera_poses = None
step2_images_txt_path = None
step3_odom_data_path = None



# select ply file
def show_file_dialog():
    root = Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        title="Splatdatei auswählen",
        filetypes=[("PLY Dateien", "*.ply"), ("Alle Dateien", "*.*")]
    )
    root.destroy()

    if file_path:
        dpg.set_value("splat_file_input", file_path)


def set_tab_done(tab, text):
    # mark tab as finished: "[OK] ..."
    dpg.set_item_label(tab, STEP_DONE + " " + text)


def set_tab_open(tab, text):
    if dpg.does_item_exist(tab):
        dpg.set_item_label(tab, STEP_OPEN + " " + text)


def get_floor_candidate_view_data():
    if step1_point_cloud is None or step1_plane_candidates is None:
        return None

    selected_candidate = dpg.get_value("floor_candidate_combo")
    if selected_candidate == "":
        return None

    candidate_number = int(selected_candidate.replace("Kandidat ", ""))

    # prepare and cache view data for the selected candidate
    if candidate_number not in step1_floor_view_cache:
        plane_model, inlier_points = step1_plane_candidates[candidate_number - 1]
        step1_floor_view_cache[candidate_number] = floor_view.prepare_floor_candidate_view_data(
            step1_point_cloud,
            plane_model,
            inlier_points,
        )

    return step1_floor_view_cache[candidate_number]


def is_latest_callback_value(sender, app_data):
    if sender is None:
        return True

    return dpg.get_value(sender) == app_data


def draw_floor_preview(view_data, visible_points):
    """draw area for top-down preview of plane candidate"""

    width = 700
    height = 420
    border = 20
    screen_center_x = width / 2
    screen_center_y = height / 2

    dpg.draw_rectangle((0, 0), (width, height), color=(80, 80, 80, 255), parent="floor_candidate_preview")

    plane_points = view_data["plane_view_points"]

    if len(plane_points) == 0:
        dpg.draw_text((20, 20), "Dieser Kandidat hat keine Inlier", parent="floor_candidate_preview")
        return

    # bound of map (area covered by plane inliers) for scaling and centering
    x_min = plane_points[:, 0].min()
    x_max = plane_points[:, 0].max()
    y_min = plane_points[:, 1].min()
    y_max = plane_points[:, 1].max()

    center_x = (x_min + x_max) / 2
    center_y = (y_min + y_max) / 2

    map_width = x_max - x_min + 0.000001
    map_height = y_max - y_min + 0.000001

    draw_width = width - 2 * border
    draw_height = height - 2 * border

    # scale
    scale_x = draw_width / map_width
    scale_y = draw_height / map_height
    scale = min(scale_x, scale_y)

    floor_left = screen_center_x + (x_min - center_x) * scale
    floor_right = screen_center_x + (x_max - center_x) * scale
    floor_top = screen_center_y - (y_max - center_y) * scale
    floor_bottom = screen_center_y - (y_min - center_y) * scale

    dpg.draw_rectangle(
        (floor_left, floor_top),
        (floor_right, floor_bottom),
        color=(0, 180, 80, 190),
        fill=(0, 180, 80, 35),
        parent="floor_candidate_preview"
    )

    visible_points = floor_view.sample_points_for_drawing(visible_points, PREVIEW_MAX_POINTS)

    for point in visible_points:
        point_x = point[0]
        point_y = point[1]

        screen_x = screen_center_x + (point_x - center_x) * scale
        screen_y = screen_center_y - (point_y - center_y) * scale

        dpg.draw_rectangle(
            (screen_x, screen_y),
            (screen_x + 1, screen_y + 1),
            color=(0, 0, 0, 0),
            fill=(190, 190, 190, 90),
            parent="floor_candidate_preview"
        )


def draw_floor_candidate(sender=None, app_data=None, user_data=None):
    """redraw top-down-view of plane candidate when candidate selection or height sliders change"""
    
    if not is_latest_callback_value(sender, app_data):
        return

    dpg.delete_item("floor_candidate_preview", children_only=True)

    if step1_point_cloud is None or step1_plane_candidates is None:
        dpg.draw_text((20, 20), "Erst Ebenenkandidaten in 1A suchen", parent="floor_candidate_preview")
        return

    view_data = get_floor_candidate_view_data()

    if view_data is None:
        dpg.draw_text((20, 20), "Kein Kandidat ausgewählt", parent="floor_candidate_preview")
        return

    # read sliders and compute visible height range
    height_a = dpg.get_value("floor_min_height_slider")
    height_b = dpg.get_value("floor_max_height_slider")
    min_height = min(height_a, height_b)
    max_height = max(height_a, height_b)

    # show simple orientation info (percentage of points above plane)
    orientation_info = view_data["orientation_info"]
    status_text = "Oberseite automatisch bestimmt: " + format(orientation_info["positive_ratio"] * 100, ".1f") + " % der Punkte liegen oberhalb der Ebene"
    dpg.set_value("floor_orientation_status", status_text)
    dpg.set_value(
        "floor_height_status",
        "Sichtbarer Höhenbereich: "
        + format(min_height, ".2f")
        + " bis "
        + format(max_height, ".2f")
        + " über der Bodenebene"
    )

    visible_points, _ = floor_view.filter_points_by_height(view_data, min_height, max_height)

    draw_floor_preview(view_data, visible_points)


def reset_floor_alignment_state():
    """Reset stored 1C alignment and GUI controls"""

    global step1_alignment_data
    global step1_final_transform_data

    step1_alignment_data = None
    step1_final_transform_data = None

    if dpg.does_item_exist("alignment_yaw_slider"):
        dpg.set_value("alignment_yaw_slider", 0.0)
        dpg.set_value("alignment_origin_x_slider", 0.0)
        dpg.set_value("alignment_origin_y_slider", 0.0)

    if dpg.does_item_exist("1c_output_text"):
        dpg.set_value("1c_output_text", "")

    if dpg.does_item_exist("1d_output_text"):
        dpg.set_value("1d_output_text", "")

    if dpg.does_item_exist("floor_alignment_preview"):
        draw_floor_alignment()


def reset_final_transform_state():
    """Reset stored 1D transformation"""

    global step1_final_transform_data

    step1_final_transform_data = None

    if dpg.does_item_exist("1d_output_text"):
        dpg.set_value("1d_output_text", "")


def get_alignment_slider_values():
    """Read current 1C slider values"""

    yaw_deg = dpg.get_value("alignment_yaw_slider")
    origin_x = dpg.get_value("alignment_origin_x_slider")
    origin_y = dpg.get_value("alignment_origin_y_slider")

    return yaw_deg, origin_x, origin_y


def get_alignment_visible_points():
    """Rebuild the 1C point set from the validated 1B state"""

    if step1_validated_floor_data is None:
        return None

    view_data = step1_validated_floor_data["view_data"]
    height_filter = step1_validated_floor_data["height_filter"]

    visible_points_2d, visible_heights = floor_view.filter_points_by_height(
        view_data,
        height_filter["min_height"],
        height_filter["max_height"],
    )

    return visible_points_2d, visible_heights


def draw_alignment_preview(points_2d):
    """Draw transformed 1C points with simple x/y axes"""

    width = 700
    height = 420
    border = 20

    dpg.draw_rectangle((0, 0), (width, height), color=(80, 80, 80, 255), parent="floor_alignment_preview")

    if len(points_2d) == 0:
        dpg.draw_text((20, 20), "Keine Punkte im validierten Höhenbereich", parent="floor_alignment_preview")
        return

    x_min = min(points_2d[:, 0].min(), 0.0)
    x_max = max(points_2d[:, 0].max(), 0.0)
    y_min = min(points_2d[:, 1].min(), 0.0)
    y_max = max(points_2d[:, 1].max(), 0.0)

    center_x = (x_min + x_max) / 2
    center_y = (y_min + y_max) / 2

    scale_x = (width - 2 * border) / (x_max - x_min + 0.000001)
    scale_y = (height - 2 * border) / (y_max - y_min + 0.000001)
    scale = min(scale_x, scale_y)

    def to_screen(point):
        x = width / 2 + (point[0] - center_x) * scale
        y = height / 2 - (point[1] - center_y) * scale
        return x, y

    x_axis_start = to_screen([x_min, 0.0])
    x_axis_end = to_screen([x_max, 0.0])
    y_axis_start = to_screen([0.0, y_min])
    y_axis_end = to_screen([0.0, y_max])
    origin = to_screen([0.0, 0.0])

    dpg.draw_line(x_axis_start, x_axis_end, color=(220, 80, 80, 180), thickness=1, parent="floor_alignment_preview")
    dpg.draw_line(y_axis_start, y_axis_end, color=(80, 180, 90, 180), thickness=1, parent="floor_alignment_preview")
    dpg.draw_circle(origin, 4, color=(255, 255, 255, 220), fill=(255, 255, 255, 120), parent="floor_alignment_preview")

    points_2d = floor_view.sample_points_for_drawing(points_2d, PREVIEW_MAX_POINTS)

    for point in points_2d:
        x, y = to_screen(point)
        dpg.draw_rectangle(
            (x, y),
            (x + 1, y + 1),
            color=(0, 0, 0, 0),
            fill=(190, 190, 190, 100),
            parent="floor_alignment_preview"
        )


def draw_floor_alignment(sender=None, app_data=None, user_data=None):
    """Redraw 1C alignment preview"""

    if not is_latest_callback_value(sender, app_data):
        return

    dpg.delete_item("floor_alignment_preview", children_only=True)

    if step1_validated_floor_data is None:
        dpg.draw_text((20, 20), "Erst Bodenebene in 1B validieren", parent="floor_alignment_preview")
        dpg.set_value("1c_alignment_status", "Erst Bodenebene in 1B validieren")
        return

    alignment_points = get_alignment_visible_points()

    if alignment_points is None:
        dpg.draw_text((20, 20), "Erst Bodenebene in 1B validieren", parent="floor_alignment_preview")
        dpg.set_value("1c_alignment_status", "Erst Bodenebene in 1B validieren")
        return

    visible_points_2d, _ = alignment_points
    yaw_deg, origin_x, origin_y = get_alignment_slider_values()
    sim_points_2d = floor_alignment.transform_points_2d(
        visible_points_2d,
        yaw_deg,
        origin_x,
        origin_y,
    )

    draw_alignment_preview(sim_points_2d)

    dpg.set_value(
        "1c_alignment_status",
        "Vorschau: "
        + str(len(visible_points_2d))
        + " Punkte aus dem validierten Höhenbereich"
    )


def accept_floor_alignment():
    """Store the selected 1C alignment for later step 1D"""

    global step1_alignment_data

    dpg.set_value("1c_output_text", "")

    def show_status(new_text):
        old_text = dpg.get_value("1c_output_text")
        dpg.set_value("1c_output_text", old_text + new_text)
        dpg.render_dearpygui_frame()

    if step1_validated_floor_data is None:
        show_status("Erst Bodenebene in 1B validieren\n")
        draw_floor_alignment()
        return

    yaw_deg, origin_x, origin_y = get_alignment_slider_values()

    # matrix for 1D
    T_floor_raw_to_sim = floor_alignment.build_floor_raw_to_sim_transform(
        yaw_deg,
        origin_x,
        origin_y,
    )
    T_sim_to_floor_raw = floor_alignment.build_sim_to_floor_raw_transform(
        yaw_deg,
        origin_x,
        origin_y,
    )

    step1_alignment_data = {
        "yaw_deg": yaw_deg,
        "origin_x": origin_x,
        "origin_y": origin_y,
        "T_floor_raw_to_sim": T_floor_raw_to_sim,
        "T_sim_to_floor_raw": T_sim_to_floor_raw,
    }
    reset_final_transform_state()

    show_status("Ausrichtung übernommen\n")
    show_status("\tRotation um Z: " + format(yaw_deg, ".2f") + " Grad\n")
    show_status("\tUrsprung X: " + format(origin_x, ".2f") + "\n")
    show_status("\tUrsprung Y: " + format(origin_y, ".2f") + "\n\n")
    show_status("Fahre mit Schritt 1D fort")

    set_tab_done("step1_tab_1c", "1C: Ausrichten")


def calculate_final_transform():
    """Calculate and show the final step 1 transform"""

    global step1_final_transform_data

    dpg.set_value("1d_output_text", "")

    def show_status(new_text):
        old_text = dpg.get_value("1d_output_text")
        dpg.set_value("1d_output_text", old_text + new_text)
        dpg.render_dearpygui_frame()

    if step1_validated_floor_data is None:
        show_status("Erst Bodenebene in 1B validieren\n")
        return

    if step1_alignment_data is None:
        show_status("Erst Ausrichtung in 1C übernehmen\n")
        return

    # final transform
    step1_final_transform_data = final_transform.build_final_transform(
        step1_validated_floor_data,
        step1_alignment_data,
    )

    splat_file = dpg.get_value("splat_file_input")
    splat_file_path = os.path.abspath(splat_file)
    splat_file_name = os.path.basename(splat_file)
    splat_name = os.path.splitext(splat_file_name)[0]
    output_dir = os.path.join("splats", splat_name)
    output_dir_exists = os.path.isdir(output_dir)

    if output_dir_exists:
        shutil.rmtree(output_dir)

    os.makedirs(output_dir, exist_ok=True)

    splat_data_file_path = os.path.join(output_dir, SPLAT_DATA_FILE_NAME)
    grid_file_path = os.path.join(output_dir, "top_down_grid.npz")

    T_splat_to_sim = step1_final_transform_data["T_splat_to_sim"]
    T_sim_to_splat = step1_final_transform_data["T_sim_to_splat"]

    # get transform values for supersplat
    # y-up systim
    T_sim_to_supersplat = final_transform.build_sim_to_supersplat_transform()
    T_splat_to_supersplat = T_sim_to_supersplat @ T_splat_to_sim
    supersplat_position = T_splat_to_supersplat[:3, 3]
    supersplat_rotation_deg = final_transform.matrix_to_euler_xyz_deg(T_splat_to_supersplat[:3, :3])

    height_filter = step1_validated_floor_data["height_filter"]
    min_height = height_filter["min_height"]
    max_height = height_filter["max_height"]
    cell_size = 0.05

    # points for occupancy grid
    points_sim = final_transform.transform_points(step1_point_cloud, T_splat_to_sim)
    occupancy_grid, origin_xy, height_range, visible_point_count = final_transform.build_top_down_grid(
        points_sim,
        min_height,
        max_height,
        cell_size,
    )

    final_transform.write_splat_data_yaml(
        splat_data_file_path,
        splat_file_name,
        splat_file_path,
        output_dir,
        len(step1_point_cloud),
        T_splat_to_sim,
        T_sim_to_splat,
        T_splat_to_supersplat,
        supersplat_position,
        supersplat_rotation_deg,
    )
    final_transform.write_top_down_grid(
        grid_file_path,
        occupancy_grid,
        cell_size,
        origin_xy,
        height_range,
        T_splat_to_sim,
        T_sim_to_splat,
    )

    step1_final_transform_data["output_dir"] = output_dir
    step1_final_transform_data["splat_data_yaml"] = splat_data_file_path
    step1_final_transform_data["top_down_grid"] = grid_file_path
    step1_final_transform_data["T_splat_to_supersplat"] = T_splat_to_supersplat
    step1_final_transform_data["supersplat_position"] = supersplat_position
    step1_final_transform_data["supersplat_rotation_deg"] = supersplat_rotation_deg
    if dpg.does_item_exist("splat_output_folder_input"):
        dpg.set_value("splat_output_folder_input", output_dir)
    if dpg.does_item_exist("3a_splat_output_folder_input"):
        dpg.set_value("3a_splat_output_folder_input", output_dir)

    show_status("Gesamttransformation berechnet: Occupancy Grid prüfen\n")

    if visible_point_count == 0:
        show_status("Fehler: Keine Punkte im gewählten Höhenbereich gefunden\n\n")

    show_status("Transformation und Grid gespeichert in: " + output_dir + "\n")
    if output_dir_exists:
        show_status("Hinweis: Vorhandener Ausgabeordner wurde überschrieben\n")
    show_status("\tDateien:\n")
    show_status("\t\tsplat_data.yaml\n")
    show_status("\t\ttop_down_grid.npz\n\n")

    show_status("SuperSplat Transformationswerte (Y-up):\n")
    show_status("\tHinweis: Unser Sim-KS nutzt Z als Höhe. SuperSplat nutzt Y als Höhe. Daher wurden die Achsen für diese Werte umgerechnet.\n")
    show_status(
        "\tOptionale Kontrolle in SuperSplat (https://superspl.at/editor): Nach Importieren der Splat-Datei und Eingabe der folgenden\n"
        + "\tWerte im Feld 'TRANSFORMATION' sollte das Grid horizontal auf dem Boden liegen und der Ursprung korrekt positioniert sein.\n\n"
    )
    show_status(
        "\t\tPosition:\tX: " + format(supersplat_position[0], ".4f")
        + "\tY: " + format(supersplat_position[1], ".4f")
        + "\tZ: " + format(supersplat_position[2], ".4f")
        + "\n\n"
    )
    show_status(
        "\t\tRotation:\tX: " + format(supersplat_rotation_deg[0], ".2f")
        + "\tY: " + format(supersplat_rotation_deg[1], ".2f")
        + "\tZ: " + format(supersplat_rotation_deg[2], ".2f")
        + "\n\n"
    )
    show_status("\t\tSkalierung: 1\n\n")

    show_status(50 * "-" + "\n\n")
    show_status("Transformation von Splat- zu Simulations-Koordinatensystem: \n\n")
    show_status("T_splat_to_sim:\n")
    show_status(final_transform.format_matrix(T_splat_to_sim))

    show_status("\n\nTransformation von Simulations- zu Splat-Koordinatensystem: \n\n")
    show_status("T_sim_to_splat:\n")
    show_status(final_transform.format_matrix(T_sim_to_splat))
    show_status("\n\n")

    show_status("Klappe Schritt 1 zu und fahre mit Schritt 2A fort")

    set_tab_done("step1_tab_1d", "1D: Transformation")


def show_saved_top_down_grid():
    """Open the saved top-down grid in Matplotlib"""

    def show_status(new_text):
        old_text = dpg.get_value("1d_output_text")
        dpg.set_value("1d_output_text", old_text + new_text)
        dpg.render_dearpygui_frame()

    if step1_final_transform_data is None:
        show_status("Erst Transformation und Grid berechnen\n")
        return

    if "top_down_grid" not in step1_final_transform_data:
        show_status("Erst Transformation und Grid berechnen\n")
        return

    final_transform.show_top_down_grid(step1_final_transform_data["top_down_grid"])


def set_step2a_status(text):
    dpg.set_value("2a_output_text", text)
    dpg.render_dearpygui_frame()


def select_splat_output_folder():
    """Select a splats/... output folder for step 2"""

    global step2_splat_output_dir
    global step3_odom_data_path

    root = Tk()
    root.withdraw()

    initial_dir = "splats"
    if not os.path.isdir(initial_dir):
        initial_dir = "."

    # selection for splat output folder
    selected_folder = filedialog.askdirectory(
        title="Splat-Ordner auswählen",
        initialdir=initial_dir,
    )
    root.destroy()

    if not selected_folder:
        return

    selected_folder = os.path.normpath(selected_folder)
    dpg.set_value("splat_output_folder_input", selected_folder)
    if dpg.does_item_exist("3a_splat_output_folder_input"):
        dpg.set_value("3a_splat_output_folder_input", selected_folder)
    step2_splat_output_dir = selected_folder

    odom_data_path = os.path.join(selected_folder, STEP3_OUTPUT_FOLDER_NAME)
    if os.path.isdir(odom_data_path):
        step3_odom_data_path = odom_data_path
    else:
        step3_odom_data_path = None

    # files from step 1D
    grid_file_path = os.path.join(selected_folder, "top_down_grid.npz")
    splat_data_file_path = os.path.join(selected_folder, SPLAT_DATA_FILE_NAME)
    splat_data_status = "splat_data.yaml gefunden"
    if not os.path.isfile(splat_data_file_path):
        splat_data_status = "splat_data.yaml nicht gefunden"

    if not os.path.isfile(grid_file_path):
        set_step2a_status("top_down_grid.npz nicht gefunden\n" + splat_data_status)
        return

    set_step2a_status("top_down_grid.npz gefunden\n" + splat_data_status)

    if os.path.isfile(os.path.join(selected_folder, "trajectory.csv")):
        set_tab_done("step2_tab_2a", "2A: Trajektorie")

    if os.path.isfile(os.path.join(selected_folder, "camera_poses_sim.csv")):
        set_tab_done("step2_tab_2b", "2B: Kameraposen")

    if os.path.isfile(os.path.join(selected_folder, "supersplat_camera_poses", "images.txt")):
        set_tab_done("step2_tab_2c", "2C: SuperSplat Export")

    image_output_dir = os.path.join(odom_data_path, STEP3_IMAGES_FOLDER_NAME)
    poses_output_file = os.path.join(odom_data_path, STEP3_POSES_FILE_NAME)
    if os.path.isdir(image_output_dir) and os.path.isfile(poses_output_file):
        set_tab_done("step3_tab_3a", "3A: Daten vorbereiten")

    if os.path.isfile(os.path.join(selected_folder, STEP3_ODOM_OUTPUT_FOLDER_NAME, "vo_output.csv")):
        set_tab_done("step3_tab_3b", "3B: Odometrie ausführen")

    update_step3_evaluation_statuses()


def load_top_down_grid(grid_file_path):
    """Load the grid values needed for trajectory drawing"""

    import numpy as np

    # npz file from step 1D
    data = np.load(grid_file_path)
    occupancy_grid = data["occupancy_grid"].copy()

    # size per grid cell in Sim coordinates
    cell_size = float(data["cell_size"])
    origin_xy = data["origin_xy"].copy()

    data.close()

    return occupancy_grid, cell_size, origin_xy


def save_trajectory_csv(file_path, points_xy):
    # save trajectory point list for 2a
    with open(file_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["point_index", "x", "y"])

        for index, point in enumerate(points_xy):
            writer.writerow([index, format(point[0], ".6f"), format(point[1], ".6f")])


def draw_trajectory_on_grid(grid_file_path, trajectory_file_path):
    """Draw waypoints on top-down grid"""

    import matplotlib
    matplotlib.use("TkAgg", force=True)
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    # load map and scale values from the selected splat folder
    occupancy_grid, cell_size, origin_xy = load_top_down_grid(grid_file_path)

    if occupancy_grid.size == 0:
        return None, "top_down_grid.npz ist leer"

    height = occupancy_grid.shape[0] * cell_size
    width = occupancy_grid.shape[1] * cell_size

    # sim coordinates for matplotlib axes
    x_min = origin_xy[0]
    y_min = origin_xy[1]
    x_max = x_min + width
    y_max = y_min + height

    points_xy = []
    saved_points_xy = []
    last_mouse_xy = None
    title_text = "W: Wegpunkt setzen , E: letzten Wegpunkt entfernen\nEnter: speichern , Schließen: verwerfen\nFür Kurven: mehrere Punkte eng setzen"

    # create matplotlib window
    fig, ax = plt.subplots(num="Trajektorie einzeichen")

    # draw grid
    ax.imshow(
        occupancy_grid,
        origin="lower",
        extent=[x_min, x_max, y_min, y_max],
        interpolation="nearest",
        cmap=ListedColormap(["white", "black"]),
        vmin=0,
        vmax=1,
    )
    ax.set_xlabel("x im Sim-KS")
    ax.set_ylabel("y im Sim-KS")
    ax.set_title(title_text)

    #line is updated when new waypoint is added
    trajectory_line, = ax.plot([], [], "o-", color="tab:red", linewidth=1, markersize=3)

    def redraw_line():
        # x and y values as separate lists for matplotlib
        x_values = [point[0] for point in points_xy]
        y_values = [point[1] for point in points_xy]
        trajectory_line.set_data(x_values, y_values)
        fig.canvas.draw_idle()

    def on_mouse_move(event):
        nonlocal last_mouse_xy

        if event.inaxes != ax:
            return

        if event.xdata is None or event.ydata is None:
            return

        last_mouse_xy = [float(event.xdata), float(event.ydata)]

    def on_key(event):
        if event.key == "w":
            if last_mouse_xy is None:
                ax.set_title("Maus erst in die Karte bewegen")
                fig.canvas.draw_idle()
                return

            # add point
            points_xy.append(last_mouse_xy.copy())
            ax.set_title(title_text)
            redraw_line()
            return

        if event.key == "e":
            if len(points_xy) > 0:
                points_xy.pop()
                ax.set_title(title_text)
                redraw_line()
            return

        if event.key == "enter":
            if len(points_xy) < 2:
                ax.set_title("Mindestens zwei Wegpunkte setzen")
                fig.canvas.draw_idle()
                return

            # Copy the points into this list so we know Enter was pressed.
            saved_points_xy.clear()
            saved_points_xy.extend(points_xy)
            save_trajectory_csv(trajectory_file_path, saved_points_xy)
            plt.close(fig)

    fig.canvas.mpl_connect("motion_notify_event", on_mouse_move)
    fig.canvas.mpl_connect("key_press_event", on_key)

    plt.show()

    # window closed without Enter, nothing is saved
    if len(saved_points_xy) == 0:
        return None, "Verworfen"

    return len(saved_points_xy), "Trajektorie gespeichert"


def start_trajectory_drawing():
    """Start step 2A trajectory drawing for the selected splat folder"""

    global step2_splat_output_dir

    selected_folder = dpg.get_value("splat_output_folder_input").strip()

    if selected_folder == "":
        set_step2a_status("Erst einen Splat-Ordner auswählen")
        return

    selected_folder = os.path.normpath(selected_folder)
    dpg.set_value("splat_output_folder_input", selected_folder)
    if dpg.does_item_exist("3a_splat_output_folder_input"):
        dpg.set_value("3a_splat_output_folder_input", selected_folder)
    step2_splat_output_dir = selected_folder

    # selected folder must contain .npz file from step 1d
    grid_file_path = os.path.join(selected_folder, "top_down_grid.npz")

    if not os.path.isfile(grid_file_path):
        set_step2a_status("top_down_grid.npz nicht gefunden")
        return

    trajectory_file_path = os.path.join(selected_folder, "trajectory.csv")

    # open matplotlib and wait until the user saves or closes window
    point_count, result_message = draw_trajectory_on_grid(grid_file_path, trajectory_file_path)

    if point_count is None:
        set_step2a_status(result_message)
        return

    final_transform.update_splat_data_yaml(
        os.path.join(selected_folder, SPLAT_DATA_FILE_NAME),
        "trajectory_generation",
        {"waypoint_count": int(point_count)},
    )

    set_step2a_status(
        result_message
        + "\n"
        + trajectory_file_path
        + "\n"
        + str(point_count)
        + " Wegpunkte"
        + "\n\nFahre mit Schritt 2B fort"
    )
    set_tab_done("step2_tab_2a", "2A: Trajektorie")


def set_step2b_status(text):
    dpg.set_value("2b_output_text", text)
    dpg.render_dearpygui_frame()


def generate_camera_poses():
    """Generate camera poses from trajectory.csv"""

    global step2_camera_poses

    step2_camera_poses = None

    if step2_splat_output_dir is None:
        set_step2b_status("Erst einen Splat-Ordner unter 2A auswählen")
        return

    try:
        camera_height = float(dpg.get_value("camera_height_input"))
    except (TypeError, ValueError):
        set_step2b_status("Ungültige Kamerahöhe")
        return

    try:
        pose_spacing = float(dpg.get_value("pose_spacing_input"))
        lookahead_steps = int(dpg.get_value("lookahead_steps_input"))
        smoothing_rounds = int(dpg.get_value("smoothing_rounds_input"))
    except (TypeError, ValueError):
        set_step2b_status("Ungültige 2B-Einstellung")
        return

    if pose_spacing <= 0:
        set_step2b_status("Posen-Abstand muss größer 0 sein")
        return

    if lookahead_steps < 1:
        set_step2b_status("Lookahead-Schritte müssen mindestens 1 sein")
        return

    if smoothing_rounds < 0:
        set_step2b_status("Glättungsrunden dürfen nicht negativ sein")
        return

    trajectory_file_path = os.path.join(step2_splat_output_dir, "trajectory.csv")
    camera_poses_file_path = os.path.join(step2_splat_output_dir, "camera_poses_sim.csv")

    if not os.path.isfile(trajectory_file_path):
        set_step2b_status("trajectory.csv nicht gefunden")
        return

    try:
        # load the manually drawn waypoints from step 2A
        waypoints = camera_pose_generator.load_trajectory_csv(trajectory_file_path)

        # create camera positions in a fixed distance
        points = camera_pose_generator.create_evenly_spaced_points(waypoints, pose_spacing)

        # smooth hard corners in the trajectory
        points = camera_pose_generator.smooth_points(points, smoothing_rounds)

        # calculate the looking direction for every camera point
        yaw_angles = camera_pose_generator.compute_yaw_angles(points, lookahead_steps)

        # combine frame, position and yaw in one list
        step2_camera_poses = camera_pose_generator.build_camera_poses(points, camera_height, yaw_angles,)

        # save poses to csv in the same folder in case program crashes
        camera_pose_generator.save_camera_poses_csv(camera_poses_file_path, step2_camera_poses)

    except ValueError as error:
        set_step2b_status(str(error))
        return

    final_transform.update_splat_data_yaml(
        os.path.join(step2_splat_output_dir, SPLAT_DATA_FILE_NAME),
        "camera_pose_generation",
        {
            "camera_pose_count": len(step2_camera_poses),
            "camera_height": camera_height,
            "pose_distance": pose_spacing,
            "look_ahead_steps": lookahead_steps,
            "smoothing_passes": smoothing_rounds,
        },
    )

    set_step2b_status(
        "Kameraposen generiert\n\n"
        + "Wegpunkte: "
        + str(len(waypoints))
        + "\n"
        + "Kameraposen: "
        + str(len(step2_camera_poses))
        + "\n"
        + "Datei: "
        + camera_poses_file_path
        + "\n"
        + "Posen-Abstand: "
        + format(pose_spacing, ".2f")
        + "\n"
        + "Kamerahöhe: "
        + format(camera_height, ".2f")
        + "\n"
        + "Lookahead-Schritte: "
        + str(lookahead_steps)
        + "\n"
        + "Glättung: "
        + str(smoothing_rounds)
        + " Runden"
        + "\n\nFahre mit Schritt 2C fort"
    )
    set_tab_done("step2_tab_2b", "2B: Kameraposen")


def set_step2c_status(text):
    dpg.set_value("2c_output_text", text)
    dpg.render_dearpygui_frame()


def export_supersplat_images_txt():
    """Export camera poses as images.txt for SuperSplat"""

    global step2_images_txt_path

    step2_images_txt_path = None

    if step2_splat_output_dir is None:
        set_step2c_status("Erst einen Splat-Ordner unter 2A auswählen")
        return

    selected_folder = step2_splat_output_dir

    camera_poses_file_path = os.path.join(selected_folder, "camera_poses_sim.csv")
    splat_data_file_path = os.path.join(selected_folder, SPLAT_DATA_FILE_NAME)

    if not os.path.isfile(camera_poses_file_path):
        set_step2c_status("camera_poses_sim.csv nicht gefunden")
        return

    if not os.path.isfile(splat_data_file_path):
        set_step2c_status("splat_data.yaml nicht gefunden")
        return

    set_step2c_status("images.txt wird erzeugt...")

    try:
        camera_poses = supersplat_export.load_camera_poses_csv(camera_poses_file_path)

        if len(camera_poses) == 0:
            set_step2c_status("Keine Kameraposen gefunden")
            return

        # fixed output folder for SuperSplat poses
        output_folder = os.path.join(selected_folder, "supersplat_camera_poses")
        os.makedirs(output_folder, exist_ok=True)

        images_txt_path = os.path.join(output_folder, "images.txt")

        # folder for the rendered SuperSplat video
        video_folder = os.path.join(selected_folder, "supersplat_video")
        os.makedirs(video_folder, exist_ok=True)

        # write images.txt
        supersplat_export.write_images_txt(camera_poses, images_txt_path)

        # read transform values for instructions
        supersplat_position, supersplat_rotation_deg = supersplat_export.load_supersplat_values_from_splat_data(splat_data_file_path)
        splat_data = final_transform.load_yaml_file(splat_data_file_path)
    except Exception as error:
        set_step2c_status("Fehler beim Erzeugen der images.txt:\n" + str(error))
        return

    step2_images_txt_path = images_txt_path
    original_splat_file_path = splat_data.get("files", {}).get("original_splat_file_path", "")

    position_text = "Transformationswerte bitte aus splat_data.yaml übernehmen:\n" + splat_data_file_path + "\n\n"
    rotation_text = ""

    if supersplat_position is not None and supersplat_rotation_deg is not None:
        position_text = (
            "\tPosition:\t"
            + "\tX: " + format(supersplat_position[0], ".4f")
            + "\tY: " + format(supersplat_position[1], ".4f")
            + "\tZ: " + format(supersplat_position[2], ".4f")
            + "\n\n"
        )
        rotation_text = (
            "\tRotation:\t"
            + "\tX: " + format(supersplat_rotation_deg[0], ".2f")
            + "\tY: " + format(supersplat_rotation_deg[1], ".2f")
            + "\tZ: " + format(supersplat_rotation_deg[2], ".2f")
            + "\n\n"
        )

    set_step2c_status(
        "images.txt erzeugt:\n"
        + images_txt_path
        + "\n\n"
        + "\n\n"
        + "Nächste Schritte in SuperSplat:\n\n"
        + "1. SuperSplat Editor öffnen:\n"
        + "   https://superspl.at/editor\n\n"
        + "2. Zugehörige Splat-Datei (.ply) durch Drag & Drop im SuperSplat Editor laden:\n\n\t"
        + original_splat_file_path
        + "\n\n"
        + "3. Im Bereich Transformation diese Werte eintragen:\n\n"
        + position_text
        + rotation_text
        + "\tSkalierung: 1\n\n"
        + "4. Kameraposen über 'Datei' -> 'Importieren...' durch folgende Datei importieren:\n\n\t"
        + os.path.abspath(images_txt_path)
        + "\n\n"
        + "\tDadurch werden die Kameraposen als Frames in die Zeitleiste eingefügt.\n\tDie Zeitleiste ggf. ganz unten links durch Klick auf 'ZEITLEISTE' aufklappen.\n\n"
        + "5. Gesamtzahl der Frames unten rechts erhöhen auf: "
        + str(len(camera_poses))
        + "\n\n"
        + "\tEine Preview kann durch klick auf den Play-Button in der Zeitleiste gestartet werden.\n\n"
        + "6. Video rendern über 'Rendern' -> 'Video...'. Auflösung optional auf 1280x720 stellen (schnelleres Rendern), Rest beibehalten.\n\n"
        + "7. Das Video in den erzeugten Video-Ordner exportieren:\n\n\t"
        + os.path.abspath(video_folder)
        + "\n\n\n"
        + "Warte bis das Rendering abgeschlossen ist und klappe anschließend Schritt 2 zu und fahre mit Schritt 3A fort"
    )
    set_tab_done("step2_tab_2c", "2C: SuperSplat Export")


def set_step3a_status(text):
    dpg.set_value("3a_output_text", text)
    dpg.render_dearpygui_frame()


def select_step3a_splat_output_folder():
    global step3_odom_data_path

    root = Tk()
    root.withdraw()

    initial_dir = "splats"
    if not os.path.isdir(initial_dir):
        initial_dir = "."

    selected_folder = filedialog.askdirectory(
        title="Splat-Ordner auswählen",
        initialdir=initial_dir,
    )
    root.destroy()

    if not selected_folder:
        return

    selected_folder = os.path.normpath(selected_folder)
    dpg.set_value("3a_splat_output_folder_input", selected_folder)

    odom_data_path = os.path.join(selected_folder, STEP3_OUTPUT_FOLDER_NAME)
    image_output_dir = os.path.join(odom_data_path, STEP3_IMAGES_FOLDER_NAME)
    poses_output_file = os.path.join(odom_data_path, STEP3_POSES_FILE_NAME)
    image_count = 0

    if os.path.isdir(odom_data_path):
        step3_odom_data_path = odom_data_path
    else:
        step3_odom_data_path = None

    if os.path.isdir(image_output_dir):
        for file_name in os.listdir(image_output_dir):
            if file_name.lower().endswith(".png"):
                image_count += 1

    if os.path.isfile(poses_output_file) and image_count > 0:
        set_step3a_status(
            "Vorhandene Daten gefunden.\n\n"
            + "Bilder:\n"
            + image_output_dir
            + "\n\n"
            + "Posen:\n"
            + poses_output_file
            + "\n\n"
            + "Bilder gefunden: "
            + str(image_count)
        )
        set_tab_done("step3_tab_3a", "3A: Daten vorbereiten")
    else:
        set_step3a_status("Splat-Ordner gesetzt.\n\nNoch keine vorbereiteten Daten gefunden.")

    if os.path.isfile(os.path.join(selected_folder, STEP3_ODOM_OUTPUT_FOLDER_NAME, "vo_output.csv")):
        set_tab_done("step3_tab_3b", "3B: Odometrie ausführen")

    update_step3_evaluation_statuses()


def prepare_visual_odometry_data():
    global step3_odom_data_path

    selected_folder = dpg.get_value("3a_splat_output_folder_input").strip()

    if selected_folder == "" and step2_splat_output_dir is not None:
        selected_folder = step2_splat_output_dir
        dpg.set_value("3a_splat_output_folder_input", selected_folder)

    if selected_folder == "":
        set_step3a_status("Erst einen Splat-Ordner auswählen")
        return

    selected_folder = os.path.normpath(selected_folder)
    dpg.set_value("3a_splat_output_folder_input", selected_folder)

    odom_data_path = os.path.join(selected_folder, STEP3_OUTPUT_FOLDER_NAME)
    image_output_dir = os.path.join(odom_data_path, STEP3_IMAGES_FOLDER_NAME)
    poses_output_file = os.path.join(odom_data_path, STEP3_POSES_FILE_NAME)

    set_step3a_status("Daten werden vorbereitet...\nBilder werden vereinzelt...\nDas kann eine Weile dauern, bitte warten...")

    try:
        result = visual_odometry_prepare.prepare_visual_odometry_data(
            selected_folder,
            image_output_dir,
            poses_output_file,
        )
    except ValueError as error:
        set_step3a_status(str(error))
        return

    video_file, num_images, num_poses = result
    step3_odom_data_path = odom_data_path

    warning_text = ""
    if num_images != num_poses:
        warning_text = "Warnung: Anzahl Bilder und Posen unterscheiden sich.\n\n"

    set_step3a_status(
        "Daten vorbereitet.\n\n"
        + warning_text
        + "Verwendetes Video:\n"
        + video_file
        + "\n\n"
        + "Extrahierte Bilder:\n"
        + image_output_dir
        + "\n\n"
        + "Exportierte Kameraposen:\n"
        + poses_output_file
        + "\n\n"
        + "Bilder extrahiert: "
        + str(num_images)
        + "\n"
        + "Kameraposen geladen: "
        + str(num_poses)
        + "\n\nFahre mit Schritt 3B fort"
    )
    set_tab_done("step3_tab_3a", "3A: Daten vorbereiten")
    update_step3_evaluation_statuses()


def run_visual_odometry():
    global step3_odom_data_path

    odom_data_path = step3_odom_data_path

    if odom_data_path is None:
        selected_folder = dpg.get_value("3a_splat_output_folder_input").strip()

        if selected_folder != "":
            odom_data_path = os.path.join(os.path.normpath(selected_folder), STEP3_OUTPUT_FOLDER_NAME)

    if odom_data_path is None or not os.path.isdir(odom_data_path):
        dpg.set_value("3b_status_text", "Erst einen Splat-Ordner unter 3A auswählen (und Daten vorbereiten)")
        return

    image_output_dir = os.path.abspath(os.path.join(odom_data_path, STEP3_IMAGES_FOLDER_NAME))
    poses_output_file = os.path.abspath(os.path.join(odom_data_path, STEP3_POSES_FILE_NAME))

    if not os.path.isdir(image_output_dir):
        dpg.set_value("3b_status_text", "Bilderordner nicht gefunden")
        return

    if not os.path.isfile(poses_output_file):
        dpg.set_value("3b_status_text", "poses.txt nicht gefunden")
        return

    step3_odom_data_path = odom_data_path
    script_folder = os.path.abspath(os.path.join("extern", "Monocular-Video-Odometery"))
    script_file = os.path.join(script_folder, "run_odom.py")

    if not os.path.isdir(script_folder):
        set_tab_open("step3_tab_3b", "3B: Odometrie ausführen")
        dpg.set_value(
            "3b_status_text",
            "Fehler: Ordner der Visual-Odometry-Implementierung nicht gefunden:\n" + script_folder,
        )
        return

    if not os.path.isfile(script_file):
        set_tab_open("step3_tab_3b", "3B: Odometrie ausführen")
        dpg.set_value(
            "3b_status_text",
            "Fehler: Python-Datei zum Ausführen der Visual Odometry nicht gefunden:\n" + script_file,
        )
        return

    output_folder = os.path.abspath(os.path.join(os.path.dirname(odom_data_path), STEP3_ODOM_OUTPUT_FOLDER_NAME))
    os.makedirs(output_folder, exist_ok=True)
    output_file = os.path.join(output_folder, "vo_output.csv")
    old_output_time = os.path.getmtime(output_file) if os.path.isfile(output_file) else None

    # start VO script
    process = subprocess.Popen([
        sys.executable,
        script_file,
        "--img_path",
        image_output_dir + os.sep,
        "--pose_path",
        poses_output_file,
        "--csv_path",
        output_file,
    ], cwd=script_folder)

    dpg.set_value("3b_status_text", "Odometrie gestartet")

    def wait_for_odometry():
        return_code = process.wait()
        output_was_updated = (
            os.path.isfile(output_file)
            and (old_output_time is None or os.path.getmtime(output_file) > old_output_time)
        )

        if return_code == 0 and output_was_updated:
            dpg.set_value("3b_status_text", "Odometry Daten gespeichert unter:\n" + output_file + "\n\nFahre mit Schritt 3C fort")
            set_tab_done("step3_tab_3b", "3B: Odometrie ausführen")
        elif return_code != 0:
            set_tab_open("step3_tab_3b", "3B: Odometrie ausführen")
            dpg.set_value(
                "3b_status_text",
                "Odometrie konnte nicht ausgeführt werden.\n"
                + "vo_output.csv wurde nicht neu gespeichert.\n\n"
                + "Fehlercode: "
                + str(return_code),
            )
        else:
            set_tab_open("step3_tab_3b", "3B: Odometrie ausführen")
            dpg.set_value("3b_status_text", "Odometrie beendet, aber vo_output.csv wurde nicht gefunden")

    threading.Thread(target=wait_for_odometry, daemon=True).start()


def set_step3c_status(text):
    if dpg.does_item_exist("3c_status_text"):
        dpg.set_value("3c_status_text", text)
        dpg.render_dearpygui_frame()


def set_step3d_status(text):
    if dpg.does_item_exist("3d_status_text"):
        dpg.set_value("3d_status_text", text)
        dpg.render_dearpygui_frame()


def get_central_evaluation_folder():
    return os.path.join(REPO_ROOT, "evaluation")


def open_central_evaluation_folder():
    evaluation_folder = get_central_evaluation_folder()
    os.makedirs(evaluation_folder, exist_ok=True)

    try:
        os.startfile(evaluation_folder)
    except OSError as error:
        set_step3d_status("Evaluations-Ordner konnte nicht geöffnet werden:\n" + str(error))


def get_step3_selected_splat_folder():
    selected_folder = ""

    if dpg.does_item_exist("3a_splat_output_folder_input"):
        selected_folder = dpg.get_value("3a_splat_output_folder_input").strip()

    if selected_folder == "" and step3_odom_data_path is not None:
        selected_folder = os.path.dirname(step3_odom_data_path)

    if selected_folder == "" and step2_splat_output_dir is not None:
        selected_folder = step2_splat_output_dir

    if selected_folder == "":
        return ""

    return os.path.normpath(selected_folder)


def get_evaluation_trajectory_names():
    evaluation_folder = get_central_evaluation_folder()

    if not os.path.isdir(evaluation_folder):
        return []

    names = []
    for name in os.listdir(evaluation_folder):
        folder_path = os.path.join(evaluation_folder, name)
        if os.path.isdir(folder_path):
            names.append(name)

    return sorted(names)


def get_short_evaluation_folder(selected_folder):
    return os.path.join(selected_folder, SHORT_EVALUATION_FOLDER_NAME)


def update_evaluation_trajectory_list():
    names = get_evaluation_trajectory_names()

    if len(names) == 0:
        list_text = "Keine Trajektorien im zentralen evaluation-Ordner gefunden."
    else:
        list_text = "\n".join(names)

    if dpg.does_item_exist("3d_evaluation_trajectory_list"):
        dpg.set_value("3d_evaluation_trajectory_list", list_text)


def update_evaluation_folder_name_input():
    selected_folder = get_step3_selected_splat_folder()

    if selected_folder == "" or not dpg.does_item_exist("3d_trajectory_name_input"):
        return

    splat_data_file = os.path.join(selected_folder, SPLAT_DATA_FILE_NAME)
    splat_data = final_transform.load_yaml_file(splat_data_file)
    evaluation_data = splat_data.get("evaluation", {}) or {}
    evaluation_folder_name = evaluation_data.get("evaluation_folder_name")

    if evaluation_folder_name is None:
        dpg.set_value("3d_trajectory_name_input", "")
    else:
        dpg.set_value("3d_trajectory_name_input", evaluation_folder_name)


def get_short_evaluation_path(selected_folder):
    return os.path.join(get_short_evaluation_folder(selected_folder), SHORT_EVALUATION_IMAGE_NAME)


def get_top_down_evaluation_path(selected_folder):
    return os.path.join(get_short_evaluation_folder(selected_folder), TOP_DOWN_EVALUATION_IMAGE_NAME)


def update_step3c_ok_status():
    selected_folder = get_step3_selected_splat_folder()

    if (
        selected_folder != ""
        and os.path.isfile(get_short_evaluation_path(selected_folder))
        and os.path.isfile(get_top_down_evaluation_path(selected_folder))
    ):
        set_tab_done("step3_tab_3c", "3C: Kompakt-Evaluation")
    else:
        set_tab_open("step3_tab_3c", "3C: Kompakt-Evaluation")


def update_step3d_ok_status():
    selected_folder = get_step3_selected_splat_folder()

    if selected_folder == "":
        set_tab_open("step3_tab_3d", "3D: Ausführliche Evaluation")
        return

    splat_data_file = os.path.join(selected_folder, SPLAT_DATA_FILE_NAME)
    splat_data = final_transform.load_yaml_file(splat_data_file)
    evaluation_data = splat_data.get("evaluation", {})
    evaluation_folder_name = evaluation_data.get("evaluation_folder_name")

    if evaluation_folder_name is None:
        set_tab_open("step3_tab_3d", "3D: Ausführliche Evaluation")
        return

    evaluation_folder = os.path.join(get_central_evaluation_folder(), evaluation_folder_name)

    if os.path.isdir(evaluation_folder):
        set_tab_done("step3_tab_3d", "3D: Ausführliche Evaluation")
    else:
        set_tab_open("step3_tab_3d", "3D: Ausführliche Evaluation")


def update_step3_evaluation_statuses():
    update_evaluation_trajectory_list()
    update_evaluation_folder_name_input()
    update_step3c_ok_status()
    update_step3d_ok_status()


def show_evaluation_plot():
    selected_folder = get_step3_selected_splat_folder()

    if selected_folder == "":
        set_step3c_status("Erst einen Splat-Ordner unter 3A auswählen")
        return

    csv_file = os.path.join(
        selected_folder,
        STEP3_ODOM_OUTPUT_FOLDER_NAME,
        "vo_output.csv",
    )
    grid_file = os.path.join(selected_folder, "top_down_grid.npz")

    if not os.path.isfile(csv_file):
        set_step3c_status("vo_output.csv nicht gefunden")
        return

    evaluation_png_path = get_short_evaluation_path(selected_folder)
    top_down_png_path = get_top_down_evaluation_path(selected_folder)
    set_step3c_status(
        "Evaluation wird erzeugt aus:\n"
        + csv_file
        + "\n\nKompakt-Evaluation gespeichert unter:\n"
        + evaluation_png_path
        + "\n\nTop-Down-Vergleich gespeichert unter:\n"
        + top_down_png_path
    )

    try:
        odometry_evaluation.plot_odometry_csv(csv_file, grid_file)
    except ValueError as error:
        set_step3c_status(str(error))
        return

    set_step3c_status(
        "Evaluation generiert aus:\n"
        + csv_file
        + "\n\nKompakt-Evaluation gespeichert unter:\n"
        + evaluation_png_path
        + "\n\nTop-Down-Vergleich gespeichert unter:\n"
        + top_down_png_path
    )
    set_tab_done("step3_tab_3c", "3C: Kompakt-Evaluation")
    odometry_evaluation.show_evaluation_window()


def is_valid_evaluation_folder_name(folder_name):
    invalid_characters = '\\/:*?"<>|'

    if folder_name == "":
        return False

    if folder_name in [".", ".."]:
        return False

    if any(character.isspace() for character in folder_name):
        return False

    for character in invalid_characters:
        if character in folder_name:
            return False

    return True


def format_evaluation_metadata_key(key):
    key_names = {
        "splat_count": "SplatCount",
        "waypoint_count": "WaypointCount",
        "camera_pose_count": "CameraPoseCount",
        "camera_height": "CameraHeight",
        "pose_distance": "PoseDistance",
        "look_ahead_steps": "LookAheadSteps",
        "smoothing_passes": "SmoothingPasses",
    }

    if key in key_names:
        return key_names[key]

    return key


def write_evaluation_metadata_csv(selected_folder, target_folder):
    splat_data_file = os.path.join(selected_folder, SPLAT_DATA_FILE_NAME)
    splat_data = final_transform.load_yaml_file(splat_data_file)

    files = splat_data.get("files", {}) or {}
    metadata = splat_data.get("metadata", {}) or {}
    trajectory_generation = splat_data.get("trajectory_generation", {}) or {}
    camera_pose_generation = splat_data.get("camera_pose_generation", {}) or {}
    project_folder = files.get("project_folder", "")
    project_folder_name = ""
    if project_folder != "":
        project_folder_name = os.path.basename(os.path.normpath(project_folder))

    rows = [
        ["OriginalSplatFileName", files.get("splat_file", "")],
        ["GeneratedSplatFolderName", project_folder_name],
        ["SplatCount", metadata.get("splat_count", "")],
        ["WaypointCount", trajectory_generation.get("waypoint_count", "")],
        ["CameraPoseCount", camera_pose_generation.get("camera_pose_count", "")],
    ]

    for key in sorted(camera_pose_generation.keys()):
        if key == "camera_pose_count":
            continue
        rows.append([format_evaluation_metadata_key(key), camera_pose_generation.get(key, "")])

    metadata_file = os.path.join(target_folder, EVALUATION_METADATA_FILE_NAME)
    with open(metadata_file, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Key", "Value"])
        writer.writerows(rows)


def save_evaluation_data_for_later_analysis():
    trajectory_name = dpg.get_value("3d_trajectory_name_input").strip()

    if trajectory_name == "":
        set_step3d_status("Bitte einen Trajektoriennamen eingeben.")
        return

    if not is_valid_evaluation_folder_name(trajectory_name):
        set_step3d_status(
            'Ungültige Zeichen im Ordnernamen. Bitte keine Leerzeichen verwenden, stattdessen Unterstriche. '
            'Vermeide Sonderzeichen wie \\ / : * ? " < > |.'
        )
        return

    selected_folder = get_step3_selected_splat_folder()
    if selected_folder == "":
        set_step3d_status("Erst einen Splat-Ordner unter 3A auswählen")
        return

    source_csv = os.path.join(selected_folder, STEP3_ODOM_OUTPUT_FOLDER_NAME, "vo_output.csv")
    source_image = get_top_down_evaluation_path(selected_folder)

    if not os.path.isfile(source_csv):
        set_step3d_status("vo_output.csv nicht gefunden. Erst Schritt 3B ausführen.")
        return

    if not os.path.isfile(source_image):
        set_step3d_status("vo_top_down_eval.png nicht gefunden. Erst die Kompakt-Evaluation generieren und anzeigen.")
        return

    evaluation_folder = get_central_evaluation_folder()
    target_folder = os.path.join(evaluation_folder, trajectory_name)

    if os.path.exists(target_folder):
        set_step3d_status(
            "Ein Ordner mit demselben Namen ist bereits vorhanden. Bitte umbenennen oder den vorhandenen Ordner manuell löschen."
            + "\n"
            + target_folder
        )
        return

    try:
        os.makedirs(target_folder)
        shutil.copy2(source_csv, os.path.join(target_folder, "vo_output.csv"))
        shutil.copy2(source_image, os.path.join(target_folder, TOP_DOWN_EVALUATION_IMAGE_NAME))
        write_evaluation_metadata_csv(selected_folder, target_folder)
        final_transform.update_splat_data_yaml(
            os.path.join(selected_folder, SPLAT_DATA_FILE_NAME),
            "evaluation",
            {"evaluation_folder_name": trajectory_name},
        )
    except OSError as error:
        set_step3d_status("Speichern fehlgeschlagen:\n" + str(error))
        return

    update_evaluation_trajectory_list()
    set_step3d_status(
        "Speichern im Evaluationsordner erfolgreich."
        + "\n"
        + target_folder
        + "\n\nZusätzliche Metadaten gespeichert in: "
        + EVALUATION_METADATA_FILE_NAME
        + "\n\nDetail- bzw. Vergleichsevaluation kann gestartet werden."
    )
    set_tab_done("step3_tab_3d", "3D: Ausführliche Evaluation")


def show_detail_comparison_confirmation():
    update_evaluation_trajectory_list()
    names = get_evaluation_trajectory_names()

    if len(names) == 0:
        set_step3d_status("Keine Trajektorienordner im zentralen evaluation-Ordner gefunden.")
        return

    dpg.set_value("3d_detail_eval_confirm_list", "\n".join(names))
    dpg.show_item("3d_detail_eval_confirm_window")


def get_rscript_path():
    rscript_path = shutil.which("Rscript")

    if rscript_path is not None:
        return rscript_path

    possible_paths = [
        Path(sys.prefix) / "Scripts" / "Rscript.exe",
        Path(sys.prefix) / "Library" / "bin" / "Rscript.exe",
        Path(sys.prefix) / "bin" / "Rscript",
        Path(sys.prefix) / "bin" / "Rscript.exe",
    ]

    for possible_path in possible_paths:
        if possible_path.is_file():
            return str(possible_path)

    return None


def run_detail_evaluation_pdf():
    dpg.hide_item("3d_detail_eval_confirm_window")

    repo_root = Path(__file__).resolve().parent.parent
    evaluation_folder = repo_root / "evaluation"
    pdf_file = evaluation_folder / "Benchmarking_Gaussian_Splatting.pdf"
    script_file = repo_root / "render_evaluation_pdf.R"
    rscript_path = get_rscript_path()
    old_pdf_time = None

    if pdf_file.is_file():
        old_pdf_time = pdf_file.stat().st_mtime

    if rscript_path is None:
        set_step3d_status(
            "Rscript wurde nicht gefunden.\n\n"
            + "Bitte die Pipeline aus dem Conda-Environment starten, das r-base enthält:\n"
            + "conda activate splat-loc-sim-env\n"
            + "python start_pipeline.py"
        )
        return

    command = [rscript_path, str(script_file)]
    status_text = (
        "PDF-Evaluation wird generiert.\n"
        + "Bitte warten, das kann etwas dauern...\n\n"
        + "Ausgabe:\n"
    )
    set_step3d_status(status_text)

    try:
        process = subprocess.Popen(
            command,
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        for line in process.stdout:
            status_text += line
            set_step3d_status(status_text)

        return_code = process.wait()
    except FileNotFoundError as error:
        set_step3d_status("Rscript wurde nicht gefunden.\n" + str(error))
        return

    if return_code != 0:
        if pdf_file.is_file() and (old_pdf_time is None or pdf_file.stat().st_mtime > old_pdf_time):
            set_step3d_status(
                status_text
                + "\nPDF-Evaluation wurde generiert."
                + "\n"
                + str(pdf_file)
                + "\n\nHinweis: R hat trotzdem einen Fehlercode gemeldet. Wenn die PDF normal geöffnet werden kann, kann diese Meldung ignoriert werden."
            )
            return

        set_step3d_status(
            status_text
            + "\n"
            "PDF-Evaluation konnte nicht generiert werden.\n"
            + "Bitte mögliche Probleme mit der LaTeX-Engine / tectonic prüfen.\n\n"
            + "Fehlercode: "
            + str(return_code)
        )
        return

    set_step3d_status(
        status_text
        + "\nPDF-Evaluation wurde generiert."
        + "\n"
        + str(pdf_file)
    )


def run_plane_search():
    global step1_point_cloud
    global step1_plane_candidates
    global step1_floor_view_cache
    global step1_validated_floor_data
    global step1_alignment_data
    global step1_final_transform_data

    dpg.set_value("1a_output_text", "")
    dpg.set_value("1b_output_text", "")
    step1_validated_floor_data = None
    step1_alignment_data = None
    step1_final_transform_data = None
    reset_floor_alignment_state()

    splat_file = dpg.get_value("splat_file_input")

    def show_status(new_text):
        # show progress for step 1A in the small text box
        old_text = dpg.get_value("1a_output_text")
        dpg.set_value("1a_output_text", old_text + new_text)
        dpg.render_dearpygui_frame()

    # run step 1A and show status messages in the GUI
    step1_result = step1.run_step_1a(splat_file, show_status)

    if step1_result is None:
        return

    step1_point_cloud, step1_plane_candidates = step1_result[1], step1_result[2]
    step1_floor_view_cache = {}
    step1_validated_floor_data = None
    step1_alignment_data = None
    step1_final_transform_data = None

    candidate_names = ["Kandidat " + str(i + 1) for i in range(len(step1_plane_candidates))]

    dpg.configure_item("floor_candidate_combo", items=candidate_names)

    # step 1A finished -> mark tab as done before drawing the 1B preview
    set_tab_done("step1_tab_1a", "1A: Ebenen finden")

    if len(candidate_names) > 0:
        dpg.set_value("floor_candidate_combo", candidate_names[0])
        draw_floor_candidate()


def validate_floor_plane():
    """confirm selection and generate outputs"""
    global step1_validated_floor_data

    dpg.set_value("1b_output_text", "")

    def show_status(new_text):
        # callback for outputting 1B status messages
        old_text = dpg.get_value("1b_output_text")
        dpg.set_value("1b_output_text", old_text + new_text)
        dpg.render_dearpygui_frame()

    selected_candidate = dpg.get_value("floor_candidate_combo")

    if selected_candidate == "":
        show_status("Erst Ebenenkandidaten in 1A suchen\n")
        return

    candidate_number = int(selected_candidate.replace("Kandidat ", ""))
    view_data = get_floor_candidate_view_data()

    if view_data is None:
        show_status("Kandidat konnte nicht vorbereitet werden\n")
        return

    height_a = dpg.get_value("floor_min_height_slider")
    height_b = dpg.get_value("floor_max_height_slider")
    min_height = min(height_a, height_b)
    max_height = max(height_a, height_b)

    step1_validated_floor_data = {
        "candidate_number": candidate_number,
        "view_data": view_data,
        "height_filter": {
            "min_height": min_height,
            "max_height": max_height,
        },
    }
    reset_floor_alignment_state()

    show_status("Bodenebene und Höhenbereich ausgewählt\n")
    show_status("\tKandidat: " + str(candidate_number) + "\n")
    show_status("\tHöhenbereich: " + format(min_height, ".2f") + " bis " + format(max_height, ".2f") + "\n")
    show_status("\tOberseite wurde automatisch bestimmt\n")
    show_status("\tPunkte oberhalb: " + format(view_data["orientation_info"]["positive_ratio"] * 100, ".1f") + " %\n\n")
    show_status("Fahre mit Schritt 1C fort")

    set_tab_done("step1_tab_1b", "1B: Boden wählen")


def build_step1_area():
    
    # main steps are vertical collapsing headers
    with dpg.collapsing_header(label="Schritt 1: Bodenebene bestimmen und Koordinatentransformation erzeugen", default_open=False):     
        
        with dpg.tab_bar(tag="step1_tab_bar"):
        # substeps are tabs inside the main step

            # section 1A
            with dpg.tab(label=STEP_OPEN + " 1A: Ebenen finden", tag="step1_tab_1a"):

                dpg.add_text("Splatdatei auswählen und Boden-Ebenenkandidaten suchen", color=HEADING_COLOR)
                dpg.add_text("Output: Ebenenkandidaten mit Ebenenmodell und Inlier-Punkten für 1B", color=OUTPUT_COLOR)
                dpg.add_text(
                    "Wähle eine 3D Gaussian-Splatdatei vom Format '.ply' aus und starte die Suche nach ebenen Flächen, die als Bodenebene in Frage kommen.",
                    color=INSTRUCTION_COLOR,
                )

                with dpg.group(horizontal=True):
                    dpg.add_input_text(tag="splat_file_input", default_value=step1.SPLAT_FILE, width=650)
                    dpg.add_button(label="Durchsuchen", callback=show_file_dialog)

                dpg.add_button(label="Ebenenkandidaten suchen", callback=run_plane_search)
                dpg.add_separator()
                dpg.add_input_text(tag="1a_output_text", default_value="", multiline=True, readonly=True, width=970, height=300)

            # section 1B
            with dpg.tab(label=STEP_OPEN + " 1B: Boden wählen", tag="step1_tab_1b"):
                dpg.add_text("Ebenenkandidaten anzeigen und Bodenebene validieren", color=HEADING_COLOR)
                dpg.add_text("Output: validierte Bodenebene, Oberseitenrichtung und Höhenfilter für 1C", color=OUTPUT_COLOR)
                dpg.add_text("Wähle den passendsten Kandidaten, der die tatsätzliche Bodenebene darstellt, aus.\nDie Anpassung des Höhenfilters kann bei der Identifizierung hilfreich sein.", color=INSTRUCTION_COLOR,)
                
                dpg.add_combo(label="Kandidat", tag="floor_candidate_combo", items=[], width=200, callback=draw_floor_candidate)
                dpg.add_text("", tag="floor_orientation_status")

                dpg.add_text("Stelle den Höhenfilter so ein, dass die Raumstruktur und Hindernisse in der Draufsicht möglichst klar erkennbar sind,\ndarüber wird später eine Occupancy Map erstellt.", color=INSTRUCTION_COLOR,)
                dpg.add_slider_float(label="Höhenfilter: Untergrenze über Bodenebene", tag="floor_min_height_slider", default_value=0.2, min_value=0.2, max_value=3.0, width=420, callback=draw_floor_candidate)
                dpg.add_slider_float(label="Höhenfilter: Obergrenze über Bodenebene", tag="floor_max_height_slider", default_value=1.0, min_value=0.0, max_value=3.0, width=420, callback=draw_floor_candidate)
                dpg.add_text("Sichtbarer Höhenbereich: 0.00 bis 3.00 über der Bodenebene", tag="floor_height_status")

                dpg.add_drawlist(width=700, height=420, tag="floor_candidate_preview")

                dpg.add_button(label="Bodenebene und Occupancy Map validieren", callback=validate_floor_plane)
                dpg.add_separator()
                dpg.add_input_text(tag="1b_output_text", default_value="", multiline=True, readonly=True, width=970, height=150)

            # section 1C
            with dpg.tab(label=STEP_OPEN + " 1C: Ausrichten", tag="step1_tab_1c"):
                dpg.add_text("Raumrotation und XY-Ursprung manuell anpassen", color=HEADING_COLOR)
                dpg.add_text("Output: manuelle Raumrotation und XY-Ursprung für die Gesamttransformation in 1D", color=OUTPUT_COLOR)
                dpg.add_text("Richte die validierte Draufsicht durch Rotation, an den X/Y-Achsen aus\nund lege den Ursprung durch Translation grob in die linke untere Raumecke.", color=INSTRUCTION_COLOR)
                dpg.add_text("Erst Bodenebene in 1B validieren", tag="1c_alignment_status")

                dpg.add_slider_float(label="Rotation um Z", tag="alignment_yaw_slider", default_value=0.0, min_value=-180.0, max_value=180.0, width=420, callback=draw_floor_alignment)
                dpg.add_slider_float(label="Ursprung X", tag="alignment_origin_x_slider", default_value=0.0, min_value=-10.0, max_value=10.0, width=420, callback=draw_floor_alignment)
                dpg.add_slider_float(label="Ursprung Y", tag="alignment_origin_y_slider", default_value=0.0, min_value=-10.0, max_value=10.0, width=420, callback=draw_floor_alignment)

                dpg.add_drawlist(width=700, height=420, tag="floor_alignment_preview")

                dpg.add_button(label="Ausrichtung übernehmen", callback=accept_floor_alignment)
                dpg.add_separator()
                dpg.add_input_text(tag="1c_output_text", default_value="", multiline=True, readonly=True, width=970, height=120)

            # section 1D
            with dpg.tab(label=STEP_OPEN + " 1D: Transformation", tag="step1_tab_1d"):
                dpg.add_text("Transformation zwischen Simulations- und Splat-Koordinatensystem berechnen und speichern", color=HEADING_COLOR)
                dpg.add_text("Output:", color=OUTPUT_COLOR)
                dpg.add_text("\t- Transformationen und Metadaten: splat_data.yaml", color=OUTPUT_COLOR)
                dpg.add_text("\t- Occupancy Grid: top_down_grid.npz", color=OUTPUT_COLOR)
                dpg.add_text("Lass die Transformationen berechnen und überprüfe das generierte Occupancy Grid.", color=INSTRUCTION_COLOR)
                dpg.add_button(label="Transformation und Grid generieren", callback=calculate_final_transform)
                dpg.add_button(label="Occupancy Grid anzeigen", callback=show_saved_top_down_grid)
                dpg.add_separator()
                dpg.add_input_text(tag="1d_output_text", default_value="", multiline=True, readonly=True, width=970, height=560)


def build_step2_area():

    with dpg.collapsing_header(label="Schritt 2: Trajektorie festlegen und Bilddaten generieren"):
        with dpg.tab_bar(tag="step2_tab_bar"):

            # section 2A
            with dpg.tab(label=STEP_OPEN + " 2A: Trajektorie", tag="step2_tab_2a"):
                dpg.add_text("Trajektorie festlegen", color=HEADING_COLOR)
                dpg.add_text("Output:", color=OUTPUT_COLOR)
                dpg.add_text("\t- Manuell gesetzte Wegpunkte: trajectory.csv", color=OUTPUT_COLOR)
                dpg.add_text("\t- Anzahl der Wegpunkte ergänzt in: splat_data.yaml", color=OUTPUT_COLOR)

                dpg.add_text("Wähle (falls nicht bereits hinterlegt) den generierten Ordner aus `splats/<Splat-Datei-Name>`, der zu deiner Splat-Datei gehört.\n", color=INSTRUCTION_COLOR)
                dpg.add_text("Daraus werden Occupancy Grid und Transformation aus Schritt 1 geladen und weitere Daten abgelegt.")

                with dpg.group(horizontal=True):
                    dpg.add_input_text(tag="splat_output_folder_input", width=650)
                    dpg.add_button(label="Ordner auswählen", callback=select_splat_output_folder)

                dpg.add_text("Hinweise:")
                dpg.add_text("\t - Die Trajektorie besteht aus geraden Linien zwischen den Wegpunkten.")
                dpg.add_text("\t - Für Kurven bitte mehrere Punkte eng hintereinander setzen. Kurvenglättungen werden nur in kleinem Umfang erzeugt.")
                dpg.add_text("\t - Zu enge Kurven können bei nicht ausreichender Framezahl zu Problemen bei der Visuellen Odometrie führen.")
                dpg.add_text("\t - Im Zeichenfenster setzt W einen Wegpunkt")
                dpg.add_text("\t - Mit E wird der zuletzt gesetzte Wegpunkt entfernt")
                dpg.add_text("\t - Mit Enter wird gespeichert, beim Schließen wird verworfen.")

                dpg.add_button(label="Trajektorie einzeichnen", callback=start_trajectory_drawing)
                dpg.add_separator()
                dpg.add_input_text(tag="2a_output_text", default_value="", multiline=True, readonly=True, width=970, height=100)

            # section 2B
            with dpg.tab(label=STEP_OPEN + " 2B: Kameraposen", tag="step2_tab_2b"):
                dpg.add_text("Kameraposen generieren", color=HEADING_COLOR)
                dpg.add_text("Output:\n", color=OUTPUT_COLOR)
                dpg.add_text("\t- Kameraposen im Simulations-Koordinatensystem: camera_poses_sim.csv", color=OUTPUT_COLOR)
                dpg.add_text("\t- Posenanzahl und Parameter ergänzt in: splat_data.yaml", color=OUTPUT_COLOR)
                dpg.add_text("Speichert Kameraposen und Parameter der Posengenerierung.", color=INSTRUCTION_COLOR)
                dpg.add_text("Kamerahöhe über Boden")
                dpg.add_input_float(tag="camera_height_input", default_value=0.4, width=160)
                dpg.add_text("Posen-Abstand - Abstand der Kameraposen entlang der Trajektorie (je kleiner, desto mehr Posen)")
                dpg.add_input_float(tag="pose_spacing_input", default_value=camera_pose_generator.POSE_SPACING, width=160)
                dpg.add_text("Lookahead-Schritte - Anzahl der Schritte, die für die Berechnung der Blickrichtung vorausgeschaut wird (min. 1)")
                dpg.add_input_int(tag="lookahead_steps_input", default_value=camera_pose_generator.LOOKAHEAD_STEPS, width=160)
                dpg.add_text("Glättungs-Durchläufe - Anzahl der Durchläufe, die harte Ecken in der Trajektorie glätten (0 = keine Glättung)")
                dpg.add_input_int(tag="smoothing_rounds_input", default_value=camera_pose_generator.SMOOTHING_ROUNDS, width=160)
                dpg.add_button(label="Kameraposen generieren", callback=generate_camera_poses)
                dpg.add_separator()
                dpg.add_input_text(tag="2b_output_text", default_value="", multiline=True, readonly=True, width=970, height=160)

            # section 2C
            with dpg.tab(label=STEP_OPEN + " 2C: SuperSplat Export", tag="step2_tab_2c"):
                dpg.add_text("Datei generieren um Kameraposen in SuperSplat Editor zu importieren und Video zu rendern", color=HEADING_COLOR)
                dpg.add_text("Output:", color=OUTPUT_COLOR)
                dpg.add_text("\t- Kameraposen im COLMAP-Format: supersplat_camera_poses\\images.txt", color=OUTPUT_COLOR)
                dpg.add_text("\t- Danach manuell über Rendering in SuperSplat: Videodatei im Ablage-Ordner 'supersplat_video'", color=OUTPUT_COLOR)
                dpg.add_text("Generiere die images.txt Datei und folge den Anweisungen, um die Kameraposen in SuperSplat zu importieren und ein Video zu rendern.", color=INSTRUCTION_COLOR)

                dpg.add_button(label="images.txt erzeugen", callback=export_supersplat_images_txt)
                dpg.add_separator()
                dpg.add_input_text(tag="2c_output_text", default_value="", multiline=True, readonly=True, width=970, height=560)


def build_step3_area():
    
    with dpg.collapsing_header(label="Schritt 3: Visuelle Lokalisierung und Evaluation"):
        with dpg.tab_bar(tag="step3_tab_bar", callback=update_step3_evaluation_statuses):
            
            # section 3A
            with dpg.tab(label=STEP_OPEN + " 3A: Daten vorbereiten", tag="step3_tab_3a"):
                dpg.add_text("Daten für visuelle Odometrie vorbereiten", color=HEADING_COLOR)
                dpg.add_text("Output:", color=OUTPUT_COLOR)
                dpg.add_text("\t- Einzelbilder: odometry_input\\images\\*.png", color=OUTPUT_COLOR)
                dpg.add_text("\t- Posen für Odometrie im KITTI-Odometry-Format: odometry_input\\poses.txt", color=OUTPUT_COLOR)
                dpg.add_text("Wähle (falls nicht bereits hinterlegt) den Ordner aus `splats/<Splat-Datei-Name>`, der zu deiner Splat-Datei gehört.\n", color=INSTRUCTION_COLOR)
                dpg.add_text("Daraus werden gerendertes Video und Kameraposen aus Schritt 2 geladen und weitere Daten abgelegt.")
                default_splat_folder = ""
                if step2_splat_output_dir is not None:
                    default_splat_folder = step2_splat_output_dir

                with dpg.group(horizontal=True):
                    dpg.add_input_text(tag="3a_splat_output_folder_input", default_value=default_splat_folder, width=650)
                    dpg.add_button(label="Ordner auswählen", callback=select_step3a_splat_output_folder)

                dpg.add_text("Starte die Daten vorbereitung, um die Bilder zu vereinzeln und die Kameraposen in das benötigte Format zu bringen.", color=INSTRUCTION_COLOR)
                dpg.add_button(label="Daten vorbereiten", callback=prepare_visual_odometry_data)
                dpg.add_input_text(tag="3a_output_text", default_value="", multiline=True, readonly=True, width=970, height=220)

            # section 3B
            with dpg.tab(label=STEP_OPEN + " 3B: Odometrie ausführen", tag="step3_tab_3b"):
                dpg.add_text("Odometrie ausführen", color=HEADING_COLOR)
                dpg.add_text("Output: Ausgabedaten der Visual Odometry: odometry_output\\vo_output.csv", color=OUTPUT_COLOR)
                dpg.add_text("Starte die visuelle Odometrie mit den vorbereiteten Daten. Das Skript läuft in einem separaten Prozess.", color=INSTRUCTION_COLOR)
                dpg.add_text("Die Odometrie Basiert auf dem Repository 'Monocular-Video-Odometry' von Ali Shobeiri (siehe Readme)\nund nutzt Feature-Tracking, Essential-Matrix-Schätzung und RANSAC zur Bewegungsschätzung.")
                dpg.add_text("Für die Auswertung wurde die Implementierung erweitert:\nPro Frame werden geschätzte Pose, Ground-Truth-Pose und zusätzliche Metriken in einer CSV-Datei gespeichert.")
                dpg.add_button(label="Odometrie starten", callback=run_visual_odometry)
                dpg.add_input_text(tag="3b_status_text", default_value="", multiline=True, readonly=True, width=970, height=80)

            # section 3C
            with dpg.tab(label=STEP_OPEN + " 3C: Kompakt-Evaluation", tag="step3_tab_3c"):
                dpg.add_text("Kompakt-Evaluation generieren und anzeigen", color=HEADING_COLOR)
                dpg.add_text("Output:", color=OUTPUT_COLOR)
                dpg.add_text("\t- Evaluationskennzahlen ergänzt in: splat_data.yaml", color=OUTPUT_COLOR)
                dpg.add_text("\t- Kompakt-Evaluationsgrafik: short-evaluation\\vo_short_eval.png", color=OUTPUT_COLOR)
                dpg.add_text("\t- Top-Down-Vergleichsgrafik: short-evaluation\\vo_top_down_eval.png", color=OUTPUT_COLOR)
                dpg.add_text("Lass die kompakte Evaluation generieren und anzeigen, um die Ergebnisse der visuellen Odometrie zu visualisieren.", color=INSTRUCTION_COLOR)
                dpg.add_button(label="Kompakt-Evaluation generieren undanzeigen", callback=show_evaluation_plot)
                dpg.add_input_text(tag="3c_status_text", default_value="", multiline=True, readonly=True, width=970, height=120)

            # section 3D
            with dpg.tab(label=STEP_OPEN + " 3D: Ausführliche Evaluation", tag="step3_tab_3d"):
                dpg.add_text("Ausführliche Evaluation vorbereiten, generieren und anzeigen", color=HEADING_COLOR)
                dpg.add_text("Speichere hierüber die aktuellen Evaluationsdaten für eine detaillierte Analyse bzw. Vergleichsanalyse\nin den zentralen Evaluations-Ordner ('/evaluation'). Vergib dafür einen aussagekräftigen Namen für die Trajektorie.", color=INSTRUCTION_COLOR)
                dpg.add_text("Hinweise zum Trajektoriennamen:")
                dpg.add_text("\t- Keine Leerzeichen verwenden, stattdessen Unterstriche.")
                dpg.add_text("\t- Keine Sonderzeichen verwenden, die für Ordnernamen ungültig sind.")
                dpg.add_text("\t- Beispiel für einen guten Namen: `Trajektorie_Test_Glättung_5`")
                with dpg.group(horizontal=True):
                    dpg.add_input_text(tag="3d_trajectory_name_input", hint="Trajektorienname", width=360)
                    dpg.add_button(label="Evaluationsdaten speichern", callback=save_evaluation_data_for_later_analysis)
                
                dpg.add_separator()

                dpg.add_text("\n\nGeneriere die Detail- bzw. Vergleichsevaluation, um eine ausführliche PDF-Auswertung mit zusätzlichen Grafiken und Analysen zu erhalten.\nDafür wird ein R-Prozess gestartet, der die Daten im zentralen Evaluationsordner verarbeitet.", color=INSTRUCTION_COLOR)
                
                dpg.add_text("\nDie Detailanalyse kann auch direkt nach Programmstart gestartet werden,\nsofern im zentralen Evaluations-Ordner ('/evaluation') bereits Trajektorien vorhanden sind.")
                dpg.add_text("Berücksichtigte Trajektorien im Evaluations-Ordner:")
                dpg.add_input_text(tag="3d_evaluation_trajectory_list", default_value="", multiline=True, readonly=True, width=360, height=70)
                with dpg.group(horizontal=True):
                    dpg.add_text("Zum ausschließen einer Trajektorie aus der Detailanalyse:\nDen entsprechenden Ordner manuell aus dem zentralen Evaluationsordner entfernen.")
                    with dpg.group():
                        dpg.add_text("")
                        dpg.add_button(label="Evaluations-Ordner öffnen", callback=open_central_evaluation_folder)

                dpg.add_button(label="Detail- / Vergleichsevaluation generieren und anzeigen", callback=show_detail_comparison_confirmation)

                dpg.add_text("")
                dpg.add_separator()
                dpg.add_text("")
                dpg.add_input_text(tag="3d_status_text", default_value="", multiline=True, readonly=True, width=970, height=210)
                update_step3_evaluation_statuses()


def build_detail_evaluation_confirm_window():
    with dpg.window(label="Detail- / Vergleichsevaluation", modal=True, show=False, tag="3d_detail_eval_confirm_window", width=560, height=330):
        dpg.add_text("Für die Detail- bzw. Vergleichsevaluation werden folgende Trajektorien berücksichtigt:", wrap=520)
        dpg.add_input_text(tag="3d_detail_eval_confirm_list", default_value="", multiline=True, readonly=True, width=520, height=130)
        with dpg.group(horizontal=True):
            dpg.add_button(label="PDF generieren", callback=run_detail_evaluation_pdf)
            dpg.add_button(label="Abbrechen", callback=lambda: dpg.hide_item("3d_detail_eval_confirm_window"))
        dpg.add_text("Hinweis: Für die PDF-Generierung muss eine LaTeX-Engine verfügbar sein. Im installierten Conda-Environment ist dafür `tectonic` vorgesehen.", color=OUTPUT_COLOR, wrap=520)

def main():
    dpg.create_context()

    with dpg.theme() as button_theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, BUTTON_COLOR)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, BUTTON_HOVER_COLOR)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, BUTTON_ACTIVE_COLOR)

    dpg.bind_theme(button_theme)

    # Main DearPyGui window.
    with dpg.window(
        label="Splat Localization Benchmark",
        tag="main_window",
        no_title_bar=True,
        no_resize=True,
        no_move=True,
        no_collapse=True
    ):
        dpg.add_separator()
        build_step1_area()
        build_step2_area()
        build_step3_area()

    build_detail_evaluation_confirm_window()

    dpg.create_viewport(title="Splat Localization Benchmark", width=1000, height=900)
    dpg.setup_dearpygui()

    dpg.set_primary_window("main_window", True)
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()


if __name__ == "__main__":
    main()
