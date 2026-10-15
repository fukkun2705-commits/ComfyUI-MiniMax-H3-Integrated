"""Experimental lightweight audio finishing for ComfyUI AUDIO tensors.

No generative reconstruction: gentle high shelf and peak limiting only.
"""
import math
import torch

class H3LightAudioFinish:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'audio': ('AUDIO',),
            'enabled': ('BOOLEAN', {'default': True}),
            'high_shelf_db': ('FLOAT', {'default': 1.5, 'min': -3.0, 'max': 4.0, 'step': 0.25}),
            'high_shelf_hz': ('FLOAT', {'default': 4000.0, 'min': 1200.0, 'max': 9000.0, 'step': 100.0}),
            'peak_ceiling': ('FLOAT', {'default': 0.98, 'min': 0.85, 'max': 1.0, 'step': 0.01}),
            'mix': ('FLOAT', {'default': 0.85, 'min': 0.0, 'max': 1.0, 'step': 0.05}),
        }}

    RETURN_TYPES = ('AUDIO',)
    RETURN_NAMES = ('audio',)
    FUNCTION = 'process'
    CATEGORY = 'audio/postprocessing'

    @staticmethod
    def _shelf_coeffs(sr, freq, gain_db):
        # RBJ Audio EQ Cookbook, high-shelf biquad with slope S=1.
        A = 10 ** (gain_db / 40)
        w0 = 2 * math.pi * min(freq, sr * 0.45) / sr
        cs, sn = math.cos(w0), math.sin(w0)
        alpha = sn / 2 * math.sqrt(2)
        rt = 2 * math.sqrt(A) * alpha
        b0 = A * ((A + 1) + (A - 1) * cs + rt)
        b1 = -2 * A * ((A - 1) + (A + 1) * cs)
        b2 = A * ((A + 1) + (A - 1) * cs - rt)
        a0 = (A + 1) - (A - 1) * cs + rt
        a1 = 2 * ((A - 1) - (A + 1) * cs)
        a2 = (A + 1) - (A - 1) * cs - rt
        return [b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0]

    def process(self, audio, enabled, high_shelf_db, high_shelf_hz, peak_ceiling, mix):
        if not enabled or mix <= 0:
            return (audio,)
        if not isinstance(audio, dict) or 'waveform' not in audio or 'sample_rate' not in audio:
            raise ValueError('Expected ComfyUI AUDIO with waveform and sample_rate')
        waveform = audio['waveform']
        if waveform.ndim != 3:
            raise ValueError('Expected AUDIO waveform [batch, channels, samples]')
        sr = int(audio['sample_rate'])
        if sr <= 0:
            raise ValueError('Invalid sample_rate')
        # Process on CPU to avoid allocating GPU VRAM for a simple post-process.
        orig_device, orig_dtype = waveform.device, waveform.dtype
        x = waveform.detach().to(device='cpu', dtype=torch.float32)
        y = x.clone()
        if abs(high_shelf_db) > 1e-6 and x.shape[-1] > 12:
            try:
                import numpy as np
                from scipy.signal import sosfilt
            except ImportError as exc:
                raise RuntimeError('scipy and numpy are required for H3 Light Audio Finish') from exc
            sos = np.asarray([self._shelf_coeffs(sr, high_shelf_hz, high_shelf_db)], dtype=np.float64)
            # Forward filter maintains the intended gain (filtfilt would double shelf gain).
            array = x.numpy().astype(np.float64, copy=False)
            filtered = sosfilt(sos, array, axis=-1)
            y = torch.from_numpy(filtered.astype(np.float32, copy=False))
        y = torch.lerp(x, y, float(mix))
        # Soft peak protection applies only above the selected threshold.
        ceiling = min(max(float(peak_ceiling), 0.001), 1.0)
        if ceiling < 1.0:
            magnitude = torch.abs(y)
            excess = torch.clamp(magnitude - ceiling, min=0.0)
            limited = ceiling + (1.0 - ceiling) * torch.tanh(excess / max(1.0 - ceiling, 1e-5))
            y = torch.where(magnitude > ceiling, torch.sign(y) * limited, y)
        else:
            y = torch.clamp(y, -1.0, 1.0)
        result = dict(audio)
        result['waveform'] = y.to(device=orig_device, dtype=orig_dtype)
        return (result,)

NODE_CLASS_MAPPINGS = {'H3LightAudioFinish': H3LightAudioFinish}
NODE_DISPLAY_NAME_MAPPINGS = {'H3LightAudioFinish': 'H3 Light Audio Finish (Experimental)'}
