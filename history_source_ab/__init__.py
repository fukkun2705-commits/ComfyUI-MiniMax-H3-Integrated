"""FLF2VA CONTINUE-only lazy selection of previous-Part video history source."""
import json
from pathlib import Path
import folder_paths

class H3FLFHistorySourceAB:
    MODES = ["A: Final MP4 tail (original)", "E: Saved Pass1 latent decoded tail (test)"]
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "scene_json": ("STRING", {"default": "H3_Scene_Projects/Project01/scenes.json"}),
            "mode_flag": ("INT", {"default":0, "min":0, "max":1}),
            "history_source": (cls.MODES, {"default":cls.MODES[0]}),
            "mp4_tail_frames": ("IMAGE", {"lazy":True}),
            "latent_decoded_tail_frames": ("IMAGE", {"lazy":True}),
        }}
    RETURN_TYPES=("IMAGE",)
    RETURN_NAMES=("context_frames",)
    FUNCTION="select"
    CATEGORY="MiniMax H3/Part Continuity"
    @classmethod
    def IS_CHANGED(cls, **kwargs):return float('nan')
    @staticmethod
    def mode(scene_json):
        root=Path(folder_paths.get_input_directory()).resolve()
        path=(root/scene_json).resolve()
        if not path.is_relative_to(root):raise ValueError('H3FLFHistorySourceAB: scene file outside input directory')
        obj=json.loads(path.read_text(encoding='utf-8-sig'))
        return str(obj.get('generation_mode','')).upper()
    def which(self,scene_json,mode_flag,history_source):
        scene_mode=self.mode(scene_json)
        use_latent=(int(mode_flag)==1 and scene_mode=='FLF2VA' and history_source==self.MODES[1])
        return use_latent,scene_mode
    def check_lazy_status(self,scene_json,mode_flag,history_source,mp4_tail_frames=None,latent_decoded_tail_frames=None):
        use_latent,_=self.which(scene_json,mode_flag,history_source)
        if use_latent:return ['latent_decoded_tail_frames'] if latent_decoded_tail_frames is None else []
        return ['mp4_tail_frames'] if mp4_tail_frames is None else []
    def select(self,scene_json,mode_flag,history_source,mp4_tail_frames=None,latent_decoded_tail_frames=None):
        use_latent,scene_mode=self.which(scene_json,mode_flag,history_source)
        frames=latent_decoded_tail_frames if use_latent else mp4_tail_frames
        if frames is None or not hasattr(frames,'shape') or len(frames.shape)!=4 or frames.shape[0]<22:
            raise ValueError('H3FLFHistorySourceAB: expected at least 22 IMAGE frames from selected source')
        if use_latent:
            print('[H3FLFHistorySourceAB] FLF2VA CONTINUE E: decoded saved Pass1 AV latent -> last 22 frames for Motion Context; audio from original saved AV latent; trim unchanged')
        else:
            print(f'[H3FLFHistorySourceAB] ORIGINAL A: MP4 frames for Motion Context (mode={scene_mode}, part={int(mode_flag)}, option={history_source!r})')
        return (frames[-22:].contiguous(),)
NODE_CLASS_MAPPINGS={'H3FLFHistorySourceAB':H3FLFHistorySourceAB}
NODE_DISPLAY_NAME_MAPPINGS={'H3FLFHistorySourceAB':'H3 FLF History Source A/E (CONTINUE only)'}
