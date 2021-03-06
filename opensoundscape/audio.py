#!/usr/bin/env python3
""" audio.py: Utilities for dealing with audio files
"""

import pathlib
import io
import librosa
import soundfile
import numpy as np


class OpsoLoadAudioInputError(Exception):
    """ Custom exception indicating we can't load input
    """

    pass


class OpsoLoadAudioInputTooLong(Exception):
    """ Custom exception indicating length of audio is too long
    """

    pass


class Audio:
    """ Immutable container for audio samples
    """

    __slots__ = ("samples", "sample_rate")

    # note: changing default sample rate from 22050 to 32000
    def __init__(
        self, audio, sample_rate=22050, max_duration=None, resample_type="kaiser_fast"
    ):
        """ Load audio in various formats and generate a spectrogram

        Deal with the various possible input types to load an audio
        file and generate a spectrogram

        Args:
            audio: string, pathlib, samples, or bytesio object
            sample_rate: the target sample rate (default: 32000 Hz)
            max_duration: the maximum length of an input file,
                          None is no maximum (default: None)
            resample_type: method used to resample_type (default: kaiser_fast)

        Returns:
            Audio: class, attributes samples and sample_rate
        """

        path = None
        from_samples = False
        if audio.__class__ == str or audio.__class__ == np.str_:
            # Simply load the audio into a pathlib.Path object
            path = pathlib.Path(audio)
        elif issubclass(audio.__class__, pathlib.PurePath):
            # We already have a pathlib object
            path = audio
        elif issubclass(audio.__class__, io.BufferedIOBase):
            # We have a BytesIO object
            print("BytesIO object")
            path = None
        elif audio.__class__ == np.ndarray:  # recieve samples, provide sample rate!
            from_samples = True
        else:
            raise OpsoLoadAudioInputError(
                f"Error: can't load files of class {audio.__class__}"
            )

        if path:
            if not path.is_file():
                raise FileNotFoundError(f"Error: The file {path} doesn't exist?")
            if (
                max_duration != None
                and librosa.get_duration(filename=path.as_posix()) > max_duration
            ):
                raise OpsoLoadAudioInputTooLong(
                    f"Error: The file {path} is longer than {max_duration} seconds"
                )

            samples, _ = librosa.load(
                str(path.resolve()), sr=sample_rate, res_type=resample_type, mono=True
            )

        elif from_samples:
            samples = audio

        else:
            input_samples, input_sample_rate = soundfile.read(audio)
            samples = librosa.resample(
                input_samples, input_sample_rate, sample_rate, res_type=resample_type
            )
            if samples.ndim > 1:
                samples = librosa.to_mono(samples)

        super(Audio, self).__setattr__("samples", samples)
        super(Audio, self).__setattr__("sample_rate", sample_rate)

    def __setattr__(self, name, value):
        raise AttributeError(
            f"Audio is an immutable container. Tried to set {name} with {value}"
        )

    def __repr__(self):
        return f"<Audio(samples={self.samples.shape}, sample_rate={self.sample_rate})>"

    def trim(self, start_time, end_time):
        """ trim Audio object in time
        
        Args:
            start_time: time in seconds for start of extracted clip
            end_time: time in seconds for end of extracted clip
        Returns:
            a new Audio object containing samples from start_time to end_time
        """
        start_sample = int(start_time * self.sample_rate)
        end_sample = int(end_time * self.sample_rate)  # exclusive
        samples_trimmed = self.samples[start_sample:end_sample]
        return Audio(samples_trimmed, self.sample_rate)

    def bandpass(self, low_f, high_f, order=9):
        """ bandpass audio signal frequencies
        
        uses a phase-preserving algorithm (scipy.signal's butter and solfiltfilt)
        
        Args:
            low_f: low frequency cutoff (-3 dB)  in Hz of bandpass filter
            high_f: high frequency cutoff (-3 dB)  in Hz of bandpass filter
            order: butterworth filter order (integer) ~= steepness of cutoff
            
        """
        from opensoundscape.audio_tools import bandpass_filter

        if low_f <= 0:
            raise ValueError("low_f must be greater than zero")

        if high_f >= self.sample_rate / 2:
            raise ValueError("high_f must be less than sample_rate/2")

        filtered_samples = bandpass_filter(
            self.samples, low_f, high_f, self.sample_rate, order=9
        )
        return Audio(filtered_samples, self.sample_rate)

    # can act on an audio file and be moved into Audio class
    def spectrum(self):
        """create frequency spectrum from an Audio object using fft
        
        Args:
            self
            
        Returns: 
            fft, frequencies
        """
        from scipy.fftpack import fft
        from scipy.fft import fftfreq

        # Compute the fft (fast fourier transform) of the selected clip
        N = len(self.samples)
        T = 1 / self.sample_rate
        fft = fft(self.samples)
        freq = fftfreq(N, d=T)  # the frequencies corresponding to fft bins

        # remove negative frequencies and scale magnitude by 2.0/N:
        fft = 2.0 / N * fft[0 : int(N / 2)]
        frequencies = freq[0 : int(N / 2)]
        fft = np.abs(fft)

        return fft, frequencies

    def save(self, path):
        """save Audio to .wav file using scipy.io.wavfile
        
        Args:
            self
            path: destination for wav file """

        if path.split(".")[-1] != "wav":
            raise ValueError("file extension must be .wav")

        from scipy.io.wavfile import write as write_wav

        write_wav(path, self.sample_rate, self.samples)
