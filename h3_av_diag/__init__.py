"""Read-only diagnostic: extract H3 video tensor from a saved Motion Context AV latent."""
import torch

class H3DiagExtractVideoLatent:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"av_latent": ("LATENT",)}}
    RETURN_TYPES = ("LATENT",)
    RETURN_NAMES = ("video_latent",)
    FUNCTION = "extract"
    CATEGORY = "MiniMax H3/Diagnostics"

    def extract(self, av_latent):
        if not isinstance(av_latent, dict) or "samples" not in av_latent:
            raise TypeError("H3 diagnostics: saved AV latent must contain samples")
        samples = av_latent["samples"]
        if isinstance(samples, (list, tuple)):
            candidates = [(i, v) for i, v in enumerate(samples) if isinstance(v, torch.Tensor) and v.ndim == 5]
            if len(candidates) != 1:
                raise ValueError(f"H3 diagnostics: expected one 5D video Tensor in AV samples list; found {[(i,tuple(v.shape)) for i,v in candidates]}")
            index, video = candidates[0]
            print(f"[H3DiagExtractVideoLatent] H3 AV samples list, video index={index}, shape={tuple(video.shape)}")
        elif isinstance(samples, torch.Tensor) and samples.ndim == 5:
            video = samples
            print(f"[H3DiagExtractVideoLatent] video-only samples, shape={tuple(video.shape)}")
        else:
            raise TypeError(f"H3 diagnostics: unsupported AV samples type={type(samples).__name__}")
        return ({"samples": video},)

NODE_CLASS_MAPPINGS={"H3DiagExtractVideoLatent": H3DiagExtractVideoLatent}
NODE_DISPLAY_NAME_MAPPINGS={"H3DiagExtractVideoLatent": "H3 DIAG - Extract Video Latent"}
