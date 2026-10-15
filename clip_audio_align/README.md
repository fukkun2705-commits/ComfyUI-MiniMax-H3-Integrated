# H3 Clip Join Audio Align (TEST)

Install folder under ComfyUI/custom_nodes/ and restart.

At each Clip2–7 join, compares the image frame count with the concatenated AUDIO duration. Corrects at most 1.5 frames per join at 24fps, using slight waveform time-resampling. An unexpectedly larger discrepancy raises an error instead of hiding it. Does not modify original disk audio.

Keep your previous working workflow and plugin versions until validated.
