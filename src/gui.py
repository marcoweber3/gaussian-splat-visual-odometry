import dearpygui.dearpygui as dpg
from tkinter import Tk
from tkinter import filedialog

step1 = __import__("1a_find_plane_candidates")
floor_view = __import__("1b_interactive_floor_validation")


STEP_OPEN = "[  ]"
STEP_DONE = "[OK]"

step1_point_cloud = None
step1_plane_candidates = None
step1_floor_view_cache = {}
step1_validated_floor_data = None

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

    visible_points = floor_view.sample_points_for_drawing(visible_points, 20000)

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


def run_plane_search():
    global step1_point_cloud
    global step1_plane_candidates
    global step1_floor_view_cache
    global step1_validated_floor_data

    dpg.set_value("1a_output_text", "")
    dpg.set_value("1b_output_text", "")
    step1_validated_floor_data = None

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

            # section 1D
            with dpg.tab(label=STEP_OPEN + " 1D: Transformation", tag="step1_tab_1d"):
                dpg.add_text("Gesamttransformation pruefen und speichern")


def build_step2_area():

    with dpg.collapsing_header(label="Schritt 2: Fahrweg festlegen und Bilddaten generieren"):
        with dpg.tab_bar(tag="step2_tab_bar"):

            # section 2A
            with dpg.tab(label="2A: Fahrweg", tag="step2_tab_2a"):
                dpg.add_text("Fahrweg festlegen")

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
