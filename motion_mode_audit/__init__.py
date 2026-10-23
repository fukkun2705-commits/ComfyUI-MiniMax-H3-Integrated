"""Passive metadata audit: one unchanged Conditioning output, for REF2VA/FLF2VA Part2."""
import json
from pathlib import Path
import folder_paths

class H3MotionContextModeAudit:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'motion_conditioning': ('CONDITIONING',), 'native_conditioning': ('CONDITIONING',), 'scene_json': ('STRING', {'default':'H3_Scene_Projects/Project01/scenes.json'})}}
    RETURN_TYPES = ('CONDITIONING',)
    RETURN_NAMES = ('conditioning',)
    FUNCTION = 'run'
    CATEGORY = 'MiniMax H3/Part Continuity'
    @classmethod
    def IS_CHANGED(cls, **kwargs): return float('nan')

    @staticmethod
    def _details(cond):
        if not isinstance(cond,(tuple,list)) or len(cond)!=1: return {'entry_count':len(cond) if isinstance(cond,(tuple,list)) else None,'error':'unexpected Conditioning entries'}
        entry=cond[0]
        if not isinstance(entry,(tuple,list)) or len(entry)<2 or not isinstance(entry[1],dict): return {'error':'unexpected entry structure'}
        meta=entry[1]; frames=meta.get('minimax_keyframes',[]); out=[]
        for i,k in enumerate(frames):
            if not isinstance(k,dict): out.append({'n':i,'type':str(type(k).__name__)});continue
            tensors={}
            for name in ('latent','audio_latent'):
                v=k.get(name)
                if v is not None and hasattr(v,'shape'): tensors[name]={'shape':list(v.shape),'dtype':str(v.dtype)}
            out.append({'n':i,'frame':k.get('resolved_frame_index'),**tensors})
        return {'text_tokens': list(entry[0].shape) if hasattr(entry[0],'shape') else None,'keyframes':out}

    def run(self, motion_conditioning, native_conditioning, scene_json):
        try:
            root=Path(folder_paths.get_input_directory()).resolve();path=(root/scene_json).resolve()
            if not path.is_relative_to(root): raise ValueError('scene_json is outside input')
            mode=json.loads(path.read_text('utf-8-sig')).get('generation_mode','unknown')
        except Exception as exc:
            mode='unknown';print(f'[H3MotionContextModeAudit] mode read warning: {type(exc).__name__}: {exc}')
        native=self._details(native_conditioning)
        motion=self._details(motion_conditioning)
        print('[H3MotionContextModeAudit] '+json.dumps({'mode':mode,'native':native,'motion':motion},ensure_ascii=False,default=str))
        print('[H3MotionContextModeAudit] PASS THROUGH: unmodified native Motion Context Conditioning')
        return (motion_conditioning,)

NODE_CLASS_MAPPINGS={'H3MotionContextModeAudit':H3MotionContextModeAudit}
NODE_DISPLAY_NAME_MAPPINGS={'H3MotionContextModeAudit':'H3 Motion Context Mode Audit (pass-through)'}
