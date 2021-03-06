# To add a new cell, type '
# To add a new markdown cell, type'
#
# Vinh Phuc Ta Dang ft Dao Cong Tinh
#
import os
import cv2
import time
import posenet
import numpy as np
from constants import *
from scipy.spatial.distance import euclidean
from tensorflow.compat.v1.keras import backend as K

VID_EXT_VALIDS = ['.mp4', '.mov']
scale_factor = 0.4 # 0.5
VIDEO_URI = 0
GUI_Enable = True
oo = 1e9
SCORE_THRESHOLD = 0.15

def normalize(features):
    mx = np.max(features)
    mn = np.min(features)
    for feature in features:
        for i in range(len(feature)):
            feature[i] = (feature[i] - mn) / (mx - mn)

    return np.array(features)

def extractFeature(frame_seq):
    features = []
    kp_prev = frame_seq[0]
    for i in range(1, len(frame_seq)):
        kp_curr = frame_seq[i]
        dist = []
        for p_i, p_j in zip(kp_curr, kp_prev):
            dist.append(euclidean(p_i, p_j))
        features.append(dist)

    return normalize(features)

def extractFeatures(VIDEO_URI):
    sess = K.get_session()
    model_cfg, model_outputs = posenet.load_model(101, sess)
    output_stride = model_cfg['output_stride']

    cap = cv2.VideoCapture(VIDEO_URI)
    flip = False
    frame_series, frame_seq = [], []

    # used to record the time when we processed last frame
    prev_frame_time = 0

    # used to record the time at which we processed current frame
    new_frame_time = 0
    print('Extracting video ' + VIDEO_URI + '...')
    while True:
        try:
            input_image, display_image, output_scale = posenet.read_cap(
                cap, flip=flip, scale_factor=scale_factor, output_stride=output_stride)
        except:
            print("End video %s.%d\n" % (VIDEO_URI, len(frame_series)))
            break

        # time when we finish processing for this frame
        new_frame_time = time.time()

        # Calculating the fps
        # fps will be number of frame processed in given time frame
        # since their will be most of time error of 0.001 second
        # we will be subtracting it to get more accurate result
        fps = 1 / (new_frame_time - prev_frame_time)
        prev_frame_time = new_frame_time

        # converting the fps into integer
        fps = int(fps)

        heatmaps_result, offsets_result, displacement_fwd_result, displacement_bwd_result = sess.run(
            model_outputs,
            feed_dict={'image:0': input_image}
        )

        pose_scores, keypoint_scores, keypoint_coords = posenet.decode_multi.decode_multiple_poses(
            heatmaps_result.squeeze(axis=0),
            offsets_result.squeeze(axis=0),
            displacement_fwd_result.squeeze(axis=0),
            displacement_bwd_result.squeeze(axis=0),
            output_stride=output_stride,
            min_pose_score=SCORE_THRESHOLD)
        keypoint_coords *= output_scale

        frame_seq.append(keypoint_coords[0])
        if len(frame_seq) % window_size == 0:
            normalized_feature = extractFeature(frame_seq)
            frame_series.append(normalized_feature)
            frame_seq = []

        # TODO this isn't particularly fast, use GL for drawing and display someday...
        if GUI_Enable:
            display_image = posenet.draw_fps(display_image, fps)
            overlay_image = posenet.draw_skel_and_kp(
                display_image, pose_scores, keypoint_scores, keypoint_coords,
                min_pose_score=SCORE_THRESHOLD, min_part_score=SCORE_THRESHOLD)

            cv2.imshow('posenet', overlay_image)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    return np.array(frame_series)


actions = np.array([])
labels = np.array([])
datasets_dir = 'pose/datasets'

time_start = time.time()
for action in classes:
    action_dir = os.path.join(datasets_dir, action)
    if '.DS_Store' not in action_dir:
        print("\n############# ACTION: %s #############\n" % action)
        total = 0
        for vid in os.listdir(action_dir):
            name, ext = os.path.splitext(vid)
            if ext in VID_EXT_VALIDS and "v2" not in name:
                video_path = os.path.join(action_dir, vid)
                keyPoints = extractFeatures(video_path)
                labels = np.append(labels, np.array(
                    [action]*keyPoints.shape[0]))
                total += keyPoints.shape[0]
                if len(actions) == 0:
                    actions = keyPoints
                else:
                    actions = np.vstack((actions, keyPoints))
        print("Total: %d" % total)
time_end = time.time()

# View result
print('Norm_MinMax_Dist2_%02d' % window_size)
print('Total-time: %.6f (s)' % (time_end - time_start))
print('actions.shape =', actions.shape)
print('labels.shape =', labels.shape)

# Store data numpy array
np.save('normalized/Norm_MinMax_Dist2_%02d_X.npy' % window_size, actions)
np.save('normalized/Norm_MinMax_Dist2_%02d_y.npy' % window_size, labels)
