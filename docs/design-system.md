# CraftControl visual system

CraftControl uses original repository-owned SVG sprites instead of operating-system
emoji, icon fonts, or copied game textures. The visual language is inspired by the
product's block interface without reproducing Mojang artwork.

## Icon families

- `static/craftcontrol-ui.svg` contains navigation, actions, states, and metric icons.
- `static/craftcontrol-mobs.svg` contains creature, player, and projectile portraits.
- `static/craftcontrol-blocks.svg` contains semantic block and ore families.

Every symbol uses a `24 × 24` view box, integer-aligned geometry, square corners,
and a small palette derived from CraftControl's deepslate, grass, copper, sand,
water, and danger colors. Icons must remain recognizable at 16–24 pixels, avoid
fine strokes, and use no more detail than survives mobile rendering.

## Usage rules

1. Use an existing semantic symbol before adding a new one. One meaning keeps one
   icon throughout the interface.
2. Add new symbols to the appropriate sprite; do not inline bespoke SVG paths in
   application markup.
3. Decorative icons receive `aria-hidden="true"`. An icon without adjacent text
   receives a localized accessible label.
4. Identifiers used in external SVG `<use>` references must come from an internal
   allowlist or a sanitized mapping, never directly from user or telemetry input.
5. Emoji, icon fonts, raster game textures, and third-party Minecraft asset packs
   are not part of the product UI.
6. Text punctuation remains text: arrows between values, multiplication signs,
   disclosure chevrons, and plus/minus controls are not decorative icons.
7. Block icons represent visual families rather than claiming to be exact game
   textures. Unknown blocks use the neutral cube and retain a readable localized
   fallback name.
8. Cache-bust the affected stylesheet and script references whenever a sprite or
   its layout changes.

## Block localization

Known identifiers have explicit Portuguese and English labels. Unknown identifiers
are normalized into readable words, with a conservative Portuguese token fallback.
Raw `minecraft:` identifiers and underscores must not be shown as primary labels.
