import csv
import os
import cv2
import numpy as np


def find_supersplat_video(splat_output_dir):
    # find supersplat video
    video_folder = os.path.join(splat_output_dir, "supersplat_video")

    if not os.path.isdir(video_folder):
        raise ValueError("Ordner supersplat_video nicht gefunden")

    for file_name in os.listdir(video_folder):
        if file_name.lower().endswith(".mp4"):
            return os.path.join(video_folder, file_name)

    raise ValueError("Keine mp4-Datei in supersplat_video gefunden")


def split_video_to_images(video_file, image_output_dir):
    video = cv2.VideoCapture(video_file)

    if not video.isOpened():
        raise ValueError("Video konnte nicht gelesen werden")

    os.makedirs(image_output_dir, exist_ok=True)

    # remove old images
    for file_name in os.listdir(image_output_dir):
        if file_name.lower().endswith(".png"):
            os.remove(os.path.join(image_output_dir, file_name))

    # split video into images
    frame_index = 0

    while True:
        success, frame = video.read()

        if not success:
            break

        file_name = str(frame_index).zfill(6) + ".png"
        image_file = os.path.join(image_output_dir, file_name)

        # save frame as png
        cv2.imwrite(image_file, frame)
        frame_index += 1

    video.release()

    if frame_index == 0:
        raise ValueError("Keine Bilder aus Video extrahiert")

    return frame_index


def load_camera_poses_sim(file_path):
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


def build_camera_pose_matrix(x, y, z, yaw_deg):
    yaw = np.radians(yaw_deg)

    right = np.array([-np.sin(yaw), np.cos(yaw), 0.0])
    up = np.array([0.0, 0.0, 1.0])
    forward = np.array([np.cos(yaw), np.sin(yaw), 0.0])

    pose_matrix = np.eye(4)
    pose_matrix[:3, 0] = right
    pose_matrix[:3, 1] = up
    pose_matrix[:3, 2] = forward
    pose_matrix[:3, 3] = np.array([x, y, z], dtype=float)

    return pose_matrix


def write_kitti_poses(camera_poses, output_file, num_used):
    first_pose = camera_poses[0]
    T_world_cam_0 = build_camera_pose_matrix(first_pose[1], first_pose[2], first_pose[3], first_pose[4])
    T_cam0_world = np.linalg.inv(T_world_cam_0)

    # write poses relative to first camera
    with open(output_file, "w", encoding="utf-8") as file:
        for index in range(num_used):
            pose = camera_poses[index]
            T_world_cam_i = build_camera_pose_matrix(pose[1], pose[2], pose[3], pose[4])
            T_relative = T_cam0_world @ T_world_cam_i
            pose_values = T_relative[:3, :4].reshape(-1)

            line_values = []

            for value in pose_values:
                line_values.append(format(value, ".9f"))

            file.write(" ".join(line_values) + "\n")


def prepare_visual_odometry_data(splat_output_dir, image_output_dir, poses_output_file):
    splat_output_dir = os.path.normpath(splat_output_dir)

    camera_poses_file = os.path.join(splat_output_dir, "camera_poses_sim.csv")

    if not os.path.isfile(camera_poses_file):
        raise ValueError("camera_poses_sim.csv nicht gefunden")

    video_file = find_supersplat_video(splat_output_dir)

    os.makedirs(os.path.dirname(poses_output_file), exist_ok=True)

    num_images = split_video_to_images(video_file, image_output_dir)

    camera_poses = load_camera_poses_sim(camera_poses_file)
    num_poses = len(camera_poses)
    num_used = min(num_images, num_poses)

    if num_used > 0:
        # write poses in kitti format
        write_kitti_poses(camera_poses, poses_output_file, num_used)
    else:
        open(poses_output_file, "w", encoding="utf-8").close()

    return video_file, num_images, num_poses
