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
