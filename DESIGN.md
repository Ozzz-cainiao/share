# Investlab Design System

## 1. Atmosphere & Identity

Investlab feels like a calm research notebook for long-horizon index studies: editorial enough for reading, structured enough for audit. The signature is paper-like depth with muted blue-gray ink, compact cards, and tables that make assumptions and results equally visible.

## 2. Color

### Palette

| Role | Token | Light | Dark | Usage |
| --- | --- | --- | --- | --- |
| Surface/primary | `--paper` | `#F5F7FB` | `#111827` | Page background |
| Surface/card | `--card` | `#FFFFFF` | `#1F2937` | Cards, tables, metric tiles |
| Surface/subtle | `--surface-subtle` | `#EEF2F8` | `#273244` | Table headers, badges |
| Text/primary | `--ink` | `#26304A` | `#F3F4F6` | Headings and body |
| Text/secondary | `--muted` | `#68758B` | `#CBD5E1` | Captions and explanatory text |
| Border/default | `--line` | `#DCE2ED` | `#374151` | Card/table borders |
| Brand/primary | `--brand` | `#405477` | `#8EA4CB` | Primary links and nav buttons |
| Status/success | `--positive` | `#1A7A3A` | `#4ADE80` | Positive excess return |
| Status/error | `--negative` | `#B53636` | `#F87171` | Negative excess return |
| Status/warning-bg | `--warning-bg` | `#FFF8DC` | `#422006` | Method notes and caveats |
| Status/warning-line | `--warning-line` | `#DFC578` | `#A16207` | Warning border |

### Rules

- Blue-gray is the default; bright color is reserved for status or navigation.
- Positive/negative colors appear only on signed numeric comparisons.
- Any new report page must reuse these semantic roles before adding a color.

## 3. Typography

### Scale

| Level | Size | Weight | Line Height | Tracking | Usage |
| --- | --- | --- | --- | --- | --- |
| H1 | `34px` desktop, `29px` mobile | 600 | 1.2 | 0 | Report title |
| H2 | `22px` | 600 | 1.35 | 0 | Section title |
| H3 | `18px` | 600 | 1.4 | 0 | Card title |
| Body | `15px` | 400 | 1.7 | 0 | Lead paragraphs |
| Body/sm | `14px` | 400 | 1.5 | 0 | Table cells, card body |
| Caption | `13px` | 400 | 1.5 | 0 | Metadata and footers |
| Overline | `11px` | 600 | 1.3 | `.05em` | Badges |

### Font Stack

- Primary: `-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif`
- Serif accent: `Georgia, "Songti SC", serif`
- Mono: `ui-monospace, SFMono-Regular, Menlo, monospace`

### Rules

- Use the serif accent only for the main H1.
- Body text never drops below 13px.
- Financial numbers use tabular figures when possible.

## 4. Spacing & Layout

### Base Unit

All spacing derives from a base of 4px.

| Token | Value | Usage |
| --- | --- | --- |
| `--space-2` | `8px` | Inline links, compact gaps |
| `--space-3` | `12px` | Table cell vertical rhythm |
| `--space-4` | `16px` | Mobile page margin, notes |
| `--space-5` | `20px` | Footer and section padding |
| `--space-6` | `24px` | Card inner spacing |
| `--space-7` | `28px` | Desktop horizontal shell padding |
| `--space-8` | `32px` | Section spacing |
| `--space-11` | `44px` | Desktop top shell padding |
| `--space-15` | `60px` | Desktop bottom shell padding |

### Grid

- Max content width: `960px` for research pages, `1120px` for site landing pages.
- Card metrics use a 4-column grid on desktop and 2 columns under `680px`.
- Tables may overflow horizontally only if wrapped by a deliberate scroll container.

### Calculator Breakpoints

- `1280px`: use the existing `1120px` wide shell; shared date controls and the
  calculate action share one row, and each strategy keeps a compact tabular row.
- `768px`: retain the wide shell within `--space-7` page padding; shared controls
  wrap by logical group and strategy fields use two columns.
- `375px`: use the narrow-page padding rule; each strategy becomes one stacked
  field flow and all actions remain full-width, labeled, and visible.
- `320px`: use the same stacked flow with no clipped labels or controls. Result
  tables remain semantic tables inside a deliberate horizontal scroll container
  with a visible scroll instruction rather than compressing numeric columns.
- These four widths are the required calculator review breakpoints. Layout changes
  use normal flow and Grid; they must not introduce nested cards or horizontal
  page overflow.

### Rules

- Page padding uses `44px 28px 60px` on desktop and `24px 14px 40px` on narrow screens.
- Keep report pages single-column unless a data table requires horizontal structure.

## 5. Components

### Research Card

- **Structure**: badge, H3 title, metric grid, body paragraphs.
- **Variants**: strategy card, methodology card.
- **Spacing**: `22px` padding, `14px` vertical margin.
- **States**: static content; no hover dependency.
- **Accessibility**: headings stay semantic; metrics remain text, not images.
- **Motion**: none.

### Result Table

- **Structure**: caption or preceding H2, semantic table, numeric cells right-aligned.
- **Variants**: summary, OOS, regime, inference.
- **Spacing**: `12px 16px` cells.
- **States**: optional row hover with subtle background.
- **Accessibility**: visible headings; no color-only meaning without signed number.
- **Motion**: none.

### Top Navigation Button

- **Structure**: text link styled as compact button.
- **Variants**: primary navigation link.
- **Spacing**: `8px 14px`.
- **States**: default and hover.
- **Accessibility**: real anchor with `href`.
- **Motion**: none.

### Result Strip

- **Structure**: semantic definition list with the terminal value and total profit.
- **Variants**: neutral value and signed profit.
- **Spacing**: `24px` inner spacing.
- **States**: static content; positive and negative values retain explicit signs.
- **Accessibility**: labels precede values in DOM order; color never carries meaning alone.

### Scenario Section

- **Structure**: numbered scenario label, H2 title, concise cash-flow rule, metrics, ledger, and methodology.
- **Variants**: no-sale benchmark, retained proceeds, recycled proceeds, partial profit-taking, and trailing-drawdown profit-taking; later strategies append as the next numbered section.
- **Spacing**: `80px` desktop and `64px` mobile before each scenario.
- **Accessibility**: scenarios remain in chronological document order with unique heading IDs.

### Strategy Comparison Table

- **Structure**: metric rows with one column per scenario.
- **Spacing**: follows Result Table cell spacing.
- **States**: the preferable value may use success color plus stronger weight; the number remains explicit.
- **Accessibility**: row and column headers use semantic table scopes; color is never the only distinction.
- **Motion**: none.

### Calculator Workspace

- **Structure**: one bordered workspace containing an H2, concise method note,
  shared labeled start/end date controls, an ordered strategy list, the visible
  add-strategy action, the primary calculate action, and a polite result-status
  region. Use `--card`, `--line`, `--ink`, and `--muted`; inner groups are divided
  by borders or `--space-*` gaps, not nested cards.
- **Spacing**: shell and section padding use `--space-6`; compact control groups
  use `--space-2`, `--space-3`, and `--space-4`; larger section separation uses
  `--space-8`. No calculator spacing bypasses the 4px scale.
- **States**: the page opens with one valid strategy row. Editing never triggers
  calculation; the calculate button applies all valid fields together. While a
  calculation is running, its existing label communicates progress and repeated
  submission is disabled. Invalid submission keeps prior results visible and
  moves focus to the first invalid field.
- **Accessibility**: use `fieldset` and `legend` for shared dates and each strategy,
  native buttons for actions, and an `aria-live="polite"` status for successful,
  empty, and failed calculations. Method and validation text is available without
  hover.
- **Motion**: only the existing Micro or Standard opacity/transform timing may be
  used for status changes; reduced-motion users receive an immediate state change.

### Strategy Row

- **Structure**: a stable row number and series key, editable display name,
  contribution amount, cadence, stop family, target return, trailing drawdown,
  sale fraction, recycle-proceeds checkbox, and a permanently visible labeled
  delete button. Rows are separated by `--line`, not individually boxed.
- **Conditional controls**: target return and sale fraction are disabled for no
  stop; trailing drawdown is enabled only for target-activated drawdown. Disabled
  fields stay labeled so the model remains understandable and never silently
  changes entered values.
- **Add/delete/max-row behavior**: start with one row; add appends after the last
  row until five exist. At five rows, the add button remains visible but disabled
  and its nearby helper plus polite status explains the five-row limit. Delete
  remains visible for every row; at one row it is disabled with a minimum-one-row
  explanation. Deletion preserves surviving row order, stable identity, entered
  values, and assigned chart series; a newly added row receives an available
  series key without recoloring survivors.
- **Desktop/tablet layout**: follow the Calculator Breakpoints Grid rules; fields
  align by label and may wrap only between complete field groups.
- **Mobile stacked layout**: at `375px` and `320px`, every label, native control,
  helper/error, recycle checkbox, and delete action occupies a predictable stacked
  reading order. No destructive or corrective action is hover-only.
- **Accessibility**: legends name rows independently of editable display names;
  row addition announces the new count and moves focus to the new display-name
  input, while deletion moves focus to the nearest surviving row heading.

### Native Form Control

- **Structure**: a visible Body/sm label above a native `input`, `select`, or
  checkbox, optional Caption helper beneath, and a dedicated Caption validation
  message linked with `aria-describedby`.
- **Default**: `--card` surface, `--ink` text, and Border/default. Placeholder and
  helper text use `--muted`; financial inputs use tabular figures.
- **Focus**: retain the browser's native keyboard focus indicator and reinforce it
  with `--brand`; focus must remain visible against both `--paper` and `--card`.
- **Invalid**: expose native validity and `aria-invalid="true"`, use `--negative`
  for the border/message, and state the correction in text. Do not use color alone.
- **Disabled**: preserve the label, use `--surface-subtle` and `--muted`, and keep
  the reason in adjacent helper text; disabled controls are not submitted as
  active stop parameters.
- **Interaction**: native keyboard, pointer, and touch behavior is preserved. A
  complete validation pass happens only on explicit calculation, not each
  keystroke.

### Calculator Results Table

- **Structure**: extend Result Table with one column per configured strategy in
  stable row order and rows for scheduled invested, external invested, ending
  holdings, cash pool, total assets, total profit, cumulative return, XIRR,
  contribution-neutral maximum drawdown, time in market, and stop count.
- **States**: before calculation, show a text empty state describing the required
  action; on invalid input, retain the last valid table and identify it as the
  previous result; after recalculation, update the caption with actual coverage.
- **Responsive behavior**: at `768px`, `375px`, and `320px`, keep the semantic
  table in a labeled horizontal scroll container. Keep metric row headers visible
  with `--card`, provide an explicit scroll instruction, and preserve right-aligned
  tabular numbers; never collapse cells into unlabeled values.
- **Accessibility**: strategy names are column headers, metric names are row
  headers, and the caption states requested and actual date coverage. Signed text
  and numbers carry meaning independently of series color.

### Calculator Time-Series Figure

- **Structure**: two Research Figure variants only: nominal total assets and
  contribution-neutral cumulative NAV return. Each contains a heading, legend,
  responsive inline SVG, current-value text summary, and a text/table alternative.
- **Stable five series**: series assignment belongs to strategy-row identity, not
  strategy type or current position. Keys one through five use `--brand`,
  `--positive`, `--negative`, `--muted`, and `--ink`, respectively, combined with
  distinct solid/dash patterns and explicit legend labels so color is never the
  sole identifier. Deleting or reordering does not recolor a surviving row.
- **Tooltip and focus behavior**: pointer hover or tap exposes the nearest dated
  values; keyboard focus exposes the same readout, starts at the latest date, and
  supports arrow-key traversal across observations. The active date, strategy
  name, and formatted value are announced in text. Focus is visibly reinforced
  with `--brand`; Escape dismisses the readout without losing the chart's place.
  No value is available only on hover.
- **Accessibility**: each SVG has a title and description naming date range and
  metric; legend order follows Strategy Row order; full daily calculations remain
  represented in the text/table alternative even if the display path is
  downsampled.
- **Motion**: tooltip and focus changes use only opacity/transform with existing
  timing tokens, and reduced motion makes the update immediate.

### Research Figure

- **Structure**: title, inline SVG trajectory, legend, and text-equivalent ledger.
- **Variants**: total assets, cumulative contribution, reserve pool.
- **Spacing**: `24px` inner spacing.
- **States**: static with responsive scaling.
- **Accessibility**: SVG includes title and description; source data remains downloadable as CSV.
- **Motion**: none.

## 6. Motion & Interaction

### Timing

| Type | Duration | Easing | Usage |
| --- | --- | --- | --- |
| Micro | `120ms` | `ease-out` | Link hover |
| Standard | `200ms` | `ease-in-out` | Future table disclosure |

### Rules

- Research pages are mostly static; avoid decorative animation.
- If motion is added, animate only opacity or transform.
- Respect reduced motion by making enhancements non-essential.

## 7. Depth & Surface

### Strategy

Mixed, but constrained: borders define card boundaries, and very soft shadows separate dense data blocks from the paper background.

| Level | Value | Usage |
| --- | --- | --- |
| Border/default | `1px solid var(--line)` | Cards, notes, tables |
| Shadow/subtle | `0 4px 18px rgba(35,45,75,.04)` | Cards |
| Shadow/table | `0 4px 20px rgba(35,45,75,.06)` | Tables |

### Rules

- Shadows stay below 8% alpha and never become decorative glow.
- Report content must remain readable if shadows are disabled.
