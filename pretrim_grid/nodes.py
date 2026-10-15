"""External Motion Context node is never modified. Guarded H3 audio preparation."""
import torch
import torch.nn.functional as F

class H3PreTrimAudioGridAlign:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "images": ("IMAGE",), "audio": ("AUDIO",), "trim_frames": ("INT", {"default":22,"min":0,"max":100000}),
        }}
    RETURN_TYPES=("AUDIO",)
    RETURN_NAMES=("audio",)
    FUNCTION="align"
    CATEGORY="H3/Audio"
    DESCRIPTION="Align decoded audio within half an H3 40Hz audio cell before the external MotionContextTrim. Never suppresses large mismatches."

    def align(self, images, audio, trim_frames):
        if not torch.is_tensor(images) or images.ndim < 1:
            raise ValueError("H3 PreTrim: invalid image frames")
        waveform=audio["waveform"]
        if not torch.is_tensor(waveform) or waveform.ndim != 3:
            raise ValueError("H3 PreTrim: expected AUDIO waveform [B,C,S]")
        sr=int(audio["sample_rate"])
        total=int(images.shape[0]); trim=int(trim_frames)
        if sr <= 0 or total <= 0 or not 0 <= trim < total:
            raise ValueError(f"H3 PreTrim: invalid frames/trim/sr ({total}, {trim}, {sr})")
        cut=round(trim/24.0*sr)
        target=cut+round((total-trim)/24.0*sr)
        have=int(waveform.shape[-1]); difference=target-have
        # H3 audio is aligned to 40 Hz. Nearest grid quantization is <= half a 25 ms cell.
        max_rounding=round(sr/80.0)
        if abs(difference)>max_rounding:
            raise ValueError(f"H3 PreTrim: {difference} samples exceeds 40Hz half-cell limit {max_rounding}; inspect decoded AV timing instead of masking drift")
        if have <= cut or target <= cut:
            raise ValueError("H3 PreTrim: audio too short for trim")
        if difference:
            # Change only the decoded tail, keeping the first trim segment unchanged.
            # That first segment will be discarded by the external node.
            head=waveform[..., :cut]
            tail=waveform[..., cut:]
            tail_out=F.interpolate(tail.float(),size=target-cut,mode="linear",align_corners=False).to(waveform.dtype)
            fixed=torch.cat([head,tail_out],dim=-1)
            print(f"[H3PreTrimAudioGridAlign] {total}f trim={trim}f: decoded {have} -> {fixed.shape[-1]} samples ({difference:+d}); <= half 40Hz cell")
        else:
            fixed=waveform
        result=dict(audio);result["waveform"]=fixed
        return (result,)

NODE_CLASS_MAPPINGS={"H3PreTrimAudioGridAlign":H3PreTrimAudioGridAlign}
NODE_DISPLAY_NAME_MAPPINGS={"H3PreTrimAudioGridAlign":"H3 PreTrim Audio Grid Align (40Hz)"}
