"""Optional part-continuation input: return the last N decoded MP4 frames.
Independent helper; does not modify third-party H3 Motion Context.
"""
import os
import cv2
import numpy as np
import torch
import folder_paths

class H3PartVideoTail:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'video_path': ('STRING', {'default': '', 'multiline': False}),
            'tail_frames': ('INT', {'default': 22, 'min': 1, 'max': 999}),
        }}

    RETURN_TYPES = ('IMAGE', 'INT')
    RETURN_NAMES = ('context_frames', 'frame_count')
    FUNCTION = 'read'
    CATEGORY = 'H3/Part Continuation'

    @classmethod
    def IS_CHANGED(cls, video_path, tail_frames):
        p = cls._path(video_path)
        try:
            st = os.stat(p)
            return (p, st.st_mtime_ns, st.st_size, tail_frames)
        except OSError:
            return float('nan')

    @staticmethod
    def _path(video_path):
        p = os.path.expandvars(os.path.expanduser(str(video_path).strip().strip('"')))
        if os.path.isabs(p):
            return p
        return os.path.join(folder_paths.get_output_directory(), p)

    def read(self, video_path, tail_frames):
        path = self._path(video_path)
        if not os.path.isfile(path):
            raise FileNotFoundError('H3 Part Video Tail: MP4 not found: ' + path)
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise RuntimeError('H3 Part Video Tail: video cannot be decoded: ' + path)
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if count < int(tail_frames):
            cap.release()
            raise ValueError(f'H3 Part Video Tail: video has {count} frames, needs {tail_frames}')
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, count - int(tail_frames)))
        frames = []
        for _ in range(int(tail_frames)):
            ok, frame = cap.read()
            if not ok:
                break
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        cap.release()
        if len(frames) != int(tail_frames):
            raise RuntimeError(f'H3 Part Video Tail: only read {len(frames)}/{tail_frames} tail frames; check MP4 seek/index')
        return (torch.from_numpy(np.stack(frames).astype(np.float32) / 255.0), count)

NODE_CLASS_MAPPINGS = {'H3PartVideoTail': H3PartVideoTail}
NODE_DISPLAY_NAME_MAPPINGS = {'H3PartVideoTail': 'H3 Part — Load MP4 Tail Frames'}
