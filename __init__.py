"""MiniMax H3 integrated custom nodes. Existing node class identifiers are preserved."""
from importlib import import_module

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

for _component in ('mode_router', 'scene_settings', 'scene_editor', 'duration', 'clip_audio_align', 'part_control', 'part_video_tail', 'last_latent', 'audio_conform', 'audio_finish', 'pretrim_grid', 'face_latent_control'):
    _module = import_module('.' + _component, __package__)
    for _name, _cls in getattr(_module, 'NODE_CLASS_MAPPINGS', {}).items():
        if _name in NODE_CLASS_MAPPINGS:
            raise RuntimeError('Duplicate MiniMax H3 node type: ' + _name)
        NODE_CLASS_MAPPINGS[_name] = _cls
    NODE_DISPLAY_NAME_MAPPINGS.update(getattr(_module, 'NODE_DISPLAY_NAME_MAPPINGS', {}))
