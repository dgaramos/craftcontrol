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
colour of saving, and red remains the destructive/error signal. Inputs and selects have at least 44px of touch
height; choice chips are 36px by their own definition. Forms stack on phones and place controls beside descriptions
when space permits; audit records expose their column labels in stacked mobile
rows. Data navigation uses four columns on phones and eight on wide screens.

Selection between a few options uses one control everywhere: a row of 36px
buttons in 10px display type, gold when chosen, wrapping when the options do not
fit. `.choice-group` is its name; the Players status filter, a setting's enum
and the analytics metric pickers are the same rule under different class names,
kept only so existing markup keeps working. A viewport-wide split button and a
horizontally scrolling row of options are not part of this language.

Controls that carry an icon are the second variant of that layout, taller
because the icon leads: the data view switch, the ranking categories, the block
modes, the ore grid, the time presets and the weather options.

Only some of them are selections. The view switch, the categories, the block
modes and the ore grid choose something that stays chosen, and they mark it in
gold like the text chips — drawn differently, though: a text chip fills with
gold, while an icon chip keeps the dark surface and takes a gold edge and label.
The sprites are multi-colour pixel art with no `currentColor`, so filling their
ground would leave the artwork fighting the colour behind it.

The time presets and the weather options borrow the same layout but are actions:
pressing one sets the time or the weather and nothing stays selected afterwards.
They have no selected state, and giving them one would claim a mode the server
does not keep.

An inner screen is built from the shared anatomy, not from new components. The
heading block is `.inner-heading`: an eyebrow, a 20px title, and an optional
11px muted paragraph. A form is one card of `.field` rows, each carrying a
label, an optional description, an optional `.field-meta` line in copper for
what qualifies the field — when it applies, what it excludes, why it is
blocked — and then its control. Meta lines are the place for that kind of
notice; a screen that needs one does not invent a banner.

Every inner screen — including Time & weather — opens with the same heading
block, and every inset field surface uses `--surface-inset` rather than a local
hex value. Headings, eyebrows, and helper copy are localized through `i18n`; no screen may
hard-code a language string.

## Color themes

The interface follows the system color scheme by default. The profile sheet
allows System, Light, or Dark; the choice is local to the browser, stored under
`craftcontrol-theme`, and never requires a backend write. With storage blocked,
a choice still works for the current page. The blocking `theme-init.js` applies
saved preferences before first paint; `core/theme.js` binds the profile controls.

`light.css` is the light palette and component color overrides. Its stylesheet
link uses `prefers-color-scheme` in System mode, so OS changes apply immediately
without JavaScript listeners. Preserve layout and original sprite colors across
themes, with gold for selection, green for healthy/save, and red for errors.
Keep the 32px background grid, 18px panel checkerboard, raised button gradients,
and grass strip in their original contexts; adapt texture contrast to the light
palette and preserve the dark design's flat form, analytics, and auth surfaces.
The System choice uses a half-sun/half-moon sprite beside its label.

## Design tokens

The palette lives in `apps/client/static/app.css :root` as three layers. The
layer boundaries are marked by `/* token-layer: … */` comments, which
`apps/client/tests/contracts/design-token-contracts.test.js` reads to enforce
the rules below.

### The authoring rule

**A color that differs between themes must be a token. `light.css` re-tints
tokens and never re-declares a selector.**

This is the whole reason the layers exist. Re-tinting a token costs no
specificity — `:root { --x: … }` does not compete with a selector. Re-declaring
a selector does compete, and because `light.css` loads last it has to escalate
(`:root :is(…)`, 0-2-1) to win. That escalation then runs over legitimate
component overrides at 0-1-0, which is how the light theme once covered the
whole Players screen with the panel checkerboard.

### Tier 1 — primitives

The raw ramps: `--stone-{950..100}`, `--grass/copper/sand/water/redstone-{700..200}`,
`--amethyst-{600,300,200}`. A higher step is darker.

Primitives are named by **Minecraft material and numeric step** — `stone`,
`grass`, `copper`, `sand`, `water`, `redstone`, `amethyst`. These are material
names, not color names: the ramp is the product's material identity, and it is
the one place where a literal value may be written.

**Call sites never reference a primitive directly.** A call site bound to a raw
ramp step loses the seam that lets `light.css` re-tint it, which defeats the
layering. Consume tier 2, or tier 3 where a component owns the decision.

### Tier 2 — semantic aliases

The vocabulary authors actually write, in six families: surfaces, elevation,
borders, content, semantic accents (an `-fg` / `-bg` / `-border` triplet for
each of success, danger, warning, info, selected, neutral), and states.

A tier-2 name says **what the token does**, never what it looks like or which
theme it belongs to. No `--green-700`, no `--dark-bg`, no `--light-surface`:
`--success-fg` keeps its meaning after the light theme re-tints it, while a
name carrying an appearance becomes a lie the moment the theme changes. The
rule is enforced per hyphen segment, so `--edge-highlight` is fine and
`--edge-light` is not.

This tier contains no literal values. It renames primitives; it does not
introduce color. A literal here would be a fourth, undocumented palette.

#### Elevation and borders

The pixel bevel is structural, so its parts are named. A raised surface
declares `border-top-color: var(--edge-highlight)` and
`border-left-color: var(--edge-highlight-soft)` over a `--border-base` frame,
and sits on `--shadow-pixel` (panels), `0 Npx 0 var(--edge-shadow)` (buttons
and small cards) or `--shadow-pressed` (a pressed button). A recessed surface
carries the soft highlight as an inset bevel: `inset 2px 2px 0
var(--edge-highlight-soft)`. Floating bars use `--shadow-overlay`; a drop whose
blur and offset belong to the site keeps its geometry and tints the ink with
`--shadow-ambient`. Neutral hairlines and outlines are `--border-strong`,
`--border-interactive` or `--border-subtle`, chosen by the ratio they measured
on the surface they sit on. `--pixel-shadow`, `--surface-border-top` and
`--surface-border-left` survive only as aliases of these tokens; write the
token, not the alias.

`light.css` re-tints the whole family (a white top edge, pale stone for the
soft edge and inset bevel, a darker stone drop, translucent moss ambient ink).
The two light selector overrides that remain in this area are deliberate
design differences, not re-statements: the dialog frame is one flat line, and
buttons sit on a 3px drop instead of 4px.

### Tier 3 — component tokens

Only where a component owns the decision and no semantic alias expresses it —
`--panel-stripe-v` / `--panel-stripe-h` and `--shadow-ambient` are the pattern.
Literals are permitted here, and the same no-appearance naming rule applies.

### Sprite exclusion

`.shield`, `.server-status-shield`, `.grass-edge` and the SVG sprites keep their
own palette in both themes. Each such rule sits inside a named region:

```css
/* region: sprites — own palette in both themes; exempt from the budget. */
…
/* endregion: sprites */
```

The contract test allowlists **by region location**, not by enumerating hex
values, so a sprite tweak does not require editing the test.

### The literal-hex budget

`design-token-contracts.test.js` pins two decreasing-only ceilings over
`app.css`, `analytics.css`, `players.css` and `auth.css`: the whole-file count,
and the count outside sprite regions. The second is the one that measures
tokenization progress. Both may be lowered as call sites migrate; neither may
ever be raised, because a raise means an untokenized color was added.

The same test pins two more guarded properties. The number of `:root`-prefixed
override rules in `light.css` is a decreasing-only ceiling, so a light-theme
fix must re-tint a token rather than add a selector. And the WCAG contrast of
each content/surface alias pair — `--text-primary` and `--text-secondary` on
every `--surface-*`, plus the border-on-surface pairs — is pinned to a floor in
both themes; a ramp step may move only while every floor still holds.

### The neutral ramp

Dark neutrals are consumed through the surface, border and content aliases,
never as literals: `--surface-sunken` for the recessed lists and code blocks,
`--surface-base` for the page-level cards, `--surface-inset` for fields,
`--surface-overlay` for chips and badges, `--neutral-bg` for drawer and
summary surfaces, `--surface-raised` for panels, `--surface-hover` for hover
fills; `--border-base` for the near-black frame, `--border-subtle`,
`--border-interactive` and `--border-strong` for the progressively lighter
edges; `--text-tertiary` for arrows and de-emphasised captions. The drop shadow
under a control is `--edge-shadow`; the inset bevels and top/left highlights
are elevation and keep their literals until that step lands.

### The accent triplets

Each semantic accent — success, danger, warning, info, selected, neutral — is
a `-fg` / `-bg` / `-border` triplet, and the three are declared together:
`-fg` is the text measured on `-bg`, `-border` frames that surface. A theme
re-tints all three or none, which is what makes "a light accent disappears in
the light theme" structurally impossible: the design never holds one value
where it needs two. The contract test pins every `-fg` on `-bg` pair to WCAG
AA (4.5:1) in both themes and requires `light.css` to re-tint every role.

The pair is text on its own accent surface: `--danger-fg` is the pale error
copy inside an error panel (`.op-error`, `.telemetry-pack-error`, the death
history), `--info-fg` the caption inside the telemetry profile, `--success-fg`
the label of a green pill and, because green text on a neutral card was the
same value, every green heading and value. Accent text on a *neutral* surface
that has a different hue — the coral `--danger` offline heading, the ore
palette, the health badges — is a different pair and keeps its own token or
literal until a component token names it.

The accent `-bg` and lightest steps of each ramp were settled by measuring the
surfaces the call sites already used, so binding a pair never lowered a ratio;
`design-token-contracts.test.js` records each migrated site's pre-migration
ratio as a floor. `--grass-light` is lighter than `--grass` in both themes, as
the name promises, and no call site consumes it any more. `light.css`
contains no `!important`: the two it once needed were symptoms of component
rules that reached for `!important` first, and both are now token re-tints.

## Icon families

- `apps/client/static/craftcontrol-ui.svg` contains navigation, actions, states, and metric icons.
- `apps/client/static/craftcontrol-mobs.svg` contains creature, player, and projectile portraits.
- `apps/client/static/craftcontrol-blocks.svg` contains semantic block and ore families.

Every symbol uses a `24 × 24` view box, integer-aligned geometry, square corners,
and a small palette derived from CraftControl's deepslate, grass, copper, sand,
water, and danger colors. Icons must remain recognizable at 16–24 pixels, avoid
fine strokes, and use no more detail than survives mobile rendering.

Navigation symbols use a dark one-pixel silhouette, a dominant semantic color,
and one highlight plane. Operational destinations such as settings, telemetry,
history, and export have distinct symbols; a generic data symbol must not stand
in for them. Ranking positions use the bundled numbered pixel badges rather than
operating-system medals.

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
