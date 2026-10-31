# Registry release checks

## After publishing

- Check the publish workflow, then inspect the exact published version in
  `https://api.comfy.org/nodes/comfyui-sceneweaver/versions?include_status_reason=true`.
  A green workflow alone does not prove Manager can offer the release.
- Confirm the version is Active. Pending is not a completed review;
  `NodeVersionStatusFlagged` needs investigation. Inspect `status_reason`
  rather than inferring a cause from the status alone.
- For a repeated finding, compare its file, issue type, and matched code with
  previously cleared releases. When authorized, request maintainer review,
  updating the existing review request when appropriate.
- Verify Manager offers the expected Registry version. A nightly Git install
  uses commit-based update checks instead of a numbered Registry installation.

## Known scanner false positive

The October 22, 2026 investigation found SceneWeaver 0.8.1 flagged on
`link.origin.connect(link.originSlot, fresh, slot)` in `js/sceneweaver.js`.
This restores LiteGraph graph links during node recreation; it does not open
a network connection.

The finding was identical to one cleared on 0.8.0, whose public reason recorded
`policy-v0.6: reviewed-safe`. Do not rename legitimate APIs, remove features,
or disable scanning merely to silence this signature. Fix actual unsafe
behavior if found; otherwise seek review. Previous clearance does not
guarantee the next release avoids a flag.

Review request: https://github.com/Comfy-Org/registry-backend/issues/296

## Manager metadata is a separate path

Manager's stars and Last Update come from its GitHub statistics database, not
the Registry publish timestamp. The scanner discovers repositories through
`custom-node-list.json`; catalog-backed Registry rows retain the GitHub
reference used to look up those statistics.

Catalog registration: https://github.com/Comfy-Org/ComfyUI-Manager/pull/3403

The investigation also found Registry-only rows missing the UI's
`update-state` field. An existing fix addresses that general defect:
https://github.com/Comfy-Org/ComfyUI-Manager/pull/3261

Check those upstream records for current outcomes. Catalog merge and database
refresh do not clear Registry security flags, and missing metadata alone does
not prove a release or Git update failed.
