"""Controlled FLF2VA Part2 conditioning A/B experiment. Not an automatic seam fix."""
import json
from pathlib import Path
import folder_paths

class H3FLFContinueABGate:
    MODES = ["A: Motion Context (current)", "B: FLF2VA First+Last (test)"]
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "mode_flag": ("INT", {"default": 0, "min": 0, "max": 1}),
            "scene_json": ("STRING", {"default": "H3_Scene_Projects/Project01/scenes.json"}),
            "flf_part2_conditioning": (cls.MODES, {"default": cls.MODES[0]}),
            "fresh_conditioning": ("CONDITIONING", {"lazy": True}),
            "continue_conditioning": ("CONDITIONING", {"lazy": True}),
        }}
    RETURN_TYPES = ("CONDITIONING",)
    RETURN_NAMES = ("conditioning",)
    FUNCTION = "run"
    CATEGORY = "MiniMax H3/Part Continuity"
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float('nan')
    @staticmethod
    def _scene_mode(scene_json):
        root=Path(folder_paths.get_input_directory()).resolve()
        path=(root / scene_json).resolve()
        if not path.is_relative_to(root):
            raise ValueError("H3FLFContinueABGate: scene_json must be within ComfyUI/input")
        with path.open('r', encoding='utf-8-sig') as f:
            mode=str(json.load(f).get('generation_mode','REF2VA')).strip().upper()
        return mode
    def _source(self, mode_flag, scene_json, flf_part2_conditioning):
        if int(mode_flag) == 0:
            return 'fresh_conditioning'
        if self._scene_mode(scene_json)=='FLF2VA' and flf_part2_conditioning==self.MODES[1]:
            return 'fresh_conditioning'
        return 'continue_conditioning'
    def check_lazy_status(self,mode_flag,scene_json,flf_part2_conditioning,fresh_conditioning=None,continue_conditioning=None):
        source=self._source(mode_flag,scene_json,flf_part2_conditioning)
        selected=fresh_conditioning if source=='fresh_conditioning' else continue_conditioning
        return [source] if selected is None else []
    def run(self,mode_flag,scene_json,flf_part2_conditioning,fresh_conditioning=None,continue_conditioning=None):
        source=self._source(mode_flag,scene_json,flf_part2_conditioning)
        selected=fresh_conditioning if source=='fresh_conditioning' else continue_conditioning
        if selected is None:
            raise ValueError('H3FLFContinueABGate: selected conditioning is missing')
        print('[H3FLFContinueABGate] '+('NEW: original conditioning' if int(mode_flag)==0 else ('CONTINUE: FLF2VA first+last A/B test, Motion Context conditioning bypassed' if source=='fresh_conditioning' else 'CONTINUE: original Motion Context conditioning')))
        return (selected,)

NODE_CLASS_MAPPINGS={'H3FLFContinueABGate':H3FLFContinueABGate}
NODE_DISPLAY_NAME_MAPPINGS={'H3FLFContinueABGate':'H3 FLF2VA CONTINUE Conditioning A/B TEST'}
