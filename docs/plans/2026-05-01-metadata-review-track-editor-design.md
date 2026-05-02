# Metadata Review Track Editor Design

**Goal:** Improve the `Tracks` tab in the metadata review workspace so it feels like a focused track editing workbench instead of a generic data table, while preserving the existing metadata review scope and backend behavior.

## Confirmed Direction

- Keep the current metadata review page shell, hero area, summary sidebar, and `Album / Tracks / Artists` tab structure.
- Redesign only the `Tracks` panel content.
- Reuse the refined Stitch screen's visual language where it fits the metadata review workflow.
- Do not import transcoding-specific concepts into metadata review.

## Keep

- Existing editable fields: `number`, `title`, `artist_name`.
- Existing save flow and JSON payload shape.
- Existing read-only duration display.
- Existing review-task scoping rules and pending-only edit restrictions.

## Do Not Add

- No task progress card.
- No transcoding terminology.
- No fake completion percentage.
- No delete-track action.
- No new backend fields or API behavior.

## Borrow From Stitch

### 1. Embedded Track Context Header

Inside the `Tracks` panel, add a compact album context block containing:

- Album cover
- Album title
- Album artist
- Year
- Track count
- Total duration

This avoids forcing the user to look back up to the hero section while editing tracks.

### 2. Editor Rows Instead Of Grid Table

Replace the bordered table with a stacked row editor:

- Each track is a rounded surface row.
- Rows separate through spacing, hover tone changes, and soft container backgrounds.
- Number remains editable, but visually compact.
- Title remains the primary field with the strongest emphasis.
- Artist remains secondary but editable.
- Duration remains right-aligned and read-only.

### 3. Lightweight Inputs

Track inputs should feel like inline editors rather than classic admin form fields:

- Softer background
- Minimal borders
- Stronger focus state
- Better spacing and hierarchy between title and artist fields

### 4. Stronger Review Affordance

The panel should read as "review and normalize this album's tracks" rather than "edit database cells". Use compact helper copy and grouped card treatment to reinforce that mental model.

## Final Shape

### Left/Primary Area

- Compact track-panel header with cover + album context chips.
- Optional short helper note explaining editable fields.
- Vertical list of editable track rows.

### Right/Secondary Area

- Keep the existing page-level review summary/sidebar.
- Existing issue summary and task actions remain there.
- No new progress card.

## Implementation Scope

- Modify `supysonic/templates/partials/metadata-review-tracks-panel.html`
- Adjust `supysonic/static/css/metadata.css`
- Keep `supysonic/frontend/metadata.py` backend logic unchanged unless the template needs new already-available values.
- Add/update frontend render tests to protect the new tracks layout markers.

## Success Criteria

- Tracks tab still edits only `number`, `title`, and `artist_name`.
- Review page remains compatible with existing save actions.
- New layout feels closer to the refined Stitch workbench style.
- No progress/transcoding/delete affordances appear.
- Related frontend tests pass.
