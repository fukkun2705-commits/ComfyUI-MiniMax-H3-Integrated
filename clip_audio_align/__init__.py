import torch
import torch.nn.functional as F

class H3ClipJoinAudioAlign:
    """Synchronize concatenated audio to the joined video at each clip boundary.

    Restricted to within 1.5 video frames per join: bigger discrepancies are
    treated as a wiring or generation error rather than silently corrected.
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"images": ("IMAGE",), "audio": ("AUDIO",)}}

    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("audio",)
    FUNCTION = "align"
    CATEGORY = "H3/Part Continuity"

    def align(self, images, audio):
        fps = 24.0
        frames = int(images.shape[0])
        sr = int(audio["sample_rate"])
        samples = audio["waveform"]
        if not torch.is_tensor(samples) or samples.ndim != 3:
            raise ValueError("Clip Join Audio Align: expected AUDIO waveform [B,C,S].")
        target = round(frames * sr / fps)
        have = int(samples.shape[-1])
        difference = abs(target - have)
        max_per_join = round(1.5 * sr / fps)
        if difference > max_per_join:
            raise ValueError(f"Clip Join Audio Align: {difference/sr*1000:.2f}ms difference exceeds 1.5-frame per-join safety limit (frames={frames}, samples={have}, sr={sr}); check join wiring.")
        if target <= 0 or have <= 0:
            raise ValueError("Clip Join Audio Align: empty audio or video.")
        if difference:
            # Resample slightly rather than append silence or discard audible data.
            updated = F.interpolate(samples.float(),size=target,mode="linear",align_corners=False).to(samples.dtype)
            print(f"[H3ClipJoinAudioAlign] Joined {frames}f @24fps: audio {have} -> {target} samples ({(target-have)/sr*1000:+.2f}ms at this boundary)")
        else:
            updated=samples
        result=dict(audio)
        result["waveform"]=updated
        return (result,)

NODE_CLASS_MAPPINGS={"H3ClipJoinAudioAlign":H3ClipJoinAudioAlign}
NODE_DISPLAY_NAME_MAPPINGS={"H3ClipJoinAudioAlign":"H3 Clip Join — Audio Frame Align"}
