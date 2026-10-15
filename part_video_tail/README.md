# H3 Part — Load MP4 Tail Frames (experimental helper)

Install this directory into `ComfyUI/custom_nodes` and restart ComfyUI. Requires `opencv-python`, `numpy`, and `torch` (usually already included in ComfyUI). The node accepts a video file path, absolute or relative to the ComfyUI output directory, and returns the last N video frames as ComfyUI `IMAGE`.

This is an independent utility, NOT a full Part1 -> Part2 workflow. The native H3 AV latent must separately be loaded with `MiniMaxH3MotionContextLoadLatent`; pass both inputs to `MiniMaxH3MotionContext`. Handling conditioning, trim, video/audio joins and Part1/Continue routing is not implemented here.

Do not modify any third-party custom node. This helper has not been runtime-tested in the user's ComfyUI installation.
