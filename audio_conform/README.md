# H3 Part Audio Frame Conform (test)

Installs as `custom_nodes/H3PartAudioFrameConform` and requires only PyTorch already available in ComfyUI.

This standalone node aligns *decoded full-output* PCM to the full selected image timeline before calling the unmodified `MiniMaxH3MotionContextTrim` node. Defaults refuse corrections greater than 1% or 80ms. This is a test-stage workaround for a small (~50ms) Part2 final-output mismatch, not proof that Part boundaries are seamless. The node slightly time-scales the decoded waveform and may alter pitch marginally; verify BGM by listening. No third-party code changes.

For the actual Part2 test, set `Use Clip Total=2`, Clip1/Clip2 enabled, and verify the two file input paths. Restart ComfyUI after installing.
