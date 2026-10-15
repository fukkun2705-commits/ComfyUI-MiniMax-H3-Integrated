"""Independent, non-invasive final AV latent selector for MiniMax H3 Parts.
Does not modify any third-party custom nodes.
"""
class H3PartLastAVLatent7:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"clip_count": ("FLOAT", {"default": 2.0, "min": 1.0, "max": 7.0, "step": 1.0})},
                "optional": {f"latent_{i}": ("LATENT", {"lazy": True}) for i in range(1, 8)}}

    RETURN_TYPES = ("LATENT",)
    RETURN_NAMES = ("last_av_latent",)
    FUNCTION = "select"
    CATEGORY = "MiniMax H3/Part Context"

    @staticmethod
    def _index(clip_count):
        value = float(clip_count)
        if not 1 <= value <= 7 or value != int(value):
            raise ValueError(f"Use Clip Total must be an integer 1..7; got {clip_count}")
        return int(value)

    def check_lazy_status(self, clip_count, **kwargs):
        key = f"latent_{self._index(clip_count)}"
        return [key] if kwargs.get(key) is None else []

    def select(self, clip_count, **kwargs):
        key = f"latent_{self._index(clip_count)}"
        latent = kwargs.get(key)
        if latent is None:
            raise ValueError(f"Final AV latent missing for Clip {self._index(clip_count)}. Check USE Clip Processor and Use Clip Total.")
        return (latent,)

NODE_CLASS_MAPPINGS = {"H3PartLastAVLatent7": H3PartLastAVLatent7}
NODE_DISPLAY_NAME_MAPPINGS = {"H3PartLastAVLatent7": "H3 Part — Final AV Latent (1–7 Lazy)"}
