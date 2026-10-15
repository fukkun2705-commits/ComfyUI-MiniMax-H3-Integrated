# H3 Clip Duration Router (test)

Place this directory under `ComfyUI/custom_nodes/` and restart ComfyUI. Load the paired workflow JSON.

* Reads each Scene JSON duration and `Use Clip Total` (1–7).
* Calculates legal H3 frame counts (5 + 17n), 22-frame Motion Context trim, and applies nearest 17-frame correction **only to the last active clip**.
* Routes images and native AUDIO from the chosen final joined clip using ComfyUI lazy inputs, avoiding later clip generation.
* No edits to FaceRefine, FaceAutoBypass, crossfade, H3 core, or Latent Upscale.

A precise target frame count is not always reachable because H3 lengths are quantized to steps of 17. Log prints expected residual. Prediction assumes 24fps and observed 22-frame trims. The router has not been run in ComfyUI.
