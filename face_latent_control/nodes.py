from __future__ import annotations
import os, numpy as np, torch
import folder_paths
from ultralytics import YOLO

_MODEL_CACHE = {}
def _candidate_roots():
    roots = [os.path.join(folder_paths.models_dir, "ultralytics")]
    try:
        for key, value in folder_paths.folder_names_and_paths.items():
            if "ultralytics" not in str(key).lower():
                continue
            paths = value[0] if isinstance(value, tuple) and value else value
            if isinstance(paths, (list, tuple, set)):
                roots.extend(str(p) for p in paths)
            elif paths:
                roots.append(str(paths))
    except Exception:
        pass
    out, seen = [], set()
    for r in roots:
        if r:
            r = os.path.normpath(r)
            if r not in seen:
                seen.add(r); out.append(r)
    return out

def _find_model(name):
    """Match upstream H3FaceRefine detector resolution exactly.

    Fails closed: never substitute an unrelated same-basename model found by
    recursive directory scanning. Folder_paths registrations take priority.
    """
    name = str(name)
    for key in ("ultralytics_bbox", "ultralytics"):
        try:
            path = folder_paths.get_full_path(key, name)
        except Exception:
            path = None
        if path:
            return os.path.normpath(path)
    root = getattr(folder_paths, "models_dir", "models")
    for sub in ("ultralytics/bbox", "ultralytics", "ultralytics/segm"):
        path = os.path.join(root, *sub.split("/"), name)
        if os.path.isfile(path):
            return os.path.normpath(path)
    raise FileNotFoundError(f"Detector '{name}' not found by the FaceRefine-compatible resolver")

def _load_yolo(path):
    if path not in _MODEL_CACHE:
        _MODEL_CACHE[path] = YOLO(path)
    return _MODEL_CACHE[path]

def _to_bgr_u8(frame):
    arr = np.clip(frame.detach().cpu().numpy() * 255.0, 0, 255).astype(np.uint8)
    return arr[..., ::-1].copy()

class H3FacePresenceGate:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required":{
            "images":("IMAGE",),
            "enabled":("BOOLEAN",{"default":True}),
            "face_detector":("STRING",{"default":"face_yolov8m.pt"}),
            "person_detector":("STRING",{"default":r"segm\person_yolov8m-seg.pt"}),
            "face_confidence":("FLOAT",{"default":0.20,"min":0.01,"max":1.0,"step":0.01}),
            "person_confidence":("FLOAT",{"default":0.20,"min":0.01,"max":1.0,"step":0.01}),
            "scan_stride":("INT",{"default":1,"min":1,"max":12,"step":1}),
        }, "optional":{
            "min_face_frames":("INT",{"default":5,"min":1,"max":100,"step":1}),
            "min_face_ratio":("FLOAT",{"default":0.15,"min":0.0,"max":1.0,"step":0.01}),
            "min_consecutive_hits":("INT",{"default":3,"min":1,"max":30,"step":1}),
        }}
    RETURN_TYPES=("BOOLEAN","STRING")
    RETURN_NAMES=("use_refine","report")
    FUNCTION="check"
    CATEGORY="MiniMax H3/Face Refine"

    def check(self, images, enabled=True, face_detector="face_yolov8m.pt",
              person_detector=r"segm\person_yolov8m-seg.pt",
              face_confidence=0.20, person_confidence=0.20, scan_stride=1,
              min_face_frames=5, min_face_ratio=0.15, min_consecutive_hits=3):
        print(f"[FaceAutoBypass DEBUG] enabled={enabled} type={type(enabled).__name__}")

        # Master OFF: stop here before detector loading/scanning.
        if not bool(enabled):
            print("[FaceAutoBypass DEBUG] master OFF -> use_refine=False")
            return (False, "AutoBypass: Face Refine master disabled -> original frames.")

        n=int(images.shape[0])
        if n<=0:
            return (False,"AutoBypass: empty batch -> original frames.")
        idx=list(range(0,n,max(1,int(scan_stride))))
        if n-1 not in idx: idx.append(n-1)

        # Require stable face visibility. One accidental bounding box in a rear-view
        # scene must not trigger the much stricter downstream H3FaceTrackCrop.
        try:
            # Reject accidentally routed person/segmentation detectors. In older
            # workflows the UI widget mapping may deliver the person model to the
            # face_detector input even when the displayed value looks correct.
            requested = str(face_detector).strip()
            if not requested:
                requested = "face_yolov8m.pt"
            normalized = requested.replace("\\", "/").lower()
            base_name = os.path.basename(normalized)
            if (not base_name.startswith("face_") or
                    not base_name.endswith(".pt") or
                    "person" in normalized or "segm/" in normalized):
                print(f"[FaceAutoBypass] WARNING: rejected non-face detector input={requested!r}; "
                      "using face_yolov8m.pt instead")
                requested = "face_yolov8m.pt"
            face_path = _find_model(requested)
            resolved_name = os.path.basename(face_path).lower()
            if not resolved_name.startswith("face_") or not resolved_name.endswith(".pt"):
                raise ValueError(f"Resolved model is not a face detector: {face_path}")
            face_model = _load_yolo(face_path)
            if getattr(face_model, "task", None) not in (None, "detect"):
                raise ValueError(f"Face detector has unsupported task={face_model.task!r}")
            print(f"[FaceAutoBypass] requested_face_detector={face_detector!r}, "
                  f"detector_path={face_path!r}, task={getattr(face_model, 'task', None)!r}, "
                  f"confidence={float(face_confidence):.3f}, frames={n}")
        except Exception as exc:
            print(f"[FaceAutoBypass] BYPASS: detector unavailable ({type(exc).__name__}: {exc})")
            return (False, f"AutoBypass: detector unavailable; skipped FaceRefine: {exc}")
        hits=[]
        for i in idx:
            try:
                r=face_model.predict(_to_bgr_u8(images[i]), conf=float(face_confidence), verbose=False)[0]
            except Exception as exc:
                print(f"[FaceAutoBypass] BYPASS: face detector failed on frame={i}: {exc}")
                return (False, f"AutoBypass: face detector failed; skipped FaceRefine: {exc}")
            if getattr(r,"boxes",None) is not None and len(r.boxes):
                hits.append(i)
        sample_count=len(idx)
        min_required=min(sample_count,max(1,int(min_face_frames)))
        ratio=len(hits)/sample_count if sample_count else 0.0
        hitset=set(hits)
        longest=0
        streak=0
        for i in idx:
            if i in hitset:
                streak += 1
                longest=max(longest,streak)
            else:
                streak=0
        allowed=(len(hits)>=min_required and
                 ratio>=float(min_face_ratio) and
                 longest>=min(int(min_consecutive_hits),sample_count))
        detail=(f"face_hits={len(hits)}/{sample_count} ({ratio:.1%}), "
                f"longest_streak={longest}, thresholds="
                f"{min_required}/{float(min_face_ratio):.0%}/{min(int(min_consecutive_hits),sample_count)}")
        print(f"[FaceAutoBypass] {'REFINE' if allowed else 'BYPASS'}: {detail}")
        if allowed:
            return (True, f"AutoBypass: stable face detection -> FaceRefine enabled; {detail}")

        # Person detection is informational only.
        person_found=False
        try:
            person_model=_load_yolo(_find_model(person_detector))
            for i in idx:
                r=person_model.predict(_to_bgr_u8(images[i]), conf=float(person_confidence), verbose=False)[0]
                if getattr(r,"boxes",None) is not None and len(r.boxes):
                    person_found=True; break
        except Exception:
            pass

        if person_found:
            return (False, f"AutoBypass: insufficient stable face detections (person present) -> FaceRefine skipped; {detail}")
        return (False, f"AutoBypass: insufficient stable face detections -> FaceRefine skipped; {detail}")

class H3LazyImageSwitch:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required":{
            "use_refine":("BOOLEAN",),
            "original":("IMAGE",{"lazy":True}),
            "refined":("IMAGE",{"lazy":True}),
        }}
    RETURN_TYPES=("IMAGE",)
    RETURN_NAMES=("images",)
    FUNCTION="select"
    CATEGORY="MiniMax H3/Face Refine"

    def check_lazy_status(self, use_refine, original=None, refined=None):
        needed="refined" if bool(use_refine) else "original"
        val=refined if bool(use_refine) else original
        return [needed] if val is None else []

    def select(self, use_refine, original=None, refined=None):
        return (refined if bool(use_refine) else original,)


class H3FaceRefineMasterControl:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required":{
            "enabled":("BOOLEAN",{"default":False}),
        }}
    RETURN_TYPES=("BOOLEAN",)
    RETURN_NAMES=("enabled",)
    FUNCTION="run"
    CATEGORY="MiniMax H3/Face Refine"

    def run(self, enabled=False):
        value = bool(enabled)
        print(f"[FaceRefineMaster DEBUG] enabled={value}")
        return (value,)



class H3LatentUpscaleMasterControl:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required":{
            "enabled":("BOOLEAN",{"default":True}),
        }}
    RETURN_TYPES=("BOOLEAN",)
    RETURN_NAMES=("enabled",)
    FUNCTION="run"
    CATEGORY="MiniMax H3/Latent Upscale"

    def run(self, enabled=True):
        value = bool(enabled)
        print(f"[LatentUpscaleMaster DEBUG] enabled={value}")
        return (value,)



class H3Pass2DeviceSelector:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required":{
            "device":(["cuda","cpu"],{"default":"cuda"}),
        }}
    RETURN_TYPES=("COMBO",)
    RETURN_NAMES=("device",)
    FUNCTION="run"
    CATEGORY="MiniMax H3/Latent Upscale"

    def run(self, device="cuda"):
        print(f"[LatentUpscaleDevice DEBUG] device={device}")
        return (device,)


class H3Pass2PrecisionSelector:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required":{
            "precision":(["fp16","bf16","fp32"],{"default":"fp16"}),
        }}
    RETURN_TYPES=("COMBO",)
    RETURN_NAMES=("precision",)
    FUNCTION="run"
    CATEGORY="MiniMax H3/Latent Upscale"

    def run(self, precision="fp16"):
        print(f"[LatentUpscalePrecision DEBUG] precision={precision}")
        return (precision,)



def _load_xmarre_3d_module():
    import importlib
    import importlib.util
    import sys

    # Try known package-style module names first.
    for modname in (
        "Comfyui_Minimax_h3_latent_Upscaler.nodes.minimax_h3_latent_upscaler_3d",
        "ComfyUI_Minimax_h3_latent_Upscaler.nodes.minimax_h3_latent_upscaler_3d",
    ):
        try:
            return importlib.import_module(modname)
        except Exception:
            pass

    # Fallback: scan custom_nodes for the exact implementation file.
    base = os.path.abspath(getattr(folder_paths, "base_path", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    custom_nodes = os.path.join(base, "custom_nodes")
    found = None
    for root, _dirs, files in os.walk(custom_nodes):
        if "minimax_h3_latent_upscaler_3d.py" in files:
            candidate = os.path.join(root, "minimax_h3_latent_upscaler_3d.py")
            # Prefer xmarre package if multiple copies exist.
            if "latent-upscaler" in candidate.lower() or "latent_upscaler" in candidate.lower():
                found = candidate
                break
            if found is None:
                found = candidate

    if not found:
        raise RuntimeError("Could not find xmarre minimax_h3_latent_upscaler_3d.py")

    pdir = os.path.dirname(found)
    if pdir not in sys.path:
        sys.path.insert(0, pdir)

    try:
        return importlib.import_module("minimax_h3_latent_upscaler_3d")
    except Exception:
        spec = importlib.util.spec_from_file_location("_h3_xmarre_up3d", found)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


def _h3_nested_members(samples):
    import comfy.nested_tensor

    if isinstance(samples, comfy.nested_tensor.NestedTensor) or getattr(samples, "is_nested", False):
        try:
            members = list(samples.unbind())
        except Exception:
            members = list(samples.tensors)
        if not members:
            raise ValueError("MiniMax H3 NestedTensor is empty")
        return members, True

    if isinstance(samples, torch.Tensor):
        return [samples], False

    raise TypeError(f"Expected torch.Tensor or MiniMax H3 NestedTensor, got {type(samples)}")


class H3NestedCleanLatentUpscaler3D:
    @classmethod
    def INPUT_TYPES(cls):
        try:
            models = folder_paths.get_filename_list("latent_upscale_models")
        except Exception:
            models = []

        default_model = "minimax_h3_latent_upscaler_3d_conv_v1_fp16.safetensors"
        if default_model not in models and models:
            default_model = models[0]

        return {"required":{
            "latent":("LATENT",),
            "model_name":(models or [default_model], {"default":default_model}),
            "scale":("FLOAT",{"default":1.5,"min":1.0,"max":4.0,"step":0.05}),
            "align":("INT",{"default":32,"min":1,"max":512,"step":1}),
            "keep_proportion":("BOOLEAN",{"default":True}),
            "offload_after_upscale":("BOOLEAN",{"default":True}),
            "device":(["cuda","cpu"],{"default":"cuda"}),
            "precision":(["fp32","fp16","bf16"],{"default":"fp16"}),
        }}

    RETURN_TYPES=("LATENT",)
    RETURN_NAMES=("latent",)
    FUNCTION="upscale"
    CATEGORY="MiniMax H3/Latent Upscale"

    def upscale(
        self,
        latent,
        model_name,
        scale=1.5,
        align=32,
        keep_proportion=True,
        offload_after_upscale=True,
        device="cuda",
        precision="fp16",
    ):
        import comfy.nested_tensor

        if not isinstance(latent, dict) or "samples" not in latent:
            raise ValueError("H3 Nested Clean Latent Upscaler requires a LATENT dict with 'samples'.")

        members, was_nested = _h3_nested_members(latent["samples"])
        video = members[0]

        if not isinstance(video, torch.Tensor) or video.ndim not in (4,5):
            raise ValueError(
                f"Expected H3 video tensor [B,C,T,H,W] or [B,C,H,W], got {type(video)} "
                f"{getattr(video, 'shape', None)}"
            )

        if video.shape[1] != 24:
            raise ValueError(f"Expected MiniMax H3 video latent with 24 channels, got {video.shape[1]}.")

        mod = _load_xmarre_3d_module()

        downsample = int(getattr(mod, "VAE_DOWNSAMPLE", 16))
        was_4d = (video.ndim == 4)
        s = video.unsqueeze(2) if was_4d else video

        _batch, _channels, temporal, h_in, w_in = s.shape
        scale_val = float(scale)

        w_pixel_target = w_in * downsample * scale_val
        h_pixel_target = h_in * downsample * scale_val

        # Use xmarre's own exact alignment helper so geometry matches its native node.
        w_pixel_final, h_pixel_final = mod._aligned_pixel_size(
            w_pixel_target,
            h_pixel_target,
            w_in,
            h_in,
            int(align),
            bool(keep_proportion),
        )

        w_out = max(1, int(w_pixel_final // downsample))
        h_out = max(1, int(h_pixel_final // downsample))

        if w_out == w_in and h_out == h_in:
            print("[H3NestedCleanUpscale] target equals source; bypass")
            return (latent,)

        print(
            f"[H3NestedCleanUpscale] video {w_in}x{h_in} -> {w_out}x{h_out} "
            f"| pixels {w_out*downsample}x{h_out*downsample} "
            f"| scale={scale_val:.3f} | audio_preserved={was_nested and len(members)>1}"
        )

        out_video = mod.upscale_clean_video_exact(
            s,
            model_name=str(model_name),
            target_h=h_out,
            target_w=w_out,
            device=str(device),
            precision=str(precision),
            offload_after_upscale=bool(offload_after_upscale),
            output_device="cpu",
            clear_cuda_cache=True,
            scale_embedding=scale_val,
        )

        if was_4d:
            out_video = out_video.squeeze(2)

        out_video = out_video.to(dtype=video.dtype)

        out = latent.copy()

        if was_nested:
            # Preserve all non-video members (MiniMax H3 audio is member 1).
            out["samples"] = comfy.nested_tensor.NestedTensor([out_video, *members[1:]])
        else:
            out["samples"] = out_video

        # Any low-resolution denoise/noise mask is no longer geometry-compatible.
        # This clean-only path goes straight to decode, so remove it deliberately.
        out.pop("noise_mask", None)

        return (out,)



class H3BoundarySafePass2Mix:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required":{
            "clean_images":("IMAGE",),
            "refined_images":("IMAGE",),
            "trim_frames":("INT",{"default":0,"min":0,"max":9999,"step":1}),
            "edge_frames":("INT",{"default":3,"min":0,"max":120,"step":1}),
            "transition_frames":("INT",{"default":3,"min":0,"max":60,"step":1}),
        }}

    RETURN_TYPES=("IMAGE",)
    RETURN_NAMES=("images",)
    FUNCTION="mix"
    CATEGORY="MiniMax H3/Latent Upscale"

    def mix(self, clean_images, refined_images, trim_frames=0,
            edge_frames=3, transition_frames=3):
        import torch

        if clean_images.ndim != 4 or refined_images.ndim != 4:
            raise ValueError("H3BoundarySafePass2Mix expects IMAGE batches [N,H,W,C].")
        if tuple(clean_images.shape) != tuple(refined_images.shape):
            raise ValueError(
                f"Clean/Pass2 image mismatch: clean={tuple(clean_images.shape)}, "
                f"refined={tuple(refined_images.shape)}"
            )

        total = int(clean_images.shape[0])
        trim = max(0, min(int(trim_frames), total))
        edge = max(0, int(edge_frames))
        trans = max(0, int(transition_frames))

        # 1.0 = clean, 0.0 = Pass2
        weight = torch.zeros(
            (total,), device=clean_images.device, dtype=clean_images.dtype
        )

        # Motion-context prefix + first visible edge stay clean.
        prefix_end = min(total, trim + edge)
        if prefix_end > 0:
            weight[:prefix_end] = 1.0

        # Fade clean -> Pass2.
        if trans > 0 and prefix_end < total:
            fade_end = min(total, prefix_end + trans)
            count = fade_end - prefix_end
            if count > 0:
                weight[prefix_end:fade_end] = torch.linspace(
                    1.0, 0.0, count + 2,
                    device=clean_images.device,
                    dtype=clean_images.dtype
                )[1:-1]

        # Last visible edge stays clean.
        suffix_start = max(0, total - edge)
        if suffix_start < total:
            weight[suffix_start:] = 1.0

        # Fade Pass2 -> clean before clip end.
        if trans > 0 and suffix_start > 0:
            fade_start = max(0, suffix_start - trans)
            count = suffix_start - fade_start
            if count > 0:
                ramp = torch.linspace(
                    0.0, 1.0, count + 2,
                    device=clean_images.device,
                    dtype=clean_images.dtype
                )[1:-1]
                weight[fade_start:suffix_start] = torch.maximum(
                    weight[fade_start:suffix_start], ramp
                )

        w = weight.view(total, 1, 1, 1)
        out = refined_images * (1.0 - w) + clean_images * w

        clean_full = int((weight >= 0.999).sum().item())
        blend_count = int(((weight > 0.001) & (weight < 0.999)).sum().item())
        pass2_full = total - clean_full - blend_count

        print(
            f"[H3BoundarySafePass2] total={total} trim={trim} "
            f"edge={edge} transition={trans} | "
            f"clean={clean_full} blend={blend_count} pass2={pass2_full}"
        )
        return (out,)

NODE_CLASS_MAPPINGS={
    "H3FacePresenceGate":H3FacePresenceGate,
    "H3LazyImageSwitch":H3LazyImageSwitch,
    "H3FaceRefineMasterControl":H3FaceRefineMasterControl,
    "H3LatentUpscaleMasterControl":H3LatentUpscaleMasterControl,
    "H3Pass2DeviceSelector":H3Pass2DeviceSelector,
    "H3Pass2PrecisionSelector":H3Pass2PrecisionSelector,
    "H3NestedCleanLatentUpscaler3D":H3NestedCleanLatentUpscaler3D,
    "H3BoundarySafePass2Mix":H3BoundarySafePass2Mix,
}
NODE_DISPLAY_NAME_MAPPINGS={
    "H3FacePresenceGate":"H3 Face Presence Gate (Auto Bypass)",
    "H3LazyImageSwitch":"H3 FaceRefine Auto Bypass Switch",
    "H3FaceRefineMasterControl":"H3 Face Refine Master Control",
    "H3LatentUpscaleMasterControl":"H3 Latent Upscale Master Control",
    "H3Pass2DeviceSelector":"H3 Pass2 Device Selector",
    "H3Pass2PrecisionSelector":"H3 Pass2 Precision Selector",
    "H3NestedCleanLatentUpscaler3D":"H3 Nested Clean Latent Upscaler (3D)",
    "H3BoundarySafePass2Mix":"H3 Boundary Safe Pass2 Mix",
}
