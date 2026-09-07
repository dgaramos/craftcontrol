# CraftControl visual system

CraftControl uses original repository-owned SVG sprites instead of operating-system
emoji, icon fonts, or copied game textures. The visual language is inspired by the
product's block interface without reproducing Mojang artwork.

## Screen layout

Home, Players, and the Server hub define the visual reference for inner screens.
Use Oxanium for headings, control labels, and values; use Geist for descriptions
and editable text. Page titles are 20px with a small copper eyebrow, placed on
the page background rather than inside an additional hero card.

Inner cards use flat stone surfaces, square corners, and raised top/left edges.
Use the `--surface-inset`, `--surface-border-top`, and `--surface-border-left`
tokens for inset fields and card edges. Keep groups 12px apart, with approximately
13px of card padding. Selection is gold, the colour the Players filter and the
analytics pickers already used; green remains the live/healthy signal and the
colour of saving, and red remains the destructive/error signal. Form controls have at least 44px
of touch height. Forms stack on phones and place controls beside descriptions
when space permits; audit records expose their column labels in stacked mobile
rows. Data navigation uses four columns on phones and eight on wide screens.

Selection between a few options uses one control everywhere: a row of 36px
buttons in 10px display type, gold when chosen, wrapping when the options do not
fit. `.choice-group` is its name; the Players status filter, a setting's enum
and the analytics metric pickers are the same rule under different class names,
kept only so existing markup keeps working. A viewport-wide split button and a
horizontally scrolling row of options are not part of this language.

Choices that carry an icon — the data view switch, the ranking categories, the
block modes, the ore grid, the time presets and the weather options — are the
second variant, taller because the icon leads. They are deliberately not folded
into the text chips, and unifying their active colour is still open: the ore
grid is the last blue selection in the panel.

An inner screen is built from the shared anatomy, not from new components. The
heading block is `.inner-heading`: an eyebrow, a 20px title, and an optional
11px muted paragraph. A form is one card of `.field` rows, each carrying a
label, an optional description, an optional `.field-meta` line in copper for
what qualifies the field — when it applies, what it excludes, why it is
blocked — and then its control. Meta lines are the place for that kind of
notice; a screen that needs one does not invent a banner.

Every inner screen — including Time & weather — opens with the same heading
block, and every inset field surface uses `--surface-inset` rather than a local
hex value. Selection is sand on both segmented controls and the data view
switch. Headings, eyebrows, and helper copy are localized through `i18n`; no
screen may hard-code a language string.

## Icon families

- `apps/client/static/craftcontrol-ui.svg` contains navigation, actions, states, and metric icons.
- `apps/client/static/craftcontrol-mobs.svg` contains creature, player, and projectile portraits.
- `apps/client/static/craftcontrol-blocks.svg` contains semantic block and ore families.

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
