class H3DiagTailFrames:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required":{"images":("IMAGE",),"count":("INT",{"default":22,"min":1,"max":1000})}}
    RETURN_TYPES=("IMAGE",)
    RETURN_NAMES=("tail_frames",)
    FUNCTION="tail"
    CATEGORY="MiniMax H3/Diagnostics"
    def tail(self, images, count):
        n=int(images.shape[0]);count=int(count)
        if n<count:
            raise ValueError(f"H3DiagTailFrames: need {count} frames but decoded only {n}")
        print(f"[H3DiagTailFrames] decoded frames={n}; saving last {count} at {tuple(images.shape[1:])}")
        return (images[-count:].contiguous(),)
NODE_CLASS_MAPPINGS={"H3DiagTailFrames":H3DiagTailFrames}
NODE_DISPLAY_NAME_MAPPINGS={"H3DiagTailFrames":"H3 DIAG — Tail Frames"}
