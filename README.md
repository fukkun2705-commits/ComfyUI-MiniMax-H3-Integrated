# ComfyUI-MiniMax-H3-Integrated

Integrated custom nodes for MiniMax H3 ComfyUI workflows.

This repository combines the user's four previously tested custom-node packages (Scene, ClipPart, Audio, Enhancement) in **one installable ComfyUI custom-node directory**. Node class identifiers and component Python sources are preserved.

## Installation

From the ComfyUI `custom_nodes` directory:

```bash
git clone https://github.com/fukkun2705-commits/ComfyUI-MiniMax-H3-Integrated.git
```

In the Python environment **used by ComfyUI**, install dependencies:

```bash
python -m pip install -r custom_nodes/ComfyUI-MiniMax-H3-Integrated/requirements.txt
```

The command above assumes the working directory is the ComfyUI root. Restart ComfyUI afterward.

**Important:** Remove or relocate the former separate `ComfyUI-H3-Integrated-Scene`, `ComfyUI-H3-Integrated-ClipPart`, `ComfyUI-H3-Integrated-Audio`, and `ComfyUI-H3-Integrated-Enhancement` directories **from `custom_nodes`** before using this consolidated package; otherwise ComfyUI will have duplicate node class identifiers. Keep backups outside `custom_nodes`.

## Features

- Scene Editor and project-wide REF2VA / T2VA / I2VA / FLF2VA routing
- Up to seven clips, clip duration planning and audio join alignment
- Part NEW / CONTINUE helpers and final AV latent selection
- Audio conforming and pre-trim audio-grid alignment
- Face Refine automatic bypass and Latent Upscale controls

The face-bypass logic remains included. Face Refine itself, Motion Context MultiRef and the 3D Latent Upscaler require their **separate external custom-node packages** as used by the workflow. No third-party code is copied into this repository.

## External workflow dependencies

- `seitanism/ComfyUI-H3-Motion-Context-MultiRef`
- `Carasibana/ComfyUI-H3-FaceRefine`
- `LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler`
- `kijai/ComfyUI-KJNodes`
- `Comfy-Org/Nvidia_RTX_Nodes_ComfyUI` (if workflow uses RTX VSR)

Install those packages separately as required by the workflow. Obtain models separately.

## Validation

The original four packages were tested in the user's ComfyUI environment. **This newly consolidated single-folder distribution has passed static Python syntax and module-layout checks only, and requires a fresh ComfyUI launch and generation test before publishing as verified.**

## License

MIT. See `LICENSE` in the GitHub repository.
