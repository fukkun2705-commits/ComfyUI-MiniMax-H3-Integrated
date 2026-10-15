# ComfyUI-H3-LightAudioFinish — Experimental

A small non-generative audio post-processing node for ComfyUI, intended as an optional experiment **after** H3 Audio Refine and Clip/Part joining. It does **not** recover missing source audio detail and cannot repair distortion baked into generated audio.

## Install

Copy the `ComfyUI-H3-LightAudioFinish` folder into your active ComfyUI `custom_nodes` directory; install `scipy` and `numpy` into the Python environment used by that ComfyUI instance (they may already be installed). Restart ComfyUI and load the companion test JSON.

## Default settings

- enabled = true
- high_shelf_db = +1.5 dB, high_shelf_hz = 4000 Hz — gently boost high frequencies; change to 0 dB if it increases hiss
- peak_ceiling = 0.98 — gently limit newly created peaks; cannot repair already-clipped audio
- mix = 0.85 — combine original and equalized audio

The node does **not** change channel count, sample rate, audio duration, or video frames. The only altered branch is the final audio reaching Create Video. Disabling it returns the unmodified AUDIO input.

## Testing

With the same seed, clip count and prompts, compare ON/OFF at matched listening loudness. If harshness/hiss worsens, reduce the shelf gain to 0.5 dB or 0. Use this as a listening test, not as an automatic quality guarantee. This node has not been run in your local ComfyUI installation.
