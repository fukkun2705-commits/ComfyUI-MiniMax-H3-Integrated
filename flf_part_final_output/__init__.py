"""Only FLF2VA CONTINUE receives complete overlapping Part joins at the normal SaveVideo output.
For all other modes and Part1 NEW the original video and audio pass unchanged.
"""
import json
from pathlib import Path
import folder_paths

class H3FLFPartFinalOutputRouter:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "scene_json": ("STRING", {"default":"H3_Scene_Projects/Project01/scenes.json"}),
            "part_mode_flag": ("INT", {"default":0,"min":0,"max":1}),
            "original_images": ("IMAGE",),
            "original_audio": ("AUDIO",),
            "flf_joined_images": ("IMAGE",),
            "flf_joined_audio": ("AUDIO",),
        }}
    RETURN_TYPES=("IMAGE","AUDIO")
    RETURN_NAMES=("output_images","output_audio")
    FUNCTION="route"
    CATEGORY="MiniMax H3/Part Continuity"
    @staticmethod
    def _mode(scene_json):
        root=Path(folder_paths.get_input_directory()).resolve()
        p=(root / str(scene_json)).resolve()
        if not p.is_relative_to(root):
            raise ValueError("Scene JSON must be inside ComfyUI input folder")
        return str(json.loads(p.read_text(encoding="utf-8-sig")).get("generation_mode", "")).upper()
    @classmethod
    def IS_CHANGED(cls,scene_json,**kwargs):
        p=(Path(folder_paths.get_input_directory()).resolve()/str(scene_json)).resolve()
        try: return (p.stat().st_mtime_ns,p.stat().st_size)
        except OSError: return float('nan')
    def route(self,scene_json,part_mode_flag,original_images,original_audio,flf_joined_images,flf_joined_audio):
        mode=self._mode(scene_json)
        if mode=='FLF2VA' and int(part_mode_flag)==1:
            print(f'[H3FLFPartFinalOutputRouter] FLF2VA CONTINUE: joined video/audio -> NORMAL SaveVideo; frames={len(flf_joined_images)}')
            return (flf_joined_images,flf_joined_audio)
        print(f'[H3FLFPartFinalOutputRouter] BYPASS: {mode} part_flag={part_mode_flag}; original video/audio -> NORMAL SaveVideo')
        return (original_images,original_audio)

NODE_CLASS_MAPPINGS={'H3FLFPartFinalOutputRouter':H3FLFPartFinalOutputRouter}
NODE_DISPLAY_NAME_MAPPINGS={'H3FLFPartFinalOutputRouter':'H3 FLF Part Final Output Router'}
