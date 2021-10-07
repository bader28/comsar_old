"""comsar/tracks/timbre.py -- TimbreTack implementation
License: BSD-3-Clasuse
Copyright (C) 2020, Michael Blaß, michael.blass@uni-hamburg.de
"""
from dataclasses import dataclass
from timeit import default_timer as timer
from typing import Optional

import numpy as np
import pandas as pd

from apollon.audio import AudioFile
"""from apollon.segment import Segmentation"""

import apollon.segment as aps
from apollon.signal import container, features
from apollon.signal.spectral import StftSegments
from apollon.tools import time_stamp

import comsar
from comsar._tracks.utilities import TrackMeta, TrackParams, TrackResult, TimbreTrackParams


STFT_DEFAULT = container.StftParams(fps=44100, window='hamming', n_fft=None,
                                    n_perseg=2**15, n_overlap=2**14,
                                    extend=True, pad=True)

CORR_DIM_DEFAULT = container.CorrDimParams(delay=14, m_dim=80, n_bins=1000,
                                           scaling_size=10)

CORR_GRAM_DEFAULT = container.CorrGramParams(wlen=2**10, n_delay=2**8, total=True)




class TimbreTrack:
    """Compute timbre track of an audio file.
    """
    def __init__(self,
                 stft_params: Optional[container.StftParams] = None,
                 corr_dim_params: Optional[container.CorrDimParams] = None,
                 corr_gram_params: Optional[container.CorrGramParams] = None) -> None:
        """
        Args:
        """
        self.params = TimbreTrackParams(stft_params or STFT_DEFAULT,
                                        corr_dim_params or CORR_DIM_DEFAULT,
                                        corr_gram_params or CORR_GRAM_DEFAULT)

        self.cutter = aps.Segmentation(self.params.stft.n_perseg,
                                   self.params.stft.n_overlap,
                                   self.params.stft.extend,
                                   self.params.stft.pad)
        self.stft = StftSegments(self.params.stft.fps, self.params.stft.window,
                                 self.params.stft.n_fft)

        self.feature_names = ('Spectral Centroid', 'Spectral Spread',
                              'Spectral Flux', 'Roughness', 'Sharpness',
                              'SPL')

        self.funcs = [features.spectral_centroid,
                      features.spectral_spread,
                      features.spectral_flux,
                      features.roughness_helmholtz,
                      features.sharpness,
                      features.spl]

        self.pace = np.zeros(self.n_features)
        self.verbose = False

    @property
    def n_features(self) -> int:
        """Number of features on track"""
        return len(self.feature_names)

    def extract(self, path) -> pd.DataFrame:
        """Perform extraction.
        """
        snd = AudioFile(path)
        if snd.fps != self.params.stft.fps:
            snd.close()
            raise ValueError('Sample rate of {snd!str} differs from init.')

        segs = self.cutter.transform(snd.data.squeeze())
        sxx = self.stft.transform(segs)

        args = [(sxx.frqs, sxx.power),
                (sxx.frqs, sxx.power),
                (sxx.abs,),
                (sxx.d_frq, sxx.abs, 15000),
                (sxx.frqs, sxx.abs),
                (segs.data,),
                (segs.data,),
                (segs.data,)]

        kwargs = [{}, {}, {}, {}, {}, {}, self.params.corr_dim.to_dict(),
                  self.params.corr_gram.to_dict()]

        out = np.zeros((segs.n_segs, self.n_features))
        for i, (fun, arg, kwarg) in enumerate(zip(self.funcs, args, kwargs)):
            out[:, i] = self._worker(i, fun, arg, kwarg)
        snd.close()

        meta = TrackMeta(comsar.__version__, time_stamp(), snd.file_name)
        out = pd.DataFrame(data=out, columns=self.feature_names)
        return TrackResult(meta, self.params, out)

    def _worker(self, idx, func, args, kwargs) -> np.ndarray:
        print(self.feature_names[idx], end=' ... ')
        pace = timer()
        res = func(*args, **kwargs)
        pace = timer() - pace
        self.pace[idx] = pace
        print(f'{pace:.4} s.')
        return res
