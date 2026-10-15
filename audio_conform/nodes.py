import logging
import torch
import torch.nn.functional as F

_LOG=logging.getLogger('H3PartAudioFrameConform')

class H3PartAudioFrameConform:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{
            'images':('IMAGE',),
            'audio':('AUDIO',),
            'fps':('FLOAT',{'default':24.0,'min':24.0,'max':24.0,'step':0.001}),
            'max_difference_percent':('FLOAT',{'default':1.0,'min':0.0,'max':5.0,'step':0.1}),
            'max_difference_ms':('FLOAT',{'default':80.0,'min':0.0,'max':250.0,'step':5.0}),
        }}
    RETURN_TYPES=('AUDIO',)
    RETURN_NAMES=('audio',)
    FUNCTION='conform'
    CATEGORY='H3 Part / Testing'
    DESCRIPTION='Conform decoded PCM duration to full selected video before native H3 motion-context trim. Refuses mismatches larger than the user-set safety thresholds.'
    def conform(self,images,audio,fps=24.0,max_difference_percent=1.0,max_difference_ms=80.0):
        n=int(images.shape[0]);sr=int(audio['sample_rate']);wave=audio['waveform'];have=int(wave.shape[-1]);want=int(round(n/float(fps)*sr))
        if n<2 or sr<1 or have<1 or want<1:raise ValueError('H3 Part Audio Frame Conform: empty or invalid video/audio')
        diff=want-have;pct=abs(diff)/want*100.0;ms=abs(diff)/sr*1000.0
        if pct>float(max_difference_percent) or ms>float(max_difference_ms):
            raise ValueError(f'H3 Part Audio Frame Conform: duration difference {ms:.2f}ms / {pct:.3f}% exceeds safety threshold; check timeline wiring (images={n}, audio_samples={have}, sample_rate={sr})')
        if diff:
            # Tiny full-track linear time scaling: preserves all musical content and the endpoint,
            # unlike adding 50 ms of silence which could be perceptible at the Part boundary.
            shape=wave.shape
            data=wave.reshape(-1,1,have).to(dtype=torch.float32)
            adjusted=F.interpolate(data,size=want,mode='linear',align_corners=False)
            wave=adjusted.reshape(*shape[:-1],want).to(dtype=wave.dtype)
            _LOG.warning('H3 Part audio conformed %d -> %d samples (%+.3f%%, %.1fms) to match %d frames at %.2ffps. Original audio unchanged on disk.',have,want,100.0*diff/have,ms,n,fps)
        else:
            _LOG.info('H3 Part audio already exactly aligned to %d frames at %.2f fps',n,fps)
        return ({'waveform':wave,'sample_rate':sr},)
NODE_CLASS_MAPPINGS={'H3PartAudioFrameConform':H3PartAudioFrameConform}
NODE_DISPLAY_NAME_MAPPINGS={'H3PartAudioFrameConform':'H3 Part — Audio Frame Conform (safe)'}
