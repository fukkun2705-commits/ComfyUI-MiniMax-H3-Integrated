"""FLF-only cumulative Part audio join with 4-ms boundary smoothing.
Normal Part audio and model paths are NOT modified.
"""
import os
import json
from pathlib import Path
import subprocess
import shutil
import numpy as np
import torch
import torch.nn.functional as F
import folder_paths

class H3FLFClipOverlapAudioJoin:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "scene_json": ("STRING", {"default":"H3_Scene_Projects/Project01/scenes.json"}),
            "part1_mp4_path": ("STRING", {"default":""}),
            "mode_flag": ("INT", {"default":0,"min":0,"max":1}),
            "joined_images": ("IMAGE",),
            "part2_trimmed_audio": ("AUDIO",),
            "part2_final_images": ("IMAGE",),
        }}
    RETURN_TYPES=("AUDIO",)
    RETURN_NAMES=("joined_audio",)
    FUNCTION="join_audio"
    CATEGORY="MiniMax H3/Part Continuity"
    @staticmethod
    def _scene_mode(scene_json):
        root=Path(folder_paths.get_input_directory()).resolve()
        p=(root / str(scene_json)).resolve()
        if not p.is_relative_to(root):
            raise ValueError("Scene JSON must be inside ComfyUI input folder")
        return str(json.loads(p.read_text(encoding="utf-8-sig")).get("generation_mode", "")).upper()
    @staticmethod
    def _decode_part1(path, sr, channels):
        # Prefer PyAV (ComfyUI video backend). Fallback to ffmpeg executable if available.
        try:
            import av
            chunks=[]
            layout="stereo" if channels == 2 else "mono"
            with av.open(path) as container:
                stream=next((s for s in container.streams if s.type=="audio"),None)
                if stream is None:
                    raise ValueError("Part1 MP4 has no audio stream")
                resampler=av.AudioResampler(format="fltp",layout=layout,rate=sr)
                for frame in container.decode(stream):
                    for r in resampler.resample(frame):
                        chunks.append(r.to_ndarray())
                for r in resampler.resample(None):
                    chunks.append(r.to_ndarray())
            if not chunks:
                raise ValueError("Part1 MP4 audio could not be decoded")
            arr=np.concatenate(chunks,axis=1)
            if arr.shape[0] != channels:
                raise ValueError("Unexpected decoded Part1 audio channel count")
            return torch.from_numpy(arr.copy()).unsqueeze(0).float()
        except ImportError:
            ffmpeg=shutil.which("ffmpeg")
            if ffmpeg is None:
                try:
                    import imageio_ffmpeg
                    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
                except ImportError:
                    pass
            if not ffmpeg:
                raise RuntimeError("Cannot decode Part1 MP4 audio: neither PyAV nor FFmpeg available in ComfyUI Python. Install PyAV or FFmpeg.")
            cmd=[ffmpeg,"-v","error","-i",path,"-vn","-f","f32le","-acodec","pcm_f32le","-ar",str(sr),"-ac",str(channels),"pipe:1"]
            proc=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            if proc.returncode != 0:
                raise RuntimeError("Part1 audio decode failed: "+proc.stderr.decode(errors="replace")[-500:])
            arr=np.frombuffer(proc.stdout,dtype="<f4")
            if not len(arr) or len(arr)%channels:
                raise ValueError("Part1 audio missing or invalid")
            return torch.from_numpy(arr.reshape(-1,channels).T.copy()).unsqueeze(0)
    @classmethod
    def IS_CHANGED(cls,scene_json,part1_mp4_path,**kwargs):
        p=os.path.expandvars(os.path.expanduser(str(part1_mp4_path).strip().strip('"')))
        if not os.path.isabs(p): p=os.path.join(folder_paths.get_output_directory(),p)
        try:
            st=os.stat(p)
            return (st.st_size,st.st_mtime_ns)
        except OSError:
            return float('nan')
    def join_audio(self,scene_json,part1_mp4_path,mode_flag,joined_images,part2_trimmed_audio,part2_final_images):
        if int(mode_flag)!=1 or self._scene_mode(scene_json)!="FLF2VA":
            print("[H3FLFClipOverlapAudioJoin] BYPASS: normal Part audio unchanged")
            return (part2_trimmed_audio,)
        path=os.path.expandvars(os.path.expanduser(str(part1_mp4_path).strip().strip('"')))
        if not os.path.isabs(path):
            path=os.path.join(folder_paths.get_output_directory(),path)
        if not os.path.isfile(path):
            raise FileNotFoundError("Part1 MP4 unavailable: "+path)
        sr=int(part2_trimmed_audio["sample_rate"])
        b=part2_trimmed_audio["waveform"]
        if b.ndim != 3 or b.shape[0]!=1 or sr<=0:
            raise ValueError("Expected AUDIO [1, channels, samples]")
        expected_part2=int(round(int(part2_final_images.shape[0])*sr/24))
        if abs(int(b.shape[-1])-expected_part2) > round(sr/24):
            raise ValueError("Part2 trimmed audio differs from final Part2 video by more than one frame")
        if b.shape[-1]!=expected_part2:
            b=F.interpolate(b.float(),size=expected_part2,mode="linear",align_corners=False).to(b.dtype)
        a=self._decode_part1(path,sr,int(b.shape[1]))
        part1_frames=int(joined_images.shape[0])-int(part2_final_images.shape[0])
        if part1_frames<=0:
            raise ValueError("Joined video does not include Part1 frames")
        expected_part1=round(part1_frames*sr/24)
        if abs(int(a.shape[-1])-expected_part1)>round(sr/24):
            raise ValueError(f"Part1 MP4 audio ({a.shape[-1]} samples) differs from Part1 video ({part1_frames}f) by more than one frame")
        if a.shape[-1]!=expected_part1:
            a=F.interpolate(a.float(),size=expected_part1,mode="linear",align_corners=False)
        # De-click only at the Part boundary. No samples are dropped/inserted,
        # so the 24-fps video/audio alignment is exactly preserved.
        # A gentle 4-ms cosine ramp on each side eliminates an abrupt
        # waveform jump without shifting or overlapping musical timing.
        a=a.to(device=b.device,dtype=b.dtype)
        fade_samples=max(2,round(sr*0.004))
        fade_samples=min(fade_samples,int(a.shape[-1]),int(b.shape[-1]))
        if fade_samples >= 2:
            a=a.clone()
            b=b.clone()
            t=torch.linspace(0.0,1.0,fade_samples,device=b.device,dtype=torch.float32)
            fade_out=(0.5+0.5*torch.cos(torch.pi*t)).to(dtype=b.dtype).view(1,1,-1)
            fade_in=(0.5-0.5*torch.cos(torch.pi*t)).to(dtype=b.dtype).view(1,1,-1)
            a[:,:,-fade_samples:]*=fade_out
            b[:,:,:fade_samples]*=fade_in
        out=torch.cat((a,b),dim=-1)
        needed=round(int(joined_images.shape[0])*sr/24)
        if abs(int(out.shape[-1])-needed)>1:
            raise ValueError("Merged soundtrack is not aligned to merged video")
        if out.shape[-1]!=needed:
            out=F.interpolate(out.float(),size=needed,mode="linear",align_corners=False).to(b.dtype)
        print(f"[H3FLFClipOverlapAudioJoin] boundary de-click: {fade_samples} samples ({fade_samples*1000/sr:.2f}ms) per side, no length change")
        print(f"[H3FLFClipOverlapAudioJoin] audio ready: Part1={part1_frames}f, Part2={part2_final_images.shape[0]}f, joined={joined_images.shape[0]}f @24fps, sr={sr}, samples={needed}; original Part2 output untouched")
        return ({"waveform":out,"sample_rate":sr},)

NODE_CLASS_MAPPINGS={"H3FLFClipOverlapAudioJoin":H3FLFClipOverlapAudioJoin}
NODE_DISPLAY_NAME_MAPPINGS={"H3FLFClipOverlapAudioJoin":"FLF Part Join — Audio + Boundary De-click (4ms x2)"}
