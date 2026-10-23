FLF2VA Pass2 Auto Guard - verification build (2026-10-18)

Only original code in mode_router/__init__.py is modified.
No third-party custom-node code is copied or modified.
Workflow wiring and Scene Editor selections remain unchanged.
REF2VA / T2VA / I2VA follow the original Pass2 routes.
FLF2VA keeps First+Last conditioning for Pass1, while Pass2 automatically uses existing T2VA conditioning to avoid late-frame horizontal stretching.
IMPORTANT: This is an automatic, tested-in-concept mitigation based on the user's A/B experiments, NOT a proven root-cause correction. Final-frame matching/quality may differ: verify with one 8-second clip, then multi-clip and long form.
Back up the current node folder before replacing; do not merge into or replace any external custom node.
Verify log: [H3SceneModeConditioningRouter] Pass2 selected FLF2VA -> T2VA conditioning (auto warp guard)
Revert: restore the prior original node package.
