# Changelog

## 2.0.0-ui-redesign
### Visual & Structural Bugs Fixed
- **Invisible CleanSheet Brand Header**: Replaced the white text on white box with a brand header featuring a gradient logo mark (`#3B82F6` to `#1D4ED8`), crisp white wordmark, and uppercase subtitle "Data Preparation Studio" on the dark sidebar.
- **Grey Label Background Leaks**: Replaced all bare `QLabel {}` and `QWidget {}` stylesheet rules with strictly objectName-scoped selectors (`QFrame#Card QLabel`, `QFrame#StatCard QLabel`, etc.), eliminating all rectangular background artifacts.
- **Sidebar Scrollbar & Cut-off Items**: Removed the scroll area; replaced with a vertical fixed-height layout with `addStretch(1)` and bottom local workspace info card. Implemented smooth animated sidebar collapsing (240px ↔ 72px) via `Ctrl+B`.
- **Profiles Page Presets & Combos**: Replaced the collapsed list with selectable grid cards, animated toggle switches, properly sized and populated strategy combos, and a sticky footer bar.
- **Checkbox Artifacts**: Restyled checkboxes and introduced modern animated toggle switches (`AnimatedToggle`) with smooth thumb sliding.
- **Native Scrollbars**: Replaced native bulky scrollbars with thin, 8px rounded modern auto-hiding scrollbars.

### New Components & Features
- **Theme Engine (`theme.py`)**: Centralized design system with tokens for both Light Mode (`#F6F7FB`) and Dark Mode (`#0B1220`) toggleable via `Ctrl+Shift+T` or header icon button.
- **Icon Helper (`icons.py`)**: Seamless vector iconography powered by `qtawesome` with phosphor and fontawesome fallbacks.
- **Modular Component Library (`components/`)**:
  - `Card` & `StatCard` with smooth count-up animations (`QPropertyAnimation`).
  - `ProgressRing`: Custom `QPainter` radial data health score ring.
  - `DropZone`: Interactive drag-and-drop file import area.
  - `ModernTable`: Tables with sticky headers, alternate row shading, and right-click context menu (copy cell, copy column, hide/unhide).
  - `JsonSyntaxHighlighter`: Fast syntax highlighter with real-time JSON validation indicator.
  - `ToastNotification`: Non-blocking bottom-right auto-dismissing toast snackbars.
  - `EmptyState`: Vector-illustrated placeholder states with actionable CTA.
- **Smooth Page Transitions**: Added 180ms fade transitions (`QGraphicsOpacityEffect`) between pages.
- **Keyboard Shortcuts**: Added `Ctrl+O` (Import), `Ctrl+B` (Toggle Sidebar), `Ctrl+Shift+T` (Toggle Theme), and `Ctrl+1..7` (Page switching).

## 1.0.0-refactor
- Removed project-specific BAT launcher and build scripts.
- Consolidated dependencies into a single `requirements.txt`.
- Added a small `main.py` entry point.
- Separated standard cleaning and profiling into `levels_1_2.py`.
- Separated advanced cleaning, validation, reports, and audit into `levels_3_4.py`.
- Moved desktop widgets, background workers, and UI event handling into `ui.py`.
- Updated regression tests to import the real engine modules rather than extracting functions from `main.py`.
- Added a documented PowerShell/Python workflow for launch, tests, and Windows executable builds.
