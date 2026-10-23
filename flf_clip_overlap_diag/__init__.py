"""FLF-only 22-frame Part continuity join for the final output router."""
import os
from pathlib import Path
import cv2
import torch
import numpy as np
import folder_paths
import json

class H3FLFClipOverlapPartJoinDIAG:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "scene_json": ("STRING", {"default": "H3_Scene_Projects/Project01/scenes.json"}),
            "part1_mp4_path": ("STRING", {"default": "", "multiline": False}),
            "mode_flag": ("INT", {"default": 0, "min": 0, "max": 1}),
            "overlap_enabled": ("BOOLEAN", {"default": True}),
            "overlap_frames": ("INT", {"default": 22, "min": 1, "max": 64}),
            "part2_pretrim": ("IMAGE",),
            "part2_final": ("IMAGE",),
        }}
    RETURN_TYPES=("IMAGE",)
    RETURN_NAMES=("comparison_join_frames",)
    FUNCTION="join"
    CATEGORY="MiniMax H3/Part Continuity"
    @classmethod
    def IS_CHANGED(cls, scene_json, part1_mp4_path, **kwargs):
        try:
            path=cls._resolve_video(part1_mp4_path)
            st=os.stat(path)
            return (st.st_size,st.st_mtime_ns,tuple(sorted((k,str(v)) for k,v in kwargs.items() if not isinstance(v,torch.Tensor))))
        except OSError:
            return float('nan')
    @staticmethod
    def _resolve_video(path):
        p=os.path.expanduser(os.path.expandvars(str(path).strip().strip('"')))
        return p if os.path.isabs(p) else os.path.join(folder_paths.get_output_directory(),p)
    @staticmethod
    def _scene_mode(scene_json):
        root=Path(folder_paths.get_input_directory()).resolve()
        path=(root / str(scene_json)).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Scene file outside ComfyUI input directory')
        return str(json.loads(path.read_text(encoding='utf-8-sig')).get('generation_mode','')).upper()
    @classmethod
    def _read_part1(cls,path):
        cap=cv2.VideoCapture(path)
        if not cap.isOpened():raise ValueError('Cannot open Part1 MP4: '+path)
        frames=[]
        while True:
            ok,bgr=cap.read()
            if not ok:break
            frames.append(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB))
        cap.release()
        if not frames:raise ValueError('Part1 MP4 contains no decodable frames: '+path)
        return np.stack(frames)
    def join(self, scene_json, part1_mp4_path, mode_flag, overlap_enabled, overlap_frames, part2_pretrim, part2_final):
        mode=self._scene_mode(scene_json)
        # NEW or REF should never access an old Part1 file. Keep the original Part video unchanged for non-FLF / NEW.
        if int(mode_flag)!=1 or mode!='FLF2VA':
            print(f'[H3FLFClipOverlapPartJoinDIAG] BYPASS: mode={mode}, part={mode_flag}; original output untouched')
            return (part2_final,)
        path=self._resolve_video(part1_mp4_path)
        if not os.path.isfile(path):raise FileNotFoundError('Part1 MP4 not found. Set PART2 INPUT — Load Part1 MP4 Tail.video_path: '+path)
        a=self._read_part1(path)
        n=int(overlap_frames)
        if len(a)<n or len(part2_pretrim)<n:
            raise ValueError(f'Insufficient context: part1={len(a)}, pretrim={len(part2_pretrim)}, overlap={n}')
        # Match destination Part1 resolution, preserving the final Part2's native upscaled image data.
        H,W=a.shape[1:3]
        target=tuple(part2_final.shape[1:3])
        if (H,W)!=target:
            a=np.stack([cv2.resize(frame,(target[1],target[0]),interpolation=cv2.INTER_AREA if W>target[1] else cv2.INTER_CUBIC) for frame in a])
            H,W=target
        p=part2_pretrim[:n].detach().cpu().numpy()
        # Limit resizing of low-res pretrim context strictly to overlap region.
        hist=np.stack([cv2.resize(np.clip(f*255,0,255).astype(np.uint8),(W,H),interpolation=cv2.INTER_CUBIC) for f in p])
        if overlap_enabled:
            for j in range(n):
                t=(j+1)/(n+1)
                t=t*t*(3-2*t)
                a[len(a)-n+j]=np.clip((1-t)*a[len(a)-n+j].astype(np.float32)+t*hist[j].astype(np.float32),0,255).astype(np.uint8)
            label='ON: smoothstep 22-frame overlap'
        else:
            label='OFF: hard Part join'
        prefix=torch.from_numpy(a.copy()).float().div_(255.0)
        final=part2_final.detach().cpu().float()
        joined=torch.cat((prefix,final),dim=0)
        print(f'[H3FLFClipOverlapPartJoinDIAG] {label}; Part1={len(a)}f, Part2 final={len(final)}f, joined={len(joined)}f; source frames unchanged')
        return (joined,)

NODE_CLASS_MAPPINGS={'H3FLFClipOverlapPartJoinDIAG':H3FLFClipOverlapPartJoinDIAG}
NODE_DISPLAY_NAME_MAPPINGS={'H3FLFClipOverlapPartJoinDIAG':'H3 FLF Clip-style Part Overlap (diagnostic ON/OFF)'}
