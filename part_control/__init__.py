"""Part switch for MiniMax H3 native AV, ComfyUI current lazy evaluation."""

class H3PartModeControl:
    MODES = ["Part1 NEW (no previous context)", "Part2+ CONTINUE (load previous context)"]
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"mode": (cls.MODES, {"default": cls.MODES[0]})}}
    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("mode_flag", "trim_frames")
    FUNCTION = "run"
    CATEGORY = "MiniMax H3/Part Control"
    def run(self, mode):
        flag = 1 if mode == self.MODES[1] else 0
        print(f"[H3PartMode] {'CONTINUE' if flag else 'NEW'}; previous-Part trim={22 if flag else 0}f")
        return (flag, 22 if flag else 0)

class H3PartClip1Length:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"normal_length": ("INT", {"default": 90, "min": 1}), "mode_flag": ("INT", {"default": 0, "min": 0, "max": 1})}}
    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("clip1_length",)
    FUNCTION = "run"
    CATEGORY = "MiniMax H3/Part Control"
    def run(self, normal_length, mode_flag):
        length = int(normal_length) + (17 if int(mode_flag) == 1 else 0)
        print(f"[H3PartMode] Clip1 length={length}f (base={normal_length}f)")
        return (length,)

class H3PartConditioningGate:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "mode_flag": ("INT", {"default": 0, "min": 0, "max": 1}),
            "fresh_conditioning": ("CONDITIONING", {"lazy": True}),
            "continue_conditioning": ("CONDITIONING", {"lazy": True}),
        }}
    RETURN_TYPES = ("CONDITIONING",)
    RETURN_NAMES = ("conditioning",)
    FUNCTION = "run"
    CATEGORY = "MiniMax H3/Part Control"
    def check_lazy_status(self, mode_flag, fresh_conditioning=None, continue_conditioning=None):
        if int(mode_flag) == 0:
            return ["fresh_conditioning"] if fresh_conditioning is None else []
        return ["continue_conditioning"] if continue_conditioning is None else []
    def run(self, mode_flag, fresh_conditioning=None, continue_conditioning=None):
        selected = continue_conditioning if int(mode_flag) else fresh_conditioning
        if selected is None:
            raise ValueError("H3PartConditioningGate: selected conditioning is missing")
        print(f"[H3PartMode] Conditioning: {'previous-Part motion context' if mode_flag else 'fresh ref2va'}")
        return (selected,)

NODE_CLASS_MAPPINGS = {
    "H3PartModeControl": H3PartModeControl,
    "H3PartClip1Length": H3PartClip1Length,
    "H3PartConditioningGate": H3PartConditioningGate,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "H3PartModeControl": "H3 Part Mode: NEW / CONTINUE",
    "H3PartClip1Length": "H3 Part Clip1 Length",
    "H3PartConditioningGate": "H3 Part Lazy Conditioning Gate",
}
