# CleanSheet Design System & UI Architecture Guide

## Overview
CleanSheet has been redesigned from a basic prototype web-lookalike into a desktop studio application inspired by the ergonomics and polish of VS Code, Notion, and Linear.

---

## 1. Design System & Theme Engine (`theme.py`)

### Colors & Palettes
The design system provides tokens for both **Light Mode** and **Dark Mode**:
- **Light Theme**:
  - Background: `#F6F7FB`
  - Surface: `#FFFFFF`, Surface Alt: `#F8FAFC`
  - Borders: `#E5E7EB`, Subtle: `#F1F5F9`
  - Text: `#0F172A` (Primary), `#334155` (Secondary), `#64748B` (Muted)
  - Accent: `#2563EB` (Hover: `#1D4ED8`, Pressed: `#1E40AF`)
  - Semantics: Success `#16A34A`, Warning `#D97706`, Danger `#DC2626`, Info `#0284C7`
- **Dark Theme**:
  - Background: `#0B1220`
  - Surface: `#111827`, Surface Alt: `#1F2937`
  - Borders: `#1F2937`, Subtle: `#1A2234`
  - Text: `#F1F5F9` (Primary), `#CBD5E1` (Secondary), `#94A3B8` (Muted)
  - Accent: `#3B82F6` (Hover: `#2563EB`, Pressed: `#1D4ED8`)

### Typography
- Primary: `Inter`
- Fallback: `Segoe UI`, `-apple-system`, `sans-serif`
- Scale: 11px (hints/badges), 12px (subtitles/captions), 13px (body/inputs), 15px (card titles), 20px (page headers), 26px (stat KPI values).

### Object-Name Scoped Selectors
To prevent styles leaking across nested widgets (such as grey background boxes behind labels inside `QFrame`), all stylesheet rules strictly target scoped object names:
```css
QFrame#Card, QFrame#StatCard, QFrame#ActionTile { ... }
QFrame#Card QLabel, QFrame#StatCard QLabel { background: transparent; }
```
Bare `QLabel {}` or `QWidget {}` background rules are strictly avoided.

---

## 2. Reusable Component Library (`components/`)

1. **`Card` & `StatCard`** (`components/widgets.py`):
   - 12px rounded corners, 1px border, subtle `QGraphicsDropShadowEffect`.
   - `StatCard` includes icon, uppercase label, big KPI number with smooth count-up animation (`QPropertyAnimation`), and contextual hint.
2. **`ProgressRing`** (`components/widgets.py`):
   - Custom `QPainter` radial health ring with dynamic arc coloring (Green for >=85, Amber for >=60, Crimson for <60) and animated score rendering.
3. **`AnimatedToggle`** (`components/widgets.py`):
   - iOS/macOS style sliding toggle switch replacing native blocky checkboxes.
4. **`Badge`** (`components/widgets.py`):
   - Pill badge supporting `success`, `warning`, `danger`, `info`, and `neutral` variants.
5. **`DropZone`** (`components/widgets.py`):
   - Dashed accent border, dragEnter hover highlight, file drop handling, and file browser trigger.
6. **`EmptyState`** (`components/widgets.py`):
   - Vector icon, bold title, descriptive subtitle, and primary call-to-action button.
7. **`ToastNotification`** (`components/widgets.py`):
   - Bottom-right auto-dismissing toast snackbar with icon, status text, and dismiss timer.
8. **`ModernTable`** (`components/table.py`):
   - Clean data table with right-click context menu (Copy Cell, Copy Column, Hide Column, Unhide All), sticky headers, and alternating row colors.
9. **`JsonSyntaxHighlighter`** (`components/table.py`):
   - Real-time syntax highlighter for JSON rules (keys, strings, numbers, booleans) with live validation status indicator.
10. **`ModernSidebar`** (`components/sidebar.py`):
    - Navy gradient background, animated collapsible width (240px ↔ 72px), active indicator accent pill, and local privacy shield note.
11. **`ModernHeader`** (`components/header.py`):
    - Page title and subtitle breadcrumb, global search box, theme toggle button, and primary "Import File" button.

---

## 3. Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| `Ctrl + O` | Import dataset (CSV / Excel) |
| `Ctrl + B` | Toggle sidebar between expanded (240px) and compact (72px) |
| `Ctrl + Shift + T` | Toggle Light / Dark Theme |
| `Ctrl + 1` to `Ctrl + 7` | Switch between pages (Overview, Import, Workflow, Profiles, Issues, Automation, Reports) |

---

## 4. Running the Application

To run CleanSheet:
```bash
python main.py
```
Or directly via:
```bash
python ui.py
```
