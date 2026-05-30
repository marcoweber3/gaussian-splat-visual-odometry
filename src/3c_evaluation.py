import csv
import os

import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np


def plot_odometry_csv(csv_file, grid_file):
    """Plot estimated and true trajectory from vo_output.csv"""

    estimated_x = []
    estimated_y = []
    true_x = []
    true_y = []

    # load csv values
    with open(csv_file, "r", newline="", encoding="utf-8") as file:
        reader = csv.reader(file)
        header = next(reader)

        x_index = header.index("x")
        y_index = header.index("y")
        true_x_index = header.index("true_x")
        true_y_index = header.index("true_y")

        for row in reader:
            estimated_x.append(float(row[x_index]))
            estimated_y.append(float(row[y_index]))
            true_x.append(float(row[true_x_index]))
            true_y.append(float(row[true_y_index]))

    if len(estimated_x) == 0:
        raise ValueError("Keine Daten in vo_output.csv gefunden")

    # plot trajectories
    plt.figure("Evaluation")
    plt.clf()

    if os.path.isfile(grid_file):
        # draw occupancy map
        data = np.load(grid_file)
        occupancy_grid = data["occupancy_grid"]
        cell_size = float(data["cell_size"])
        origin_xy = data["origin_xy"]

        height = occupancy_grid.shape[0] * cell_size
        width = occupancy_grid.shape[1] * cell_size
        x_min = origin_xy[0]
        y_min = origin_xy[1]

        plt.imshow(
            occupancy_grid,
            origin="lower",
            extent=[x_min, x_min + width, y_min, y_min + height],
            interpolation="nearest",
            cmap=ListedColormap(["white", "black"]),
            vmin=0,
            vmax=1,
        )

        data.close()

    plt.plot(true_x, true_y, "r-", label="Echt")
    plt.plot(estimated_x, estimated_y, "g-", label="Geschätzt")
    plt.xlabel("x")
    plt.ylabel("y")
    plt.title("Visual Odometry Evaluation")
    plt.axis("equal")
    plt.grid(True)
    plt.legend()
    plt.show()
