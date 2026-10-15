---
name: eui-pyside6-polish
description: Polish PySide6/PyQt desktop tools with an EUI-NEO inspired product UI: cohesive theme tokens, clear component states, rounded panels, native-tool density, and reusable desktop design rules. Use when improving this invoice app's UI or any long-lived Python Qt desktop utility.
---

# EUI PySide6 Polish

Use this skill for native desktop tools, especially PySide6/PyQt apps that should feel like a durable product instead of a script window.

This blends:
- Anthropic frontend-design: choose an intentional aesthetic and avoid generic AI UI.
- EUI-NEO: lightweight desktop GUI feel, theme tokens, rounded panels, explicit hover/pressed states.
- EvolveUI: Qt-oriented component consistency, centralized theme values, reusable components.
- Elastic UI: mature component-system thinking, especially navigation, tables, tokens, and state coverage.

## Design Direction

Default aesthetic for the invoice tool: **clean EUI desktop workbench**.

- Light, low-noise background.
- Big but not bloated rounded panels.
- Left navigation with thick selected state.
- Main workspace with a calm top toolbar, KPI strip, and large functional panels.
- Dense tables where data matters, but without harsh grid noise.
- Accent color used for selected state and primary action only.
- No decorative gradients, hero sections, or marketing layout.

## Required Theme Tokens

Define tokens before styling widgets. Do not hardcode colors directly across QSS.

- `app_bg`
- `surface`
- `surface_alt`
- `surface_hover`
- `surface_active`
- `field`
- `border`
- `text`
- `muted`
- `primary`
- `primary_hover`
- `primary_soft`
- `danger`
- `warning`
- `success`
- `radius_sm`
- `radius_md`
- `radius_lg`
- `shadow_panel`
- `control_height`
- `nav_item_height`
- `table_row_height`

Every theme must provide these tokens. Component QSS must read from tokens.

## Layout Rules

Use a stable shell:

1. Left sidebar: module navigation.
2. Right page stack: one page per module.
3. Current workflow page: top command panel, optional KPI/status strip, then resizable work surface.

For this invoice app:

- Sidebar modules: 发票分叠, 发票整理, 财务系统, 设置.
- 发票分叠 is the first working page.
- 发票整理 and 财务系统 may be placeholder pages, but must look intentional.
- 设置 contains theme choice and long-term preferences.

Avoid nested cards. Use panels for major regions, not every row.

## Component Rules

### Sidebar

- Width: 190-230 px.
- Brand at top.
- Nav item height: 46-56 px.
- Selected nav item: filled primary, white text, clear left/whole-block state.
- Unselected nav item: surface background, subtle border, visible hover.
- Use short labels and optional icons.

### Panels

- Major panel radius: 14-20 px.
- Border: subtle, visible enough to separate surfaces.
- Shadow: soft and sparse; panel shadows can exist, but do not stack them everywhere.
- Inner padding: 14-22 px depending on density.

### Buttons

Use exactly three button forms:

- Filled: primary action only.
- Outline: normal secondary action.
- Ghost: low-emphasis toolbar/navigation action.

Matched peer actions must share the same form. For example, 新增 and 删除 should not be visually unrelated.

Button state coverage is mandatory:

- normal
- hover
- pressed
- disabled
- checked/active when applicable

### Inputs And Dropdowns

Inputs, date editors, spin boxes, and combo boxes must share:

- Same height.
- Same radius.
- Same border/focus behavior.
- Popup list normal/hover/selected text and background.

Never leave combo popup selection invisible until hover.

### Tables And Trees

For data-heavy desktop tools:

- Hide vertical row headers unless row numbers are meaningful.
- Prefer soft alternating rows over full grid lines.
- Selected rows must be visible both focused and unfocused.
- Header background should be calmer than primary actions.
- Row height should be stable, usually 30-36 px.
- Amount columns right-aligned.

### Empty And Placeholder Pages

No marketing hero. Use:

- Page title.
- One short sentence explaining module purpose.
- Empty state panel with concrete future actions.

## Typography

For Chinese desktop tools:

- Base font: `Microsoft YaHei UI` or system fallback.
- Titles: heavier weight, not huge.
- Data rows: readable, compact.
- Do not use viewport-scaled fonts.
- Keep labels short and Chinese-localized.

## PySide6 Implementation

- Use `QStackedWidget` for module pages.
- Use object names on widgets and one app-level QSS.
- Build helper methods for repeated panels and controls.
- Keep business logic separate from UI styling helpers.
- Store selected theme in `settings.json`.
- Verify by `python -m py_compile` and by instantiating `MainWindow` offscreen when possible.

## Pre-Final Checklist

- Can the selected nav item, selected table row, selected dropdown item, and focused input all be seen immediately?
- Do all controls in one row share height and radius?
- Does the first screen show the actual invoice workflow?
- Is the UI cohesive in light and dark themes?
- Are disabled states readable but clearly inactive?
- Did you avoid generic web landing-page aesthetics?
- Did you avoid fixing one widget while leaving sibling widgets in a different style?
