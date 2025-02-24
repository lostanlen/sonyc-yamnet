import sys

import datetime
import glob
import h5py
import numpy as np
import os
import tensorflow as tf
import time

src_dir = os.path.dirname(os.path.abspath(__file__))
git_dir = os.path.split(src_dir)[0]
yamnet_dir = os.path.join(git_dir, "yamnet")
sys.path.append(yamnet_dir)
import params  # noqa: E402
import yamnet  # noqa: E402

# Parse arguments.
# The first argument is the path to a directory containing SONYC recordings
# for a given sensor.
# The second argument is the path to the output directory for YAMNet features.
args = sys.argv[1:]
sensor_dir = str(args[0])
out_dir = str(args[1])
sensor_str = os.path.split(sensor_dir)[1]
sonycnode_str = os.path.splitext(sensor_str)[0].split("-")[1]

# Print header.
start_time = int(time.time())
print(str(datetime.datetime.now()) + " Start.")
print("Running YAMNET on SONYC recordings for sensor " + sonycnode_str)
print("Directory: " + sensor_dir)
print("")
print("numpy version: {:s}".format(np.__version__))
print("tensorflow version: {:s}".format(tf.__version__))
print("")

# Parse parameters.
yamnet_params = {
    k: params.__dict__[k] for k in params.__dict__ if k == k.upper()}
for yamnet_param in yamnet_params:
    print(yamnet_param + " = " + str(yamnet_params[yamnet_param]))
print("")

# Load YAMNet.
# We turn the YAMNet model into a two-output model:
# 1. first output is the convnet embedding (task-agnostic)
# 2. second output is the audio event classification (task = AudioSet labels)
tf.get_logger().setLevel('ERROR')
graph = tf.Graph()
with graph.as_default():
    yamnet_model = yamnet.yamnet_frames_model(params)
    yamnet_model_path = os.path.join(yamnet_dir, "yamnet.h5")
    yamnet_model.load_weights(yamnet_model_path)
    yamnet_multi_model = tf.keras.Model(
        inputs=yamnet_model.inputs,
        outputs=[yamnet_model.layers[-4].output, yamnet_model.output]
    )

# Initialize HDF5 folder for prediction
data_dir = os.path.split(sensor_dir)[0]
out_pred_dir = os.path.join(data_dir, "covid_yamnet-pred")
os.makedirs(out_pred_dir, exist_ok=True)
h5_path = os.path.join(out_pred_dir, sonycnode_str + "_yamnet-pred.h5")

# Initialize NPZ folder for features
out_features_dir = os.path.join(out_dir, "covid_yamnet-features")
os.makedirs(out_features_dir, exist_ok=True)
out_sensor_dir = os.path.join(out_features_dir, sensor_str)
os.makedirs(out_sensor_dir, exist_ok=True)

# List SONYC recordings (NPZ files)
# These have been resampled to 16 kHz and converted to float32 by Mark Cartwright
# The directory structure is <sensor_id>/<date>/<sensor_id>_<timestamp>_16k.npz
# each npz file contains the signal x and the sample rate fs
glob_regexp = os.path.join(sensor_dir, "**", "*_16k.npz")
sonyc_paths = glob.glob(glob_regexp)

# Compute features
for sonyc_path in sonyc_paths:
    date_dir, sonyc_name = os.path.split(sonyc_path)
    sensor_timestamp_str = os.path.splitext(sonyc_name)[0]
    sensor_timestamp_split = sensor_timestamp_str.split("_")[:-1]
    sonyc_key = "_".join(sensor_timestamp_split)
    sonyc_npz = np.load(sonyc_path)
    waveform = sonyc_npz["x"][np.newaxis, :]
    with graph.as_default():
        yamnet_feature, yamnet_pred, _ = yamnet_multi_model.predict(
            waveform, steps=1)
    # Save feature.
    date_str = os.path.split(date_dir)[1]
    out_date_dir = os.path.join(out_sensor_dir, date_str)
    os.makedirs(out_date_dir, exist_ok=True)
    yamnet_feature_name = sensor_timestamp_str + "_yamnet-features.npz"
    yamnet_feature_path = os.path.join(out_date_dir, yamnet_feature_name)
    np.savez(yamnet_feature_path, yamnet_feature)
    # Save prediction.
    with h5py.File(h5_path, "a") as h5_file:
        h5_file[sonyc_key] = yamnet_pred

# Print elapsed time.
print(str(datetime.datetime.now()) + " Finish.")
elapsed_time = time.time() - int(start_time)
elapsed_hours = int(elapsed_time / (60 * 60))
elapsed_minutes = int((elapsed_time % (60 * 60)) / 60)
elapsed_seconds = elapsed_time % 60.
elapsed_str = "{:>02}:{:>02}:{:>05.2f}".format(elapsed_hours,
                                               elapsed_minutes,
                                               elapsed_seconds)
print("Total elapsed time: " + elapsed_str + ".")
