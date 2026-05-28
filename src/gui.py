import csv
import os
import dearpygui.dearpygui as dpg
from tkinter import Tk
from tkinter import filedialog

step1 = __import__("1a_find_plane_candidates")
floor_view = __import__("1b_interactive_floor_validation")
floor_alignment = __import__("1c_manual_floor_alignment")
final_transform = __import__("1d_build_transform")


STEP_OPEN = "[  ]"
STEP_DONE = "[OK]"

step1_point_cloud = None
step1_plane_candidates = None
step1_floor_view_cache = {}
step1_validated_floor_data = None
step1_alignment_data = None
step1_final_transform_data = None
step2_splat_output_dir = None

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

    dpg.draw_rectangle((0, 0), (width, height), color=(80, 80, 80, 255), parent="floor_candidate_preview")

    plane_points = view_data["plane_view_points"]

    if len(plane_points) == 0:
        dpg.draw_text((20, 20), "Dieser Kandidat hat keine Inlier", parent="floor_candidate_preview")
        return

    x_min = plane_points[:, 0].min()
    x_max = plane_points[:, 0].max()
    y_min = plane_points[:, 1].min()
    y_max = plane_points[:, 1].max()

    center_x = (x_min + x_max) / 2
    center_y = (y_min + y_max) / 2

    scale_x = (width - 2 * border) / (x_max - x_min + 0.000001)
    scale_y = (height - 2 * border) / (y_max - y_min + 0.000001)
    scale = min(scale_x, scale_y)

    def to_screen(point):
        x = width / 2 + (point[0] - center_x) * scale
        y = height / 2 - (point[1] - center_y) * scale
        return x, y

    top_left = to_screen([x_min, y_max])
    bottom_right = to_screen([x_max, y_min])
    dpg.draw_rectangle(
        top_left,
        bottom_right,
        color=(0, 180, 80, 190),
        fill=(0, 180, 80, 35),
        parent="floor_candidate_preview"
    )

    visible_points = floor_view.sample_points_for_drawing(visible_points, 10000)

    for point in visible_points:
        x, y = to_screen(point)
        dpg.draw_rectangle(
            (x, y),
            (x + 1, y + 1),
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
        dpg.draw_text((20, 20), "Kein Kandidat ausgewaehlt", parent="floor_candidate_preview")
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
        "Sichtbarer Hoehenbereich: "
        + format(min_height, ".2f")
        + " bis "
        + format(max_height, ".2f")
        + " ueber der Ebene"
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
        dpg.draw_text((20, 20), "Keine Punkte im validierten Hoehenbereich", parent="floor_alignment_preview")
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

    points_2d = floor_view.sample_points_for_drawing(points_2d, 10000)

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
        + " Punkte aus dem validierten Hoehenbereich"
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

    show_status("1C: Ausrichtung uebernommen\n")
    show_status("\tRotation um Z: " + format(yaw_deg, ".2f") + " Grad\n")
    show_status("\tUrsprung X: " + format(origin_x, ".2f") + "\n")
    show_status("\tUrsprung Y: " + format(origin_y, ".2f") + "\n")
    show_status("\tTransformation fuer 1D vorbereitet\n")

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

    step1_final_transform_data = final_transform.build_final_transform(
        step1_validated_floor_data,
        step1_alignment_data,
    )

    splat_file = dpg.get_value("splat_file_input")
    splat_file_path = os.path.abspath(splat_file)
    splat_file_name = os.path.basename(splat_file)
    splat_name = os.path.splitext(splat_file_name)[0]
    output_dir = os.path.join("splats", splat_name)

    os.makedirs(output_dir, exist_ok=True)

    transform_yaml_path = os.path.join(output_dir, "transform.yaml")
    grid_file_path = os.path.join(output_dir, "top_down_grid.npz")

    T_splat_to_sim = step1_final_transform_data["T_splat_to_sim"]
    T_sim_to_splat = step1_final_transform_data["T_sim_to_splat"]

    height_filter = step1_validated_floor_data["height_filter"]
    min_height = height_filter["min_height"]
    max_height = height_filter["max_height"]
    cell_size = 0.05

    points_sim = final_transform.transform_points(step1_point_cloud, T_splat_to_sim)
    occupancy_grid, origin_xy, height_range, visible_point_count = final_transform.build_top_down_grid(
        points_sim,
        min_height,
        max_height,
        cell_size,
    )

    final_transform.write_transform_yaml(
        transform_yaml_path,
        splat_file_name,
        splat_file_path,
        T_splat_to_sim,
        T_sim_to_splat,
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
    step1_final_transform_data["transform_yaml"] = transform_yaml_path
    step1_final_transform_data["top_down_grid"] = grid_file_path

    show_status("1D: Gesamttransformation berechnet\n")
    show_status("\tKandidat: " + str(step1_validated_floor_data["candidate_number"]) + "\n")
    show_status("\tRotation um Z: " + format(step1_alignment_data["yaw_deg"], ".2f") + " deg\n")
    show_status("\tUrsprung X: " + format(step1_alignment_data["origin_x"], ".2f") + "\n")
    show_status("\tUrsprung Y: " + format(step1_alignment_data["origin_y"], ".2f") + "\n\n")

    if visible_point_count == 0:
        show_status("Keine Punkte im gewaehlten Hoehenbereich gefunden\n\n")

    show_status("Gespeichert in:\n")
    show_status(output_dir + "\n\n")
    show_status("Dateien:\n")
    show_status("transform.yaml\n")
    show_status("top_down_grid.npz\n\n")

    show_status("T_splat_to_sim:\n")
    show_status(final_transform.format_matrix(T_splat_to_sim))
    show_status("\n\nT_sim_to_splat:\n")
    show_status(final_transform.format_matrix(T_sim_to_splat))
    show_status("\n")

    set_tab_done("step1_tab_1d", "1D: Transformation")


def show_saved_top_down_grid():
    """Open the saved top-down grid in Matplotlib"""

    dpg.set_value("1d_output_text", "")

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

    root = Tk()
    root.withdraw()

    initial_dir = "splats"
    if not os.path.isdir(initial_dir):
        initial_dir = "."

    # selection for splat output folder
    selected_folder = filedialog.askdirectory(
        title="Splat-Ordner auswaehlen",
        initialdir=initial_dir,
    )
    root.destroy()

    if not selected_folder:
        return

    selected_folder = os.path.normpath(selected_folder)
    dpg.set_value("splat_output_folder_input", selected_folder)
    step2_splat_output_dir = selected_folder

    # grid file from step 1D
    grid_file_path = os.path.join(selected_folder, "top_down_grid.npz")

    if not os.path.isfile(grid_file_path):
        set_step2a_status("top_down_grid.npz nicht gefunden")
        return

    set_step2a_status("top_down_grid.npz gefunden")


def load_top_down_grid(grid_file_path):
    """Load the grid values needed for trajectory drawing"""

    import numpy as np

    # npz file from step 1D
    data = np.load(grid_file_path)
    occupancy_grid = data["occupancy_grid"]

    # size per grid cell in Sim coordinates
    cell_size = float(data["cell_size"])
    origin_xy = data["origin_xy"]

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

    import matplotlib.pyplot as plt

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
    title_text = "Rechtsklick: Wegpunkt setzen , Enter: speichern , Schließen: verwerfen\n Für Kurven: mehrere Punkte eng setzen"

    # create matplotlib window
    fig, ax = plt.subplots(num="Trajektorie einzeichen")

    # draw grid
    ax.imshow(
        occupancy_grid,
        origin="lower",
        extent=[x_min, x_max, y_min, y_max],
        interpolation="nearest",
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

    def on_click(event):
        if event.inaxes != ax:
            return

        if event.xdata is None or event.ydata is None:
            return

        # right click adds a waypoint.
        if event.button == 3:
            points_xy.append([float(event.xdata), float(event.ydata)])
            ax.set_title(title_text)
            redraw_line()

    def on_key(event):
        # Enter saves the trajectory
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

    fig.canvas.mpl_connect("button_press_event", on_click)
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
        set_step2a_status("Erst Ordner auswaehlen")
        return

    selected_folder = os.path.normpath(selected_folder)
    dpg.set_value("splat_output_folder_input", selected_folder)
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

    set_step2a_status(
        result_message
        + "\n"
        + trajectory_file_path
        + "\n"
        + str(point_count)
        + " Wegpunkte"
    )
    set_tab_done("step2_tab_2a", "2A: Trajektorie")


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

    if len(candidate_names) > 0:
        dpg.set_value("floor_candidate_combo", candidate_names[0])
        draw_floor_candidate()

    # step 1A finished -> mark tab as done
    set_tab_done("step1_tab_1a", "1A: Ebenen finden")


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

    show_status("1B: Bodenebene ausgewaehlt\n")
    show_status("\tKandidat: " + str(candidate_number) + "\n")
    show_status("\tHoehenbereich: " + format(min_height, ".2f") + " bis " + format(max_height, ".2f") + "\n")
    show_status("\tOberseite wurde automatisch bestimmt\n")
    show_status("\tPunkte oberhalb: " + format(view_data["orientation_info"]["positive_ratio"] * 100, ".1f") + " %\n")
    show_status("\tBoden-Transformation fuer 1C vorbereitet\n")

    set_tab_done("step1_tab_1b", "1B: Boden waehlen")


def build_step1_area():
    
    # main steps are vertical collapsing headers
    with dpg.collapsing_header(label="Schritt 1: Koordinatentransformation generieren", default_open=True):     
        
        with dpg.tab_bar(tag="step1_tab_bar"):
        # substeps are tabs inside the main step

            # section 1A
            with dpg.tab(label=STEP_OPEN + " 1A: Ebenen finden", tag="step1_tab_1a"):

                dpg.add_text("Splatdatei auswaehlen und Boden-Ebenenkandidaten suchen")
                dpg.add_text(
                    "Waehle eine Splatdatei aus und starte die Suche nach ebenen Flaechen, die als Boden in Frage kommen."
                )

                with dpg.group(horizontal=True):
                    dpg.add_input_text(tag="splat_file_input", default_value=step1.SPLAT_FILE, width=650)
                    dpg.add_button(label="Durchsuchen", callback=show_file_dialog)

                dpg.add_button(label="Ebenenkandidaten suchen", callback=run_plane_search)
                dpg.add_separator()
                dpg.add_text("", tag="1a_output_text")

            # section 1B
            with dpg.tab(label=STEP_OPEN + " 1B: Boden waehlen", tag="step1_tab_1b"):
                dpg.add_text("Ebenenkandidaten anzeigen und Bodenebene validieren")
                dpg.add_text(
                    "Waehle den passendsten Kandidaten aus und stelle den Hoehenfilter so ein,\ndass die Raumstruktur und Hindernisse in der Draufsicht moeglichst klar erkennbar sind."
                )
                dpg.add_combo(label="Kandidat", tag="floor_candidate_combo", items=[], width=200, callback=draw_floor_candidate)
                dpg.add_text("", tag="floor_orientation_status")

                dpg.add_slider_float(label="Hoehenfilter: Untergrenze ueber Ebene", tag="floor_min_height_slider", default_value=0.0, min_value=0.0, max_value=3.0, width=420, callback=draw_floor_candidate)
                dpg.add_slider_float(label="Hoehenfilter: Obergrenze ueber Ebene", tag="floor_max_height_slider", default_value=3.0, min_value=0.0, max_value=3.0, width=420, callback=draw_floor_candidate)
                dpg.add_text("Sichtbarer Hoehenbereich: 0.00 bis 3.00 ueber der Ebene", tag="floor_height_status")

                dpg.add_drawlist(width=700, height=420, tag="floor_candidate_preview")

                dpg.add_button(label="Bodenebene validieren", callback=validate_floor_plane)
                dpg.add_separator()
                dpg.add_text("", tag="1b_output_text")

            # section 1C
            with dpg.tab(label=STEP_OPEN + " 1C: Ausrichten", tag="step1_tab_1c"):
                dpg.add_text("Raumrotation und XY-Ursprung manuell anpassen")
                dpg.add_text("Richte die validierte Draufsicht an den X/Y-Achsen aus und lege den Ursprung fest.")
                dpg.add_text("Erst Bodenebene in 1B validieren", tag="1c_alignment_status")

                dpg.add_slider_float(label="Rotation um Z", tag="alignment_yaw_slider", default_value=0.0, min_value=-180.0, max_value=180.0, width=420, callback=draw_floor_alignment)
                dpg.add_slider_float(label="Ursprung X", tag="alignment_origin_x_slider", default_value=0.0, min_value=-10.0, max_value=10.0, width=420, callback=draw_floor_alignment)
                dpg.add_slider_float(label="Ursprung Y", tag="alignment_origin_y_slider", default_value=0.0, min_value=-10.0, max_value=10.0, width=420, callback=draw_floor_alignment)

                dpg.add_drawlist(width=700, height=420, tag="floor_alignment_preview")

                dpg.add_button(label="Ausrichtung uebernehmen", callback=accept_floor_alignment)
                dpg.add_separator()
                dpg.add_text("", tag="1c_output_text")

            # section 1D
            with dpg.tab(label=STEP_OPEN + " 1D: Transformation", tag="step1_tab_1d"):
                dpg.add_text("Gesamttransformation pruefen und speichern")
                dpg.add_text("Berechnet die Gesamttransformation aus validierter Bodenebene und manueller Ausrichtung.")
                dpg.add_button(label="Transformation berechnen", callback=calculate_final_transform)
                dpg.add_button(label="Top-Down Grid anzeigen", callback=show_saved_top_down_grid)
                dpg.add_separator()
                dpg.add_text("", tag="1d_output_text")


def build_step2_area():

    with dpg.collapsing_header(label="Schritt 2: Trajektorie festlegen und Bilddaten generieren"):
        with dpg.tab_bar(tag="step2_tab_bar"):

            # section 2A
            with dpg.tab(label="2A: Trajektorie", tag="step2_tab_2a"):
                dpg.add_text("Trajektorie festlegen")

                dpg.add_text("Wähle den Ordner aus `splats/...`, der zu deiner Splat-Datei gehört. Daraus wird die gespeicherte Top-Down-Karte und später Transformation geladen.")

                with dpg.group(horizontal=True):
                    dpg.add_input_text(tag="splat_output_folder_input", width=650)
                    dpg.add_button(label="Ordner auswaehlen", callback=select_splat_output_folder)

                dpg.add_text("Hinweis: Die Trajektorie besteht aus geraden Linien zwischen den Wegpunkten.")
                dpg.add_text("Fuer Kurven bitte mehrere Punkte eng hintereinander setzen.")
                dpg.add_text("Reine Drehungen auf der Stelle oder Kurvenglättungen werden nicht automatisch erzeugt.")
                dpg.add_text("Im Zeichenfenster setzt Rechtsklick einen Wegpunkt")
                dpg.add_text("Mit Enter wird gespeichert, beim Schliessen wird verworfen.")

                dpg.add_button(label="Trajektorie einzeichnen", callback=start_trajectory_drawing)
                dpg.add_separator()
                dpg.add_input_text(
                    tag="2a_output_text",
                    default_value="",
                    multiline=True,
                    readonly=True,
                    width=700,
                    height=100,
                )

            # section 2B
            with dpg.tab(label="2B: Bilddaten", tag="step2_tab_2b"):
                dpg.add_text("Bilddaten generieren")


def build_step3_area():
    
    with dpg.collapsing_header(label="Schritt 3: Lokalisierung und Evaluation"):
        with dpg.tab_bar(tag="step3_tab_bar"):
            
            # section 3A
            with dpg.tab(label="3A: Lokalisierung", tag="step3_tab_3a"):
                dpg.add_text("Lokalisierung ausfuehren")

            # section 3B
            with dpg.tab(label="3B: Evaluation", tag="step3_tab_3b"):
                dpg.add_text("Evaluation anzeigen")


def main():
    dpg.create_context()

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

    dpg.create_viewport(title="Splat Localization Benchmark", width=1000, height=750)
    dpg.setup_dearpygui()

    dpg.set_primary_window("main_window", True)
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()


if __name__ == "__main__":
    main()
