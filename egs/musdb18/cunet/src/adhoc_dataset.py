import os
import random
import json

import numpy as np
import torch
import torchaudio

from utils.utils_audio import build_window
from dataset import MUSDB18Dataset

__sources__=['drums','bass','other','vocals']

SAMPLE_RATE_MUSDB18 = 44100
EPS=1e-12
THRESHOLD_POWER=1e-5

class WaveDataset(MUSDB18Dataset):
    def __init__(self, musdb18_root, sr=44100, sources=__sources__, target=None):
        super().__init__(musdb18_root, sr=sr, sources=sources, target=target)

        self.json_data = None

    def __getitem__(self, idx):
        """
        Args:
            idx <int>: index
        Returns:
            mixture <torch.Tensor>: (n_mics, T)
            target <torch.Tensor>: (n_mics, T)
            latent <torch.Tensor>: (len(target),)
            name <str>: Artist and title of song
            sources <torch.Tensor>: (len(target),n_mics, T)
            scale <float>: ()
        """
        data = self.json_data[idx]

        songID = data['songID']
        track = self.tracks[songID]
        name = track['name']
        paths = track['path']
        start = data['start']
        samples = data['samples']

        if set(self.sources) == set(__sources__):
            mixture, _ = torchaudio.load(paths['mixture'], frame_offset=start, num_frames=samples)
        else:
            sources = []
            for _source in self.sources:
                source, _ = torchaudio.load(paths[_source], frame_offset=start, num_frames=samples)
                sources.append(source.unsqueeze(dim=0))
            sources = torch.cat(sources, dim=0)
            mixture = sources.sum(dim=0)
        
        if type(self.target) is list:
            latent = torch.zeros(len(self.target))

            _target = random.choice(self.sources)
            source_idx = self.sources.index(_target)
            scale = random.uniform(0, 1)
            latent[source_idx] = scale

            target, _ = torchaudio.load(paths[_target], frame_offset=start, num_frames=samples)
            target = scale * target
        else:
            raise ValueError("self.target must be list.")

        return mixture, target, latent, name, sources, scale

    def __len__(self):
        return len(self.json_data)

class SpectrogramDataset(WaveDataset):
    def __init__(self, musdb18_root, fft_size, hop_size=None, window_fn='hann', normalize=False, sr=44100, sources=__sources__, target=None):
        super().__init__(musdb18_root, sr=sr, sources=sources, target=target)
        
        if hop_size is None:
            hop_size = fft_size // 2
        
        self.fft_size, self.hop_size = fft_size, hop_size
        self.n_bins = fft_size // 2 + 1

        if window_fn:
            self.window = build_window(fft_size, window_fn=window_fn)
        else:
            self.window = None
        
        self.normalize = normalize

    def _is_active(self, input, threshold=1e-5):
        n_dims = input.dim()

        if n_dims > 2:
            input = input.reshape(-1, input.size(-1))

        input = torch.stft(input, n_fft=self.fft_size, hop_length=self.hop_size, window=self.window, normalized=self.normalize, return_complex=True) # (len(sources)*2, n_bins, n_frames)
        power = torch.sum(torch.abs(input)**2, dim=-1) # (len(sources)*2, n_bins, n_frames)
        power = torch.mean(power)

        if power.item() >= threshold:
            return True
        else:
            return False
        
    def __getitem__(self, idx):
        """
        Returns:
            mixture <torch.Tensor>: Complex tensor with shape (1, 2, n_bins, n_frames)  if `target` is list, otherwise (2, n_bins, n_frames) 
            target <torch.Tensor>: Complex tensor with shape (len(target), 2, n_bins, n_frames) if `target` is list, otherwise (2, n_bins, n_frames)
            latent
            T (), <int>: Number of samples in time-domain
            title <str>: Title of song
        """
        mixture, target, latent, title, source, scale = super().__getitem__(idx)
        
        n_dims = mixture.dim()
        T = mixture.size(-1)

        if n_dims > 2:
            mixture_channels = mixture.size()[:-1]
            target_channels = target.size()[:-1]
            mixture = mixture.reshape(-1, mixture.size(-1))
            target = target.reshape(-1, target.size(-1))

        mixture = torch.stft(mixture, n_fft=self.fft_size, hop_length=self.hop_size, window=self.window, normalized=self.normalize, return_complex=True) # (1, 2, n_bins, n_frames) or (2, n_bins, n_frames)
        target = torch.stft(target, n_fft=self.fft_size, hop_length=self.hop_size, window=self.window, normalized=self.normalize, return_complex=True) # (len(sources), 2, n_bins, n_frames) or (2, n_bins, n_frames)
        
        if n_dims > 2:
            mixture = mixture.reshape(*mixture_channels, *mixture.size()[-2:])
            target = target.reshape(*target_channels, *target.size()[-2:])

        return mixture, target, latent, T, title, source, scale

class SpectrogramTrainDataset(SpectrogramDataset):
    def __init__(self, musdb18_root, fft_size, hop_size=None, window_fn='hann', normalize=False, sr=44100, patch_samples=4*SAMPLE_RATE_MUSDB18, overlap=None, sources=__sources__, target=None, threshold=THRESHOLD_POWER):
        super().__init__(musdb18_root, fft_size=fft_size, hop_size=hop_size, window_fn=window_fn, normalize=normalize, sr=sr, sources=sources, target=target)
        
        train_txt_path = os.path.join(musdb18_root, 'train.txt')

        with open(train_txt_path, 'r') as f:
            names = [line.strip() for line in f]
        
        if overlap is None:
            overlap = patch_samples // 2
        
        self.samples_per_epoch = None

        for songID, name in enumerate(names):
            mixture_path = os.path.join(musdb18_root, 'train', name, "mixture.wav")
            audio_info = torchaudio.info(mixture_path)
            sr = audio_info.sample_rate
            track_samples = audio_info.num_frames

            track = {
                'name': name,
                'samples': track_samples,
                'path': {
                    'mixture': mixture_path
                }
            }

            for source in sources:
                track['path'][source] = os.path.join(musdb18_root, 'train', name, "{}.wav".format(source))
            
            self.tracks.append(track)

            for start in range(0, track_samples, patch_samples - overlap):
                if start + patch_samples >= track_samples:
                    break
                data = {
                    'songID': songID,
                    'start': start,
                    'samples': patch_samples,
                }
                self.json_data.append(data)

    def __getitem__(self, idx):
        """
        Returns:
            mixture <torch.Tensor>: Complex tensor with shape (1, 2, n_bins, n_frames)  if `target` is list, otherwise (2, n_bins, n_frames) 
            target <torch.Tensor>: Complex tensor with shape (len(target), 2, n_bins, n_frames) if `target` is list, otherwise (2, n_bins, n_frames)
        """
        mixture, target, latent, _, _, _, _ = super().__getitem__(idx)

        return mixture, target, latent

class SpectrogramEvalDataset(SpectrogramDataset):
    def __init__(self, musdb18_root, fft_size, hop_size=None, window_fn='hann', normalize=False, sr=44100, patch_size=256, max_samples=10*SAMPLE_RATE_MUSDB18, sources=__sources__, target=None, threshold=THRESHOLD_POWER):
        super().__init__(musdb18_root, fft_size=fft_size, hop_size=hop_size, window_fn=window_fn, normalize=normalize, sr=sr, sources=sources, target=target)
        
        valid_txt_path = os.path.join(musdb18_root, 'validation.txt')
        
        with open(valid_txt_path, 'r') as f:
            names = [line.strip() for line in f]

        self.patch_size = patch_size
        self.max_samples = max_samples

        self.tracks = []
        self.json_data = []

        for songID, name in enumerate(names):
            mixture_path = os.path.join(musdb18_root, 'train', name, "mixture.wav")
            audio_info = torchaudio.info(mixture_path)
            sr = audio_info.sample_rate
            track_samples = audio_info.num_frames
            samples = min(self.max_samples, track_samples)

            track = {
                'name': name,
                'samples': track_samples,
                'path': {
                    'mixture': mixture_path
                }
            }

            for source in sources:
                track['path'][source] = os.path.join(musdb18_root, 'train', name, "{}.wav".format(source))
            
            song_data = {
                'songID': songID,
                'start': 0,
                'samples': samples
            }
            
            self.tracks.append(track)
            self.json_data.append(song_data) # len(self.json_data) determines # of samples in dataset
    
    def __getitem__(self, idx):
        """
        Returns:
            mixture <torch.Tensor>: Complex tensor with shape (1, 2, n_bins, n_frames)  if `target` is list, otherwise (2, n_bins, n_frames) 
            target <torch.Tensor>: Complex tensor with shape (len(target), 2, n_bins, n_frames) if `target` is list, otherwise (2, n_bins, n_frames)
        """
        data = self.json_data[idx]

        songID = data['songID']
        track = self.mus.tracks[songID]
        track.chunk_start = data['start']
        track.chunk_duration = data['duration']

        sources = []
        target = []
        latent = np.zeros((len(self.sources), len(self.sources)))
        scales = []
        source_names = self.sources.copy()

        for source_idx, source_name in enumerate(self.sources):
            source = track.targets[source_name].audio.transpose(1, 0)[np.newaxis]
            sources.append(source)
            scale = random.uniform(0.5, 1) # 1 doesn't work.
            latent[source_idx, source_idx] = scale
            target.append(scale * source)
            scales.append(scale)
        
        sources = np.concatenate(sources, axis=0)
        target = np.concatenate(target, axis=0)
        mixture = sources.sum(axis=0, keepdims=True)

        mixture = torch.Tensor(mixture).float()
        target = torch.Tensor(target).float()
        latent = torch.Tensor(latent).float()
        scales = torch.Tensor(scales).float()
        
        n_dims = mixture.dim()

        if n_dims > 2:
            mixture_channels = mixture.size()[:-1]
            target_channels = target.size()[:-1]
            mixture = mixture.reshape(-1, mixture.size(-1))
            target = target.reshape(-1, target.size(-1))

        mixture = torch.stft(mixture, n_fft=self.fft_size, hop_length=self.hop_size, window=self.window, normalized=self.normalize, return_complex=True) # (1, 2, n_bins, n_frames) or (2, n_bins, n_frames)
        target = torch.stft(target, n_fft=self.fft_size, hop_length=self.hop_size, window=self.window, normalized=self.normalize, return_complex=True) # (len(sources), 2, n_bins, n_frames) or (2, n_bins, n_frames)
        
        if n_dims > 2:
            mixture = mixture.reshape(*mixture_channels, *mixture.size()[-2:])
            target = target.reshape(*target_channels, *target.size()[-2:])

        return mixture, target, latent, source_names, scales

"""
Data loader
"""
class EvalDataLoader(torch.utils.data.DataLoader):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        assert self.batch_size == 1, "batch_size is expected 1, but given {}".format(self.batch_size)

        self.collate_fn = eval_collate_fn

def eval_collate_fn(batch):
    mixture, target, latent, source_names, scale = batch[0]
    
    return mixture, target, latent, source_names, scale

def _test_train_dataset():
    torch.manual_seed(111)
    
    musdb18_root = "../../../../../db/musdb18"

    dataset = SpectrogramTrainDataset(musdb18_root, fft_size=2048, hop_size=512, sr=8000, duration=4, target='vocals')
    
    for mixture, sources in dataset:
        print(mixture.size(), sources.size())
        break

    dataset.save_as_json('data/tmp.json')

    dataset = SpectrogramTrainDataset.from_json(musdb18_root, 'data/tmp.json', fft_size=2048, hop_size=512, sr=44100, target='vocals')
    for mixture, sources in dataset:
        print(mixture.size(), sources.size())
        break

if __name__ == '__main__':
    _test_train_dataset()