"""FLF2VA Part2+ output-only seam correction; leave model, latent, trim and audio untouched."""
import json
from pathlib import Path
import torch
import torch.nn.functional as F
import folder_paths

class H3FLFOutputSeam:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "images": ("IMAGE",),
            "previous_part_tail": ("IMAGE",),
            "part_mode_flag": ("INT", {"forceInput": True}),
            "scene_json": ("STRING", {"default": "H3_Scene_Projects/Project01/scenes.json"}),
            "transition_frames": ("INT", {"default": 6, "min": 1, "max": 12, "step": 1}),
            "blend_curve": (["Smoothstep (test)", "Linear (original)"], {"default": "Smoothstep (test)"}),
        }}
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "apply"
    CATEGORY = "MiniMax H3/Part Continuity"

    @staticmethod
    def _read_mode(scene_json):
        root = Path(folder_paths.get_input_directory()).resolve()
        scene_path = (root / scene_json).resolve()
        if not scene_path.is_relative_to(root):
            raise ValueError("H3FLFOutputSeam: scene_json must be within ComfyUI/input")
        with scene_path.open("r", encoding="utf-8-sig") as fp:
            obj = json.load(fp)
        return str(obj.get("generation_mode", "REF2VA")).strip().upper()

    def apply(self, images, previous_part_tail, part_mode_flag, scene_json, transition_frames, blend_curve="Smoothstep (test)"):
        if int(part_mode_flag) == 0:
            print("[H3FLFOutputSeam] Part1 NEW -> unchanged")
            return (images,)
        mode = self._read_mode(scene_json)
        if mode != "FLF2VA":
            print(f"[H3FLFOutputSeam] {mode} -> unchanged")
            return (images,)
        if images.ndim != 4 or previous_part_tail.ndim != 4 or images.shape[0] == 0 or previous_part_tail.shape[0] == 0:
            raise ValueError("H3FLFOutputSeam: expected nonempty image batches [B,H,W,C]")
        if images.shape[-1] != previous_part_tail.shape[-1]:
            raise ValueError("H3FLFOutputSeam: image channel counts must match")
        frames = min(int(transition_frames), int(images.shape[0]))
        target_h, target_w = images.shape[1:3]
        last = previous_part_tail[-1:].to(device=images.device, dtype=images.dtype)
        if last.shape[1:3] != (target_h, target_w):
            last = F.interpolate(last.permute(0, 3, 1, 2), size=(target_h, target_w), mode="bicubic", align_corners=False).permute(0, 2, 3, 1).clamp(0, 1)
        out = images.clone()
        for i in range(frames):
            # On first frame weight=1; fade linearly to original frame by the last corrected frame.
            # Smoothstep starts and ends with zero derivative; avoids a hard
            # correction-to-generated-video slope change at the last frame.
            if blend_curve == "Smoothstep (test)" and frames > 1:
                t = i / float(frames - 1)
                strength = 1.0 - (3.0 * t * t - 2.0 * t * t * t)
            else:
                # Exact legacy implementation; selectable as comparison baseline.
                strength = 1.0 - (i / float(frames))
            out[i:i+1] = (strength * last + (1.0-strength) * images[i:i+1]).clamp(0, 1)
        print(f"[H3FLFOutputSeam] FLF2VA CONTINUE: {blend_curve}; replace frame 0; fade over {frames} frames after VSR; output frames={images.shape[0]}")
        return (out,)

NODE_CLASS_MAPPINGS = {"H3FLFOutputSeam": H3FLFOutputSeam}
NODE_DISPLAY_NAME_MAPPINGS = {"H3FLFOutputSeam": "H3 FLF2VA Output Seam (Test)"}
