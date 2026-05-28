"""Generate simple camera poses from trajectory waypoints."""

import csv

import numpy as np


POSE_SPACING = 0.10
LOOKAHEAD_STEPS = 5


def load_trajectory_csv(file_path):
    """Load x/y waypoints from trajectory.csv"""

    waypoints = []

    # read x and y values from the csv file
    with open(file_path, "r", newline="", encoding="utf-8") as file:
        reader = csv.reader(file)
        next(reader, None)

        for row in reader:
            x = float(row[1])
            y = float(row[2])
            waypoints.append([x, y])

    waypoints = np.array(waypoints, dtype=float)

    if len(waypoints) < 2:
        raise ValueError("Mindestens zwei Wegpunkte erforderlich")

    return waypoints


def create_evenly_spaced_points(waypoints, spacing):
    """Create points with equal spacing between the waypoints"""

    points = []

    # create points along every path segment
    for index in range(len(waypoints) - 1):
        start_point = waypoints[index]
        end_point = waypoints[index + 1]

        direction = end_point - start_point
        length = np.linalg.norm(direction)

        # skip segment if both points are the same
        if length == 0:
            continue

        # make direction a unit vector to only shows the direction
        direction = direction / length

        distance = 0.0
        while distance < length:
            new_point = start_point + direction * distance

            # do not add the same point two times
            if len(points) == 0 or np.linalg.norm(points[-1] - new_point) > 0.000001:
                points.append(new_point)

            distance += spacing

    # add last waypoint
    if len(points) == 0 or np.linalg.norm(points[-1] - waypoints[-1]) > 0.000001:
        points.append(waypoints[-1])

    return np.array(points, dtype=float)


def compute_yaw_angles(points, lookahead_steps):
    """Calculate yaw angle for every point"""

    yaw_angles = []
    last_yaw_deg = 0.0

    for index in range(len(points)):
        # look a few points ahead to get a smoother direction
        target_index = index + lookahead_steps

        if target_index >= len(points):
            target_index = len(points) - 1

        dx = points[target_index][0] - points[index][0]
        dy = points[target_index][1] - points[index][1]

        # keep last direction for the final points
        if dx == 0 and dy == 0:
            yaw_angles.append(last_yaw_deg)
            continue

        yaw_rad = np.arctan2(dy, dx)
        yaw_deg = np.degrees(yaw_rad)

        yaw_angles.append(yaw_deg)
        last_yaw_deg = yaw_deg

    return np.array(yaw_angles, dtype=float)


def build_camera_poses(points, camera_height, yaw_angles):
    """Build frame, x, y, z, yaw_deg rows"""

    camera_poses = []

    for index, point in enumerate(points):
        frame = index
        x = float(point[0])
        y = float(point[1])
        z = float(camera_height)
        yaw_deg = float(yaw_angles[index])

        camera_poses.append([frame, x, y, z, yaw_deg])

    return camera_poses
