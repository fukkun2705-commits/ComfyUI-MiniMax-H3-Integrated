"""Experimental H3 four-mode router for SceneSettings v1. DO NOT use as production code."""
import json
from pathlib import Path
import folder_paths

MODES = ('REF2VA','T2VA','I2VA','FLF2VA')

def _mode(scene_json):
    root=Path(folder_paths.get_input_directory()).resolve()
    file=(root/scene_json).resolve()
    if not file.is_relative_to(root):
        raise ValueError('Scene JSON must be inside ComfyUI/input/')
    with file.open('r',encoding='utf-8-sig') as f:
        data=json.load(f)
    mode=data.get('generation_mode','REF2VA')
    if mode not in MODES:raise ValueError(f'Unsupported generation_mode {mode!r}')
    return mode

class H3SceneModeAVRouter:
    """Select only one conditioning/latent branch lazily.

    Both outputs are taken from the SAME mode, preventing cross-wired conditions.
    Unselected branches must not execute (ComfyUI lazy input contract).
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'scene_json':('STRING',{'default':'H3_Scene_Projects/Project01/scenes.json'})},
                'optional':{name:(typ,{'lazy':True}) for name,typ in [
                   ('ref_conditioning','CONDITIONING'),('ref_latent','LATENT'),
                   ('t2v_conditioning','CONDITIONING'),('t2v_latent','LATENT'),
                   ('i2v_conditioning','CONDITIONING'),('i2v_latent','LATENT'),
                   ('i2va_conditioning','CONDITIONING'),('i2va_latent','LATENT')]}}
    RETURN_TYPES=('CONDITIONING','LATENT')
    RETURN_NAMES=('conditioning','latent')
    FUNCTION='select'
    CATEGORY='MiniMax H3/Scene Settings'
    @classmethod
    def IS_CHANGED(cls,**kwargs):
        # Important: Editor can rewrite scene JSON with same filename.
        return float('nan')
    def check_lazy_status(self,scene_json,**kwargs):
        mode=_mode(scene_json)
        a={'REF2VA':('ref_conditioning','ref_latent'),
           'T2VA':('t2v_conditioning','t2v_latent'),
           'I2VA':('i2va_conditioning','i2va_latent'),
           'FLF2VA':('i2v_conditioning','i2v_latent')}[mode]
        return [name for name in a if kwargs.get(name) is None]
    def select(self,scene_json,**kwargs):
        mode=_mode(scene_json)
        names={'REF2VA':('ref_conditioning','ref_latent'),
               'T2VA':('t2v_conditioning','t2v_latent'),
               'I2VA':('i2va_conditioning','i2va_latent'),
           'FLF2VA':('i2v_conditioning','i2v_latent')}[mode]
        if any(kwargs.get(name) is None for name in names):
            raise ValueError(f'{mode} branch missing required conditioning/latent: {names}')
        print(f'[H3SceneModeAVRouter] selected {mode} conditioning/latent')
        return tuple(kwargs[name] for name in names)

class H3SceneModeConditioningRouter:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'scene_json':('STRING',{'default':'H3_Scene_Projects/Project01/scenes.json'})},
                'optional':{name:('CONDITIONING',{'lazy':True}) for name in
                            ('ref_conditioning','t2v_conditioning','i2v_conditioning','i2va_conditioning')}}
    RETURN_TYPES=('CONDITIONING',)
    RETURN_NAMES=('conditioning',)
    FUNCTION='select'
    CATEGORY='MiniMax H3/Scene Settings'
    @classmethod
    def IS_CHANGED(cls,**kwargs):return float('nan')
    def check_lazy_status(self,scene_json,**kwargs):
        name={'REF2VA':'ref_conditioning','T2VA':'t2v_conditioning','I2VA':'i2va_conditioning','FLF2VA':'i2v_conditioning'}[_mode(scene_json)]
        return [name] if kwargs.get(name) is None else []
    def select(self,scene_json,**kwargs):
        mode=_mode(scene_json)
        name={'REF2VA':'ref_conditioning','T2VA':'t2v_conditioning','I2VA':'i2va_conditioning','FLF2VA':'i2v_conditioning'}[mode]
        if kwargs.get(name) is None:raise ValueError(f'{mode} branch missing {name}')
        print(f'[H3SceneModeConditioningRouter] Pass2 selected {mode}')
        return (kwargs[name],)

class H3NativeAVLatentCanvas:
    """Derive H3 video canvas directly from the upscaled VIDEO latent (B,C,T,H,W)."""
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'latent':('LATENT',)}}
    RETURN_TYPES=('INT','INT')
    RETURN_NAMES=('width','height')
    FUNCTION='dimensions'
    CATEGORY='MiniMax H3/Scene Settings'
    def dimensions(self,latent):
        samples=latent['samples']
        if samples.ndim!=5:
            raise ValueError(f'H3 canvas expects 5D video latent [B,C,T,H,W], got {tuple(samples.shape)}')
        width,height=int(samples.shape[-1])*16,int(samples.shape[-2])*16
        print(f'[H3NativeAVLatentCanvas] video latent {tuple(samples.shape)} => {width}x{height}')
        return width,height

NODE_CLASS_MAPPINGS={
    'H3SceneModeAVRouter':H3SceneModeAVRouter,
    'H3SceneModeConditioningRouter':H3SceneModeConditioningRouter,
    'H3NativeAVLatentCanvas':H3NativeAVLatentCanvas,
}
NODE_DISPLAY_NAME_MAPPINGS={
    'H3SceneModeAVRouter':'H3 Scene Mode Native AV Router (TEST)',
    'H3SceneModeConditioningRouter':'H3 Scene Mode Pass2 Conditioning Router (TEST)',
    'H3NativeAVLatentCanvas':'H3 Upscaled Latent Actual Canvas (TEST)',
}
