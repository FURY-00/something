# Canva guide

Canva's tools work on designs in the user's account. Element positions and sizes are in
pixels relative to the page. Colours are hex strings like "#1A2B3C".

## Editing an existing design
1. Find it: `search-designs` with words from the user's request (title or content), or use the
   design ID or URL they gave. If several match, pick the most recently modified or ask.
2. Open a draft: `read-design` with `open_transaction: true` and `filter.fields` ["design_content",
   "thumbnails"]. Note the `transaction_id`, each page's index, and the element locator IDs.
3. Edit: `edit-design` with `transaction_id`, `page_index` (1-based), `finalize: "keep_open"` and
   `operations`. Several operations can go in one call.
4. Check the returned draft state or thumbnail matches the request.
5. Save: `edit-design` with `finalize: "commit"` and no operations. Jarvis asks the user to approve
   first. If they decline, change what they ask for, or send `finalize: "cancel"`.

## Operations
- Wording: `find_and_replace_text` (locator_id, find_text, replace_text) or `replace_text` (locator_id, text).
  On responsive pages use `find_and_replace_text`.
- Text style: `format_text` with `formatting`: `font_size` (px), `color` (hex), `font_weight` normal/bold,
  `font_style` normal/italic, `text_align` start/center/end, `line_height`, `decoration` underline,
  `strikethrough`, lists (`list_level`, `list_marker`), `link`.
- **Font family (typeface) can't be changed with these tools.** If the user asks for a new font,
  say so plainly and offer what is possible: size, weight, italics, colour or alignment. They can
  change the typeface in Canva's editor (select the text, then the font box at the top).
- Background: a page background is usually a shape or image element filling the page. Recolour
  a shape with `recolor_element` (locator_id, color). Replace an image background with `update_fill`
  (needs an asset_id from `upload-asset-from-url`). New pages can have a colour: `add_page` with `background_color`.
- Colours of shapes and graphics: `recolor_element`; outlines: `update_stroke_properties`.
- Layout: `position_element` (top, left), `resize_element` (text: width only), `rotate_element`,
  `layer_element` (front/back), `update_opacity`, `group_elements`, `ungroup_elements`, `delete_element`.
- Adding: `add_text` (page_id, text, top, left, width), `insert_shape` (SVG path, sizes, colour),
  `insert_fill` (image/video asset), `add_page`, `reorder_page`, `replace_speaker_notes`, `update_title`.
- Images: `update_fill` replaces, `crop_media` crops, `flip_media` flips. Get assets from
  `upload-asset-from-url` or `get-assets`. Background removal: `remove-background`.

## Other tasks
- New design from a description: `generate-design` (returns candidates), then `create-design-from-candidate`.
- Export: `get-export-formats` then `export-design` (PNG, JPG, PDF, MP4, PPTX...). Give the user the result:
  call `open_link` with the download URL.
- Resize to another format (Instagram post, A4, presentation): `resize-design`.
- Copy before risky changes: `copy-design`. Organise: `create-folder`, `move-item-to-folder`.
- Show a design: `open_link` with its edit or view URL from the tool results.
