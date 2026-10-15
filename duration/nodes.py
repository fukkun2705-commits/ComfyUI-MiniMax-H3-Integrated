"""H3 1-7 clip duration planner and lazy AV router. Does not modify FaceRefine."""
import math

def _h3_frames(n):
    return max(5, 5 + 17 * round((max(5, int(round(float(n)))) - 5) / 17))

class H3ClipDurationPlanner:
    @classmethod
    def INPUT_TYPES(cls):
        req = {"clip_count": ("FLOAT", {"default": 7, "min": 1, "max": 7, "step": 1})}
        for i in range(1, 8):
            req[f"duration_{i}"] = ("FLOAT", {"default": 3., "min": 0.1, "max": 900., "step": .01})
        return {"required": req}
    RETURN_TYPES = ("INT",) * 7 + ("STRING",)
    RETURN_NAMES = tuple(f"frames_{i}" for i in range(1, 8)) + ("duration_report",)
    FUNCTION = "plan"
    CATEGORY = "H3/Duration"
    def plan(self, clip_count, **kwargs):
        count=max(1,min(7,int(round(float(clip_count)))))
        durations=[max(0.,float(kwargs[f"duration_{i}"])) for i in range(1,8)]
        # Match the previously verified 73 + 6*(90-22)=481 H3 arithmetic.
        base=[_h3_frames(round(durations[0]*24))]
        for d in durations[1:]:
            base.append(_h3_frames(max(5,round(d*24))+22))
        target=round(sum(durations[:count])*24)
        base_total=sum(base[:count])-22*(count-1)
        # All H3 legal frame counts are 5+17*k. Only the last active Clip changes.
        diff=target-base_total
        k=math.floor(diff/17+.5)
        minimum=5
        k=max(k,math.ceil((minimum-base[count-1])/17))
        base[count-1]+=17*k
        estimated=base_total+17*k
        inactive=[0 if i>=count else base[i] for i in range(7)]
        report=(f"clips={count}; target={target}f; predicted={estimated}f; "
                f"delta={estimated-target:+d}f; final_clip_step={k:+d}x17f; "
                f"lengths={inactive}")
        print('[H3ClipDurationPlanner] '+report)
        return (*inactive,report)

class H3AVLazySelect7:
    @classmethod
    def INPUT_TYPES(cls):
        required={"clip_count": ("FLOAT", {"default":7.,"min":1,"max":7,"step":1})}
        for i in range(1,8):
            required[f"images_{i}"]=("IMAGE",{"lazy":True})
            required[f"audio_{i}"]=("AUDIO",{"lazy":True})
        return {"required":required}
    RETURN_TYPES=("IMAGE","AUDIO")
    RETURN_NAMES=("images","audio")
    FUNCTION="select"
    CATEGORY="H3/Duration"
    def check_lazy_status(self,clip_count,**kwargs):
        n=max(1,min(7,int(round(float(clip_count)))))
        return [key for key in (f"images_{n}",f"audio_{n}") if key not in kwargs or kwargs[key] is None]
    def select(self,clip_count,**kwargs):
        n=max(1,min(7,int(round(float(clip_count)))))
        print(f"[H3AVLazySelect7] selected Clip{n} final video/audio")
        return (kwargs[f"images_{n}"],kwargs[f"audio_{n}"])

NODE_CLASS_MAPPINGS={"H3ClipDurationPlanner":H3ClipDurationPlanner,"H3AVLazySelect7":H3AVLazySelect7}
NODE_DISPLAY_NAME_MAPPINGS={"H3ClipDurationPlanner":"H3 Clip Duration Planner (1-7)","H3AVLazySelect7":"H3 Lazy Final AV Select (1-7)"}
