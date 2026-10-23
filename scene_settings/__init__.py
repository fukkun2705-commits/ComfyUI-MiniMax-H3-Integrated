"""Scene JSON loader for existing MiniMax H3 R2V workflow; one node per clip."""
import json
import os
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps
import torch
import subprocess
import shutil
import wave
import folder_paths


def _safe_input_file(value, purpose):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{purpose}: file name must be a nonempty string')
    root = Path(folder_paths.get_input_directory()).resolve()
    candidate = (root / value).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError(f'{purpose}: path must stay within ComfyUI input directory')
    if not candidate.is_file():
        raise FileNotFoundError(f'{purpose}: missing file under ComfyUI/input/: {value}')
    return candidate


def _load_image(name):
    path = _safe_input_file(name, 'reference image')
    with Image.open(path) as image:
        im = ImageOps.exif_transpose(image).convert('RGB')
        arr = np.asarray(im, dtype=np.float32) / 255.0
    return torch.from_numpy(arr).unsqueeze(0)


def _get_clip(scene_filename, clip_index):
    path = _safe_input_file(scene_filename, 'scene JSON')
    with path.open('r', encoding='utf-8-sig') as handle:
        data = json.load(handle)
    if data.get('version') != 1:
        raise ValueError('Scene JSON version must be 1')
    mode = data.get('generation_mode', 'REF2VA')
    if mode not in ('REF2VA', 'T2VA', 'I2VA', 'FLF2VA'):
        raise ValueError('generation_mode must be REF2VA, T2VA, I2VA or FLF2VA')
    clips = data.get('clips')
    if not isinstance(clips, list):
        raise ValueError('Scene JSON clips must be an array')
    matches = [x for x in clips if isinstance(x, dict) and x.get('clip') == clip_index]
    if len(matches) != 1:
        raise ValueError(f'Clip {clip_index} requires exactly one entry')
    clip = matches[0]
    if clip.get('enabled') is not True:
        # Disabled clips still need a harmless duration output for the existing Part math.
        # Do not access images or require an active prompt for bypassed clips.
        return '', [], 2.0, [], []
    prompt = clip.get('prompt')
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError(f'Clip {clip_index}: prompt is missing')
    duration = clip.get('duration')
    if isinstance(duration, bool) or not isinstance(duration, (int,float)) or not 0 < float(duration) <= 15:
        raise ValueError(f'Clip {clip_index}: duration must be in (0, 15] seconds')
    references = clip.get('references')
    if not isinstance(references, list):
        raise ValueError(f'Clip {clip_index}: references must be an array')
    if (mode == 'REF2VA' and not 1 <= len(references) <= 9) or (mode == 'T2VA' and references) or (mode == 'FLF2VA' and len(references) != 2) or (mode == 'I2VA' and len(references) != 1):
        raise ValueError(f'Clip {clip_index}: {mode} requires REF2VA 1-9 / T2VA 0 / I2VA 1 / FLF2VA 2 images')
    if mode != 'REF2VA' and (clip.get('ref_audios') or clip.get('ref_videos')):
        raise ValueError(f'Clip {clip_index}: audio/video reference assets are only available in REF2VA mode')
    audios = clip.get('ref_audios', [])
    videos = clip.get('ref_videos', [])
    if not isinstance(audios,list) or len(audios)>3 or not isinstance(videos,list) or len(videos)>3:
        raise ValueError(f'Clip {clip_index}: max 3 reference audios and 3 videos')
    return prompt, references, float(duration), audios, videos


def _load_audio(name):
    """Use ComfyUI's own PyAV audio decoder (same as its built-in Load Audio)."""
    path = _safe_input_file(name, 'reference audio')
    try:
        from comfy_extras.nodes_audio import load as comfy_load_audio
        waveform, sr = comfy_load_audio(str(path))
    except Exception as exc:
        raise RuntimeError(f'Failed to decode reference audio {name!r} via ComfyUI Load Audio: {exc}') from exc
    return {'waveform': waveform.unsqueeze(0).float(), 'sample_rate': int(sr)}


def _load_video(name):
    """Reference video as an RGB IMAGE batch, normalized to 24 fps."""
    path = _safe_input_file(name, 'reference video')
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError('Reference video requires opencv-python (cv2) in ComfyUI venv') from exc
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError(f'Cannot open reference video: {name}')
    source_fps = capture.get(cv2.CAP_PROP_FPS) or 24.0
    if not (1 <= source_fps <= 240):
        source_fps = 24.0
    frames=[]
    idx=0; next_t=0.0; max_frames=360
    try:
        while len(frames)<max_frames:
            ok, frame = capture.read()
            if not ok:break
            t=idx/source_fps
            idx+=1
            if t+1e-6<next_t:continue
            frames.append(torch.from_numpy(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).copy()).float().div_(255.0))
            next_t=len(frames)/24.0
    finally:
        capture.release()
    if len(frames)<5:
        raise ValueError(f'Reference video requires at least 5 frames: {name}')
    return torch.stack(frames)

class H3SceneClipLoader:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'scene_json': ('STRING', {'default': 'H3_Scene_Settings_Part1_SAMPLE.json'}),
            'clip_index': ('INT', {'default':1, 'min':1,'max':7}),
        }}

    RETURN_TYPES = ('STRING','IMAGE','IMAGE','IMAGE','FLOAT','IMAGE','IMAGE','AUDIO','AUDIO','IMAGE','IMAGE','IMAGE','IMAGE','IMAGE','IMAGE','IMAGE','AUDIO')
    RETURN_NAMES = ('prompt','ref_image_0','ref_image_1','ref_image_2','duration','ref_image_3','ref_image_4','ref_audio_0','ref_audio_1','ref_video_0','ref_image_5','ref_image_6','ref_image_7','ref_image_8','ref_video_1','ref_video_2','ref_audio_2')
    FUNCTION = 'load'
    CATEGORY = 'MiniMax H3/Scene Settings'

    @classmethod
    def IS_CHANGED(cls, scene_json, clip_index):
        # Cache invalidation for both JSON and the referenced image files.
        import hashlib
        h = hashlib.sha256()
        try:
            prompt, refs, duration, audios, videos = _get_clip(scene_json, clip_index)
            files = [_safe_input_file(scene_json,'scene JSON')] + [_safe_input_file(x,'reference image') for x in refs] + [_safe_input_file(x,'reference audio') for x in audios] + [_safe_input_file(x,'reference video') for x in videos]
            for p in files:
                h.update(str(p).encode('utf-8'))
                # file contents: detects edits even if timestamps are preserved
                with p.open('rb') as f:
                    for chunk in iter(lambda:f.read(1024*1024),b''):
                        h.update(chunk)
            h.update(str(clip_index).encode())
            return h.hexdigest()
        except Exception as exc:
            return f'INVALID:{type(exc).__name__}:{exc}'

    def load(self, scene_json, clip_index):
        prompt, refs, duration, audios, videos = _get_clip(scene_json, clip_index)
        if not refs:
            # T2VA has no reference image: these placeholders MUST NOT be connected
            # to a ReferenceToVideo conditioning node. The WF mode branch must bypass it.
            blank = torch.zeros((1, 64, 64, 3), dtype=torch.float32)
            return (prompt, blank, blank, blank, duration, None, None, None, None, None, None, None, None, None, None, None, None)
        images = [_load_image(x) for x in refs]
        # Keep the original 3-IMAGE output contract without requiring a third file.
        # When only two reference images exist, reuse image 2 in slot 3.
        while len(images) < 3:
            images.append(images[-1])
        additional = [_load_image(x) for x in refs[3:9]]
        while len(additional)<6:
            additional.append(None)
        audio_objs = [_load_audio(x) for x in audios]
        while len(audio_objs)<3:
            audio_objs.append(None)
        video_objs = [_load_video(v) for v in videos]
        while len(video_objs)<3:
            video_objs.append(None)
        return (prompt, images[0], images[1], images[2], duration, *additional[:2], *audio_objs[:2], video_objs[0], *additional[2:], *video_objs[1:], audio_objs[2])

NODE_CLASS_MAPPINGS = {'H3SceneClipLoader': H3SceneClipLoader}
NODE_DISPLAY_NAME_MAPPINGS = {'H3SceneClipLoader': 'H3 Scene Clip Loader (JSON)'}
