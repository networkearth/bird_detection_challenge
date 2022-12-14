import os
from statistics import median
import click
import shutil
import librosa
import numpy as np
import pandas as pd

from tqdm import tqdm
from scipy.signal.windows import hamming
from PIL import Image

def build_spectrogram(
    song, sr=22050, overlap=0.5, frame_length=0.04, n_mels=40
):
    samples_per_frame = frame_length * sr
    n_fft = int(samples_per_frame)
    hop_length = int((1 - overlap) * samples_per_frame)
    window = hamming

    expected_samples = int(len(song)/samples_per_frame/overlap)

    S = librosa.feature.melspectrogram(
        y=song, sr=sr, n_fft=n_fft, hop_length=hop_length,
        window=window, n_mels=n_mels, power=1, center=True,
    )
    S_DB = librosa.amplitude_to_db(S, ref=np.max)[:,:expected_samples]
    if S_DB.shape == (n_mels, expected_samples):
        return S_DB
    return None

def filter_spectrogram(
    spectrogram
):
    # this just does median filtering along each frequency bin
    median_filtered = (
        (spectrogram.T > np.median(spectrogram, axis=1)) * (spectrogram.T) + (spectrogram.T <= np.median(spectrogram, axis=1)) * np.median(spectrogram, axis=1)
    ).T
    # and then drops the frequency bin by its median 
    # so the "noise" level is the same for each bin
    median_filtered = (
        (median_filtered.T - np.median(median_filtered, axis=1))
    ).T
    return median_filtered

def prepare_for_img(data):
    data -= data.min()
    data /= data.max()
    data *= 255
    data = data.astype(np.uint8)
    return data

def load_song(file_path):
    y, sr = librosa.load(file_path)
    song, _ = librosa.effects.trim(y)
    return song, sr

@click.command()
@click.option('-i', '--input_dir', required=True, help='input directory of wav files')
@click.option('-s', '--spectrogram_dir', required=True, help='output file to write spectrograms')
@click.option('-o', '--overlap', required=False, default=0.5, type=float, help='overlap between frames')
@click.option('-f', '--frame_length', required=False, default=0.04, type=float, help='length (s) of frames')
@click.option('-n', '--n_mels', required=False, default=40, type=int, help='number of Mel buckets')
@click.option('-m', '--labels_map', required=True, help='file with map between file name and labels')
def main(input_dir, spectrogram_dir, overlap, frame_length, n_mels, labels_map):
    if os.path.exists(spectrogram_dir):
        shutil.rmtree(spectrogram_dir)
    os.mkdir(spectrogram_dir)

    labels_map = {
        str(row['itemid']): int(row['hasbird'])
        for _, row in pd.read_csv(labels_map).iterrows()
    }

    for file_path in tqdm(os.listdir(input_dir)):
        input_file_path = os.path.join(input_dir, file_path)
        song, sr = load_song(input_file_path)

        if len(song) / sr > 10.: 
            song = song[:sr*10]

        if len(song) / sr < 10:
            song = np.pad(song, [(0, sr * 10 - (len(song)))])

        spectrogram = build_spectrogram(
            song, sr, overlap=overlap, frame_length=frame_length,
            n_mels=n_mels
        )
        if spectrogram is not None:
            spectrogram = filter_spectrogram(spectrogram)
            spectrogram = prepare_for_img(spectrogram)

            label = 'hasbird' if labels_map[file_path.split('.')[0]] == 1 else 'nobird'
            root = '.'.join(file_path.split('.')[:-1])
            output_file_path = os.path.join(
                spectrogram_dir, 
                label, 
                f'{root}.png'
            )
            if not os.path.exists(os.path.join(spectrogram_dir, label)):
                os.mkdir(os.path.join(spectrogram_dir, label))
            Image.fromarray(spectrogram, mode='L').save(output_file_path)
