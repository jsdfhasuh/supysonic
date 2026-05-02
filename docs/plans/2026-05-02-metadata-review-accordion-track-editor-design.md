# Metadata Review Tracks Editor Design

**Goal:** Replace the current stacked row editor in the metadata review `Tracks` tab with a stronger album-first editing workbench that keeps the approved header and right rail, while switching the middle track editor area to the continuous scroll-editor style from Stitch `fbc2687e4c1d4a8091bedf504e6d96cb`.

## Status

- This design supersedes the earlier row-editor-only direction in `docs/plans/2026-05-01-metadata-review-track-editor-design.md`.
- This design also replaces the temporary accordion direction captured earlier on 2026-05-02.
- The page shell, hero area, top-level `Album / Tracks / Artists` navigation, and right-side review rail stay in place.
- Only the `Tracks` panel content is being redesigned.

## Approved Reference Set

### Header Reference

- Stitch: `fbc2687e4c1d4a8091bedf504e6d96cb`
- Use this as the reference for:
  - stronger album cover presence
  - larger album title treatment
  - clearer album-level metadata chips
  - better visual separation between album context and track editing list

### Middle Editor Reference

- Stitch: `fbc2687e4c1d4a8091bedf504e6d96cb`
- Use this as the reference for:
  - continuous scroll-editor structure
  - always-visible track editing surfaces
  - denser track list rhythm
  - inline per-track field grouping without accordion affordances

### Approved Header And Right-Rail Reference

- Stitch: `a6b5610986414dfdbe8408a7681670f5`
- Keep this as the reference for:
  - stronger album cover presence
  - larger album title treatment
  - cleaner album-level metadata chips
  - metadata-focused right rail with summary, issues, and confirm / dismiss actions

## Rejected Reference

- Reject `16fe98acad464fc1acfc7f9a112bd560`
- Reason: the album header is too weak and visually compressed.

## Keep

- Existing editable fields only:
  - `number`
  - `title`
  - `artist_name`
- Existing save endpoint and payload shape.
- Existing review-task scoping rules.
- Existing pending-only edit restrictions.
- Existing artist autocomplete behavior.
- Existing read-only duration display.
- Existing right-side review summary, detected issues, and confirm / dismiss actions.

## Do Not Add

- No new backend fields.
- No fake editable inputs for fields that do not exist in the current review flow.
- No progress card.
- No transcoding language.
- No delete-track action.
- No iframe or alternate page shell.

## Interaction Model

### 1. Keep The Approved Album Context Header

Inside the `Tracks` panel, keep the approved stronger album context block before the track editor list.

Required contents:

- album cover
- album title
- album artist
- year when present
- track count
- total duration

This block should stay aligned with `a6b...`. The intent is to keep the album visible as the primary review object, not just a label above a form.

### 2. Continuous Scroll Track Editor

The middle work area is split into two coordinated parts:

- a continuous track sequence list
- a focused editor panel for the selected track

Multiple tracks stay visible in the sequence list at the same time, while only the selected track shows the full editing surface.

Each row should combine:

- compact track identity in the sequence list
- a selected-track editor surface on the right

- track number
- track title
- artist
- duration

The editor should feel like the middle section of `fbc...`: a scannable review surface with a visible selected-track editing state and no collapse state.

### 3. No Accordion Affordance

- Do not use accordion toggles, chevrons, collapsed summaries, or expand/collapse behavior.
- All track editors in the middle list should remain directly visible while the panel itself scrolls.

### 4. Current-Scope Inline Fields

Each visible track editor should only render the fields that really work today.

Required editable controls:

- `number`
- `title`
- `artist_name`

Required read-only content:

- `duration`

Allowed contextual display:

- `album` may appear as a read-only context note inside the selected-track editor so the workbench better matches the `fbc...` mental model, but it must not be treated as a saved track field in this pass.

Unsupported fields shown in Stitch, such as album, genre, year, ISRC, language, composer, lyricist, comments, or review badges, are not added in this pass.

## Layout Shape

### Left / Primary Column

- stronger album context header using `a6b...` as reference
- continuous scroll track editor using `fbc...` as reference
- no accordion states

### Right / Secondary Column

- keep current page-level summary rail
- keep review summary
- keep detected issues
- keep confirm / dismiss actions
- do not introduce new cards

## Visual Principles

- Preserve the existing application shell and dark theme.
- Increase album-header emphasis before any per-track controls.
- Make the continuous track list dense and scannable.
- Make each visible editor feel like a focused review surface, not a generic admin form.
- Keep mobile behavior clean: stacked layout, no horizontal overflow for common titles, and no requirement to inspect the right rail before editing tracks.

## Implementation Scope

- Modify `supysonic/templates/partials/metadata-review-tracks-panel.html`
- Modify `supysonic/static/css/metadata.css`
- Update `tests/frontend/test_metadata_review_workspace.py`
- Only touch `supysonic/templates/metadata-review-task.html` if the new continuous editor markup needs small selector adjustments
- Keep `supysonic/frontend/metadata.py` unchanged unless the template genuinely needs already-available values exposed differently

## Success Criteria

- The `Tracks` tab clearly follows the revised split-reference decision:
  - `a6b...` for album header and right rail
  - `fbc...` for the middle track editor structure
- Only `number`, `title`, and `artist_name` remain editable.
- Duration remains read-only.
- No unsupported metadata fields are faked into the UI.
- Existing save flow still works.
- Existing artist autocomplete still works.
- The right-side review rail remains limited to summary, issues, and confirm / dismiss actions.
- The middle track editor no longer uses accordion interaction.
- Related frontend tests pass.
