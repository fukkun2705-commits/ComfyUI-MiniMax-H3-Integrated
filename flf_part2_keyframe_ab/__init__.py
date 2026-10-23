"""FLF2VA Part2 diagnostic A/B: retain native Motion Context while optionally removing a duplicate start-image keyframe."""
import json
from pathlib import Path
import folder_paths

class H3FLFPart2StartKeyframeAB:
    OPTIONS=('A: Original (safe)','B: History + End (test)','C: Start + History (test)','D: History Only (test)')
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{
            'mode_flag':('INT',{'default':0,'min':0,'max':1}),
            'scene_json':('STRING',{'default':'H3_Scene_Projects/Project01/scenes.json'}),
            'part2_keyframe_mode':(list(cls.OPTIONS),{'default':cls.OPTIONS[0]}),
            'fresh_conditioning':('CONDITIONING',{'lazy':True}),
            'continue_conditioning':('CONDITIONING',{'lazy':True}),
        }}
    RETURN_TYPES=('CONDITIONING',)
    RETURN_NAMES=('conditioning',)
    FUNCTION='run'
    CATEGORY='MiniMax H3/Part Continuity'
    @classmethod
    def IS_CHANGED(cls,**kwargs):return float('nan')

    @staticmethod
    def get_scene_mode(scene_json):
        root=Path(folder_paths.get_input_directory()).resolve()
        path=(root/scene_json).resolve()
        if not path.is_relative_to(root):raise ValueError('Scene JSON must be inside input directory')
        with path.open('r',encoding='utf-8-sig') as f:
            return str(json.load(f).get('generation_mode','')).strip().upper()

    def check_lazy_status(self,mode_flag,scene_json,part2_keyframe_mode,fresh_conditioning=None,continue_conditioning=None):
        if int(mode_flag)==0:
            return ['fresh_conditioning'] if fresh_conditioning is None else []
        return ['continue_conditioning'] if continue_conditioning is None else []

    def run(self,mode_flag,scene_json,part2_keyframe_mode,fresh_conditioning=None,continue_conditioning=None):
        if int(mode_flag)==0:
            if fresh_conditioning is None:raise RuntimeError('Part1 conditioning missing')
            print('[H3FLFPart2StartKeyframeAB] NEW: original FLF conditioning; no previous latent needed')
            return (fresh_conditioning,)
        if continue_conditioning is None:raise RuntimeError('Part2 Motion Context conditioning missing')
        actual_mode=self.get_scene_mode(scene_json)
        print(f'[H3FLFPart2StartKeyframeAB] ROUTE CHECK: mode_flag={int(mode_flag)}; requested={part2_keyframe_mode!r}; scene_generation_mode={actual_mode!r}; scene_json={scene_json!r}')
        if actual_mode!='FLF2VA':
            print(f'[H3FLFPart2StartKeyframeAB] NON-FLF BYPASS: generation_mode={actual_mode!r}; requested {part2_keyframe_mode!r} NOT applied; original Motion Context unchanged')
            return (continue_conditioning,)
        if part2_keyframe_mode==self.OPTIONS[0]:
            print('[H3FLFPart2StartKeyframeAB] CONTINUE FLF2VA A: original Motion Context (unchanged)')
            return (continue_conditioning,)
        if part2_keyframe_mode not in self.OPTIONS[1:]:raise ValueError('Unknown Keyframe A/B/C/D option')
        if not isinstance(continue_conditioning,(list,tuple)) or len(continue_conditioning)!=1:
            raise RuntimeError('B test: expected one Conditioning entry; no fallback modifications')
        entry=continue_conditioning[0]
        if not isinstance(entry,(list,tuple)) or len(entry)!=2 or not isinstance(entry[1],dict):
            raise RuntimeError('B test: unsupported Conditioning representation')
        meta=entry[1]
        keyframes=meta.get('minimax_keyframes')
        if not isinstance(keyframes,list) or len(keyframes)!=3:
            raise RuntimeError('B test requires exactly 3 native keyframes; no mutation performed')
        first,end,history=keyframes
        def position(k):return k.get('resolved_frame_index') if isinstance(k,dict) else None
        def tensor(k):return k.get('latent') if isinstance(k,dict) else None
        if position(first)!=0 or position(end) is None or position(end)<=0 or position(history)!=0:
            raise RuntimeError('B test: unexpected keyframe time positions')
        first_t,end_t,hist_t=map(tensor,keyframes)
        if any(t is None or not hasattr(t,'shape') for t in (first_t,end_t,hist_t)):
            raise RuntimeError('B test: expected tensor keyframes')
        if first_t.ndim!=5 or first_t.shape[2]!=1 or end_t.shape[2]!=1 or hist_t.ndim!=5 or hist_t.shape[2]<2:
            raise RuntimeError('B test: unexpected keyframe tensor shapes')
        if 'audio_latent' not in history:
            raise RuntimeError('B test: missing audio history; refusing to alter Motion Context')
        # Copy only the metadata container; neither original keyframes nor their tensors are mutated.
        altered_meta=dict(meta)
        if part2_keyframe_mode==self.OPTIONS[1]:
            altered_meta['minimax_keyframes']=[end,history]
            print('[H3FLFPart2StartKeyframeAB] CONTINUE FLF2VA B: remove start-image only; preserve end + 22-frame history; original unmodified')
        elif part2_keyframe_mode==self.OPTIONS[2]:
            altered_meta['minimax_keyframes']=[first,history]
            print('[H3FLFPart2StartKeyframeAB] CONTINUE FLF2VA C: remove end-image only; preserve start + native 22-frame AV history; original unmodified')
        elif part2_keyframe_mode==self.OPTIONS[3]:
            altered_meta['minimax_keyframes']=[history]
            print('[H3FLFPart2StartKeyframeAB] CONTINUE FLF2VA D: remove BOTH start/end image keyframes; preserve only native 22-frame AV Motion Context; original unmodified')
        else:
            raise ValueError('Unknown Keyframe option; original not modified')
        altered_entry=[entry[0],altered_meta]
        return ([altered_entry],)

NODE_CLASS_MAPPINGS={'H3FLFPart2StartKeyframeAB':H3FLFPart2StartKeyframeAB}
NODE_DISPLAY_NAME_MAPPINGS={'H3FLFPart2StartKeyframeAB':'H3 FLF Part2 Start-Keyframe A/B TEST'}
