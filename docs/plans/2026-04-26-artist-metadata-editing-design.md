# Artist Metadata Editing Design

**Goal:** Let admins edit artist biography and upload a single primary artist photo from `/artists`, with manual uploads overriding any auto-fetched artist images.

**Current State**
- `/artists` already supports assigning a primary artist.
- Artist biography and images already live in `Artist.artist_info_json`.
- `Artist.get_info()` and `/rest/getArtistInfo2` already read `biography` plus `image.small|medium|large` from that JSON file.
- Artist cover art serving already reads those image paths via `api.media.__new_get_cover_path()`.

**Chosen Approach**
- Extend the `/artists` modal to include a biography textarea and a single image upload control.
- Switch the save request from JSON to `multipart/form-data` so the same submit action can update:
  - primary artist mapping
  - biography text
  - optional uploaded image
- Keep all artist metadata in the existing `artist_info_json` file.
- On upload, store one source image and generate three derived files: `small`, `medium`, and `large`.
- Manual uploads always overwrite the image entries currently referenced by that artist metadata.

**Storage Rules**
- Metadata JSON stays at the path referenced by `Artist.artist_info_json`.
- If the artist has no metadata file yet, create one under the app cache directory in an artist-specific folder.
- Generated files live next to the metadata JSON.
- Image JSON shape remains compatible with existing readers:

```json
{
  "biography": "...",
  "image": {
    "small": "/abs/path/to/small.png",
    "medium": "/abs/path/to/medium.png",
    "large": "/abs/path/to/large.png"
  }
}
```

**Backend Behavior**
- `/artists` POST accepts both legacy JSON primary-artist requests and the new multipart form submission.
- Primary-artist reassignment continues to migrate historical relations.
- Biography updates overwrite `biography` in the target artist metadata JSON.
- If a photo is uploaded:
  - validate it as an image using PIL
  - generate/overwrite `small`, `medium`, and `large`
  - update JSON image paths to the generated files
- If no photo is uploaded, existing image paths remain unchanged.

**UI Behavior**
- The modal keeps the read-only current artist field and primary artist input.
- Add a biography textarea.
- Add a single file picker for the primary artist photo.
- Preserve the existing modal open/close behavior and success toast flow.

**Error Handling**
- Reject invalid images with HTTP 400.
- Reject malformed primary-artist mappings the same way current logic does.
- Allow empty biography to clear the stored text.
- If metadata JSON is missing or empty, initialize it lazily.

**Testing Strategy**
- Template regression test for new form fields and labels.
- Unit tests for metadata file update helpers.
- Frontend integration test for multipart POST updating biography and image metadata.
- Frontend integration test for invalid image upload returning 400.
