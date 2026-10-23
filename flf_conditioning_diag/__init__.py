"""Nonmutating comparison of FLF2VA frame conditioning vs native Motion Context."""
import json
from pathlib import Path
import folder_paths

class H3FLFConditioningStructureDiag:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'mode_flag': ('INT', {'default': 0, 'min': 0, 'max': 1}),
            'scene_json': ('STRING', {'default': 'H3_Scene_Projects/Project01/scenes.json'}),
            'inspect_flfo_conditioning': ('BOOLEAN', {'default': True}),
            'fresh_conditioning': ('CONDITIONING', {'lazy': True}),
            'continue_conditioning': ('CONDITIONING', {'lazy': True}),
        }}
    RETURN_TYPES = ('CONDITIONING',)
    RETURN_NAMES = ('conditioning',)
    FUNCTION='run'
    CATEGORY='MiniMax H3/Part Continuity'
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float('nan')
    def _is_flf(self, scene_json):
        root=Path(folder_paths.get_input_directory()).resolve()
        path=(root / scene_json).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Scene JSON must be inside ComfyUI input')
        with path.open('r',encoding='utf-8-sig') as f:
            return str(json.load(f).get('generation_mode','')).strip().upper()=='FLF2VA'
    def _need_both(self, mode_flag, scene_json, inspect_flfo_conditioning):
        return int(mode_flag)==1 and bool(inspect_flfo_conditioning) and self._is_flf(scene_json)
    def check_lazy_status(self, mode_flag, scene_json, inspect_flfo_conditioning, fresh_conditioning=None, continue_conditioning=None):
        if int(mode_flag)==0:
            return ['fresh_conditioning'] if fresh_conditioning is None else []
        keys=['continue_conditioning']
        if self._need_both(mode_flag,scene_json,inspect_flfo_conditioning):
            keys.append('fresh_conditioning')
        return [key for key in keys if (fresh_conditioning if key=='fresh_conditioning' else continue_conditioning) is None]
    @staticmethod
    def _structure(conditioning):
        result=[]
        if not isinstance(conditioning,(list,tuple)):
            return {'container_type':type(conditioning).__name__}
        for entry in conditioning[:3]:
            if not isinstance(entry,(list,tuple)) or len(entry)<2:
                result.append({'entry_type':type(entry).__name__});continue
            tensor=entry[0]
            meta=entry[1]
            fields={}
            if isinstance(meta,dict):
                for k,v in meta.items():
                    if hasattr(v,'shape'): val={'type':type(v).__name__,'shape':list(v.shape)}
                    elif isinstance(v,(str,bool,int,float,type(None))):val={'type':type(v).__name__,'value':str(v)[:100]}
                    elif isinstance(v,(list,tuple)):val={'type':type(v).__name__,'length':len(v)}
                    elif isinstance(v,dict):val={'type':'dict','keys':[str(q) for q in v.keys()]}
                    else:val={'type':type(v).__name__}
                    fields[str(k)]=val
            result.append({'embedding_shape':list(tensor.shape) if hasattr(tensor,'shape') else type(tensor).__name__, 'metadata':fields})
        return {'count':len(conditioning),'sample_entries':result}
    @staticmethod
    def _summarize_keyframe_value(value, depth=0):
        """Inspect type/shape/time metadata only; never serialize image or latent contents."""
        import math
        if value is None or isinstance(value, (bool, str, int, float)):
            if isinstance(value, str):
                return value[:160]
            if isinstance(value, float) and not math.isfinite(value):
                return str(value)
            return value
        if hasattr(value, 'shape'):
            return {'type': type(value).__name__, 'shape': list(value.shape),
                    'dtype': str(getattr(value, 'dtype', 'unknown'))}
        if isinstance(value, (list, tuple)):
            if depth >= 3:
                return {'type': type(value).__name__, 'length': len(value)}
            return {'type': type(value).__name__, 'length': len(value),
                    'items': [H3FLFConditioningStructureDiag._summarize_keyframe_value(v, depth+1)
                              for v in value[:8]]}
        if isinstance(value, dict):
            if depth >= 3:
                return {'type': 'dict', 'keys': [str(k) for k in list(value)[:30]]}
            return {'type': 'dict', 'fields': {
                str(k): H3FLFConditioningStructureDiag._summarize_keyframe_value(v, depth+1)
                for k,v in list(value.items())[:30]}}
        # Namedtuple/dataclass/object type details; no arbitrary repr or file contents.
        info={'type': type(value).__name__}
        if hasattr(value, '__dict__'):
            try:
                fields=vars(value)
                info['fields']={str(k): H3FLFConditioningStructureDiag._summarize_keyframe_value(v, depth+1)
                                for k,v in list(fields.items())[:30]} if depth < 3 else {'keys': list(fields)[:30]}
            except Exception as exc:
                info['inspect_error']=type(exc).__name__
        return info

    @classmethod
    def _keyframe_details(cls, conditioning):
        out=[]
        if not isinstance(conditioning, (list,tuple)):
            return {'error':'not a conditioning sequence'}
        for entry_index,entry in enumerate(conditioning[:3]):
            if not isinstance(entry,(list,tuple)) or len(entry)<2 or not isinstance(entry[1],dict):
                out.append({'entry_index':entry_index,'error':'invalid entry metadata'});continue
            keyframes=entry[1].get('minimax_keyframes')
            if not isinstance(keyframes,(list,tuple)):
                out.append({'entry_index':entry_index,'type':type(keyframes).__name__});continue
            out.append({'entry_index':entry_index,'keyframe_count':len(keyframes),
                        'keyframes':[{'index':i,'description':cls._summarize_keyframe_value(k)}
                                     for i,k in enumerate(keyframes[:12])]})
        return out

    @staticmethod
    def _consistency(fresh_conditioning, continue_conditioning):
        """Read-only latent comparisons. No modification of any conditioning."""
        import torch
        def keys(c):
            try:
                return c[0][1]['minimax_keyframes']
            except (IndexError, KeyError, TypeError):
                return []
        fk, mk = keys(fresh_conditioning), keys(continue_conditioning)
        report={'flf_count':len(fk),'motion_count':len(mk),'pairs':[]}
        pairs=[('start_image',0,0),('end_image',1,1),('motion_history_first_vs_flf_start',0,2)]
        for label,fi,mi in pairs:
            item={'label':label,'flf_keyframe':fi,'motion_keyframe':mi}
            if fi >= len(fk) or mi >= len(mk):
                item['status']='missing keyframe';report['pairs'].append(item);continue
            a,b=fk[fi],mk[mi]
            if not isinstance(a,dict) or not isinstance(b,dict):
                item['status']='non-dictionary keyframe';report['pairs'].append(item);continue
            item['flf_position']=a.get('resolved_frame_index')
            item['motion_position']=b.get('resolved_frame_index')
            x,y=a.get('latent'),b.get('latent')
            if not isinstance(x,torch.Tensor) or not isinstance(y,torch.Tensor):
                item['status']='missing tensor';report['pairs'].append(item);continue
            item['flf_shape']=list(x.shape);item['motion_shape']=list(y.shape)
            item['same_python_tensor_object']=x is y
            item['same_storage']=bool(x.device==y.device and x.untyped_storage().data_ptr()==y.untyped_storage().data_ptr())
            if x.shape!=y.shape:
                item['status']='shape mismatch; not numerically comparable'
                report['pairs'].append(item);continue
            with torch.no_grad():
                try:
                    xx=x.detach().float();yy=y.detach().float()
                    finite=torch.isfinite(xx)&torch.isfinite(yy)
                    item['finite_fraction']=round(float(finite.float().mean().item()),7)
                    if bool(finite.all().item()):
                        z=(xx-yy).abs()
                        item['mae']=round(float(z.mean().item()),9)
                        item['max_abs_diff']=round(float(z.max().item()),9)
                        item['exact_equal']=bool(torch.equal(xx,yy))
                        item['allclose_1e-5']=bool(torch.allclose(xx,yy,atol=1e-5,rtol=1e-5))
                        item['status']='compared'
                    else:
                        item['status']='non-finite values; numerical comparison skipped'
                except Exception as exc:
                    item['status']='comparison_failed:'+type(exc).__name__
                finally:
                    try: del xx,yy
                    except UnboundLocalError: pass
            report['pairs'].append(item)
        return report

    def run(self,mode_flag,scene_json,inspect_flfo_conditioning,fresh_conditioning=None,continue_conditioning=None):
        if int(mode_flag)==0:
            if fresh_conditioning is None: raise RuntimeError('Part1 fresh conditioning missing')
            print('[H3FLFConditioningStructureDiag] NEW: original conditioning; previous-Part conditioning not requested')
            return (fresh_conditioning,)
        if continue_conditioning is None: raise RuntimeError('Part2 Motion Context conditioning missing')
        if self._need_both(mode_flag,scene_json,inspect_flfo_conditioning):
            print('[H3FLFConditioningStructureDiag] FLF2VA Part2: inspect only; native Motion Context remains SELECTED')
            print('[H3FLFConditioningStructureDiag] FLF frame conditioning: '+json.dumps(self._structure(fresh_conditioning),ensure_ascii=False))
            print('[H3FLFConditioningStructureDiag] Motion Context conditioning: '+json.dumps(self._structure(continue_conditioning),ensure_ascii=False))
            print('[H3FLFConditioningStructureDiag] FLF keyframe details: '+json.dumps(self._keyframe_details(fresh_conditioning),ensure_ascii=False,default=str))
            print('[H3FLFConditioningStructureDiag] Motion keyframe details: '+json.dumps(self._keyframe_details(continue_conditioning),ensure_ascii=False,default=str))
            print('[H3FLFConditioningStructureDiag] Keyframe consistency: '+json.dumps(self._consistency(fresh_conditioning,continue_conditioning),ensure_ascii=False,default=str))
        else:
            print('[H3FLFConditioningStructureDiag] CONTINUE: original Motion Context conditioning; inspection off/non-FLF')
        return (continue_conditioning,)

NODE_CLASS_MAPPINGS={'H3FLFConditioningStructureDiag':H3FLFConditioningStructureDiag}
NODE_DISPLAY_NAME_MAPPINGS={'H3FLFConditioningStructureDiag':'H3 FLF Conditioning Structure DIAG (no change to generation)'}
