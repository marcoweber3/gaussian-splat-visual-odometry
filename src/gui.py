"""
Simple GUI for the pipeline.
"""

import dearpygui.dearpygui as dpg
from tkinter import Tk
from tkinter import filedialog

import step1_generate_coordinate_transform as step1


STEP_OPEN = "[  ]"
STEP_DONE = "[OK]"


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


def run_plane_search():
    dpg.set_value("1a_output_text", "")

    splat_file = dpg.get_value("splat_file_input")

    def show_status(new_text):
        # callback for outputting 1A status messages
        old_text = dpg.get_value("1a_output_text")
        dpg.set_value("1a_output_text", old_text + new_text)
        dpg.render_dearpygui_frame()

    # run step 1A and show status messages in the GUI
    step1_result = step1.run_step_1a(splat_file, show_status)

    if step1_result is None:
        return

    # step 1A finished -> mark tab as done
    set_tab_done("step1_tab_1a", "1A: Ebenen finden")


def build_step1_area():
    
    # main steps are vertical collapsing headers
    with dpg.collapsing_header(label="Schritt 1: Koordinatentransformation generieren", default_open=True):     
        
        with dpg.tab_bar(tag="step1_tab_bar"):
        # substeps are tabs inside the main step

            # section 1A
            with dpg.tab(label=STEP_OPEN + " 1A: Ebenen finden", tag="step1_tab_1a"):

                dpg.add_text("Splatdatei auswaehlen und Boden-Ebenenkandidaten suchen")

                with dpg.group(horizontal=True):
                    dpg.add_input_text(tag="splat_file_input", default_value=step1.SPLAT_FILE, width=650)
                    dpg.add_button(label="Durchsuchen", callback=show_file_dialog)

                dpg.add_button(label="Ebenenkandidaten suchen", callback=run_plane_search)
                dpg.add_separator()
                dpg.add_text("", tag="1a_output_text")

            # section 1B
            with dpg.tab(label=STEP_OPEN + " 1B: Boden waehlen", tag="step1_tab_1b"):
                dpg.add_text("Ebenenkandidaten anzeigen und Bodenebene validieren")

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
