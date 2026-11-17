"""Reusable modern UI components for CleanSheet Desktop Studio."""
import math
from typing import Optional, List
from PySide6.QtCore import (
    Qt, QRectF, QPropertyAnimation, QEasingCurve, Property, Signal, QTimer, QSize, QPoint
)
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPaintEvent, QMouseEvent,
    QPainterPath, QCursor, QLinearGradient
)
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QGraphicsDropShadowEffect, QSizePolicy, QDialog, QApplication,
    QAbstractItemView, QHeaderView, QTableWidget, QMenu
)

from theme import ThemeManager, ThemeColors
from icons import get_icon


class Card(QFrame):
    """Modern card container with 12px rounded corners, 1px border, and soft drop shadow."""
    def __init__(self, parent=None, elevation: bool = True):
        super().__init__(parent)
        self.setObjectName("Card")
        if elevation:
            self.shadow = QGraphicsDropShadowEffect(self)
            self.shadow.setBlurRadius(24)
            self.shadow.setOffset(0, 4)
            c = ThemeManager.instance().colors.shadow_color
            self.shadow.setColor(c)
            self.setGraphicsEffect(self.shadow)
            ThemeManager.instance().subscribe(self._on_theme)

    def _on_theme(self, colors: ThemeColors):
        if hasattr(self, "shadow"):
            self.shadow.setColor(colors.shadow_color)


class StatCard(Card):
    """Metric KPI card with animated count-up, icon, label, and hint."""
    def __init__(self, label: str, value: str = "--", hint: str = "", icon_name: str = "rows", parent=None):
        super().__init__(parent, elevation=True)
        self.setObjectName("StatCard")
        self.setMinimumHeight(104)
        
        self._target_num = 0
        self._current_num = 0
        self._raw_value = value
        self._is_numeric = False
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)
        
        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(18, 18)
        self.icon_name = icon_name
        
        self.lbl_label = QLabel(label.upper())
        self.lbl_label.setObjectName("StatLabel")
        
        top_row.addWidget(self.icon_label)
        top_row.addWidget(self.lbl_label)
        top_row.addStretch()
        layout.addLayout(top_row)
        
        self.lbl_val = QLabel(str(value))
        self.lbl_val.setObjectName("StatValue")
        layout.addWidget(self.lbl_val)
        
        if hint:
            self.lbl_hint = QLabel(hint)
            self.lbl_hint.setObjectName("StatHint")
            layout.addWidget(self.lbl_hint)
        else:
            self.lbl_hint = None
            
        self._anim = QPropertyAnimation(self, b"anim_value")
        self._anim.setDuration(450)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        
        self._update_icon(ThemeManager.instance().colors)
        ThemeManager.instance().subscribe(self._update_icon)

    def _update_icon(self, c: ThemeColors):
        ico = get_icon(self.icon_name, c.accent, 16)
        self.icon_label.setPixmap(ico.pixmap(16, 16))

    def _get_anim_value(self) -> int:
        return self._current_num

    def _set_anim_value(self, val: int):
        self._current_num = int(val)
        self.lbl_val.setText(f"{self._current_num:,}")

    anim_value = Property(int, _get_anim_value, _set_anim_value)

    def set_value(self, val: str, hint: str = ""):
        clean = str(val).replace(",", "").strip()
        if clean.isdigit():
            self._target_num = int(clean)
            self._anim.stop()
            self._anim.setStartValue(self._current_num)
            self._anim.setEndValue(self._target_num)
            self._anim.start()
        else:
            self.lbl_val.setText(str(val))
        if hint and self.lbl_hint:
            self.lbl_hint.setText(hint)


class PrimaryButton(QPushButton):
    """Primary branded button with icon and hover lift micro-animation."""
    def __init__(self, text: str, icon_name: Optional[str] = None, parent=None):
        super().__init__(text, parent)
        self.setObjectName("PrimaryButton")
        self.setProperty("variant", "primary")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(36)
        
        self.icon_name = icon_name
        if icon_name:
            self._apply_icon(ThemeManager.instance().colors)
            ThemeManager.instance().subscribe(self._apply_icon)

    def _apply_icon(self, colors: ThemeColors):
        if self.icon_name:
            self.setIcon(get_icon(self.icon_name, "#FFFFFF", 16))
            self.setIconSize(QSize(16, 16))


class ProgressRing(QWidget):
    """Custom circular progress ring for Data Health Score."""
    def __init__(self, value: float = 0.0, max_value: float = 100.0, size: int = 120, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._value = 0.0
        self._target_value = value
        self._max = max_value
        self.anim = QPropertyAnimation(self, b"ring_value")
        self.anim.setDuration(700)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        ThemeManager.instance().subscribe(lambda _: self.update())

    def _get_ring_value(self) -> float:
        return self._value

    def _set_ring_value(self, val: float):
        self._value = float(val)
        self.update()

    ring_value = Property(float, _get_ring_value, _set_ring_value)

    def set_score(self, score: float):
        self.anim.stop()
        self.anim.setStartValue(self._value)
        self.anim.setEndValue(min(self._max, max(0.0, float(score))))
        self.anim.start()

    def paintEvent(self, event: QPaintEvent):
        c = ThemeManager.instance().colors
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        pen_width = 10
        rect = QRectF(pen_width / 2 + 2, pen_width / 2 + 2, w - pen_width - 4, h - pen_width - 4)
        
        # Track background
        track_pen = QPen(QColor(c.border), pen_width, Qt.SolidLine, Qt.RoundCap)
        p.setPen(track_pen)
        p.drawArc(rect, 0, 360 * 16)
        
        # Determine color by score
        if self._value >= 85:
            arc_color = QColor(c.success)
        elif self._value >= 60:
            arc_color = QColor(c.warning)
        else:
            arc_color = QColor(c.danger)
            
        active_pen = QPen(arc_color, pen_width, Qt.SolidLine, Qt.RoundCap)
        p.setPen(active_pen)
        
        angle = int((self._value / self._max) * 360 * 16)
        # Start from top (90 degrees in Qt angles is 90 * 16)
        p.drawArc(rect, 90 * 16, -angle)
        
        # Center text
        cy = h / 2.0
        p.setPen(QColor(c.text_primary))
        score_pt = max(14, int(h * 0.16))
        font = QFont("Segoe UI", score_pt, QFont.Bold)
        p.setFont(font)
        text = f"{self._value:.1f}" if self._value > 0 else "--"
        p.drawText(QRectF(0, cy - h * 0.20, w, h * 0.26), Qt.AlignCenter, text)
        
        # Center subtext - positioned comfortably within the circle
        p.setPen(QColor(c.text_secondary))
        sub_pt = max(6, int(h * 0.065))
        font_sub = QFont("Segoe UI", sub_pt, QFont.Bold)
        font_sub.setLetterSpacing(QFont.AbsoluteSpacing, 0.5)
        p.setFont(font_sub)
        p.drawText(QRectF(0, cy + h * 0.07, w, h * 0.16), Qt.AlignCenter, "HEALTH SCORE")
        p.end()


class AnimatedToggle(QWidget):
    """Modern iOS / macOS style animated toggle switch."""
    toggled = Signal(bool)

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setFixedSize(44, 24)
        self.setCursor(Qt.PointingHandCursor)
        self._checked = checked
        self._thumb_pos = 20.0 if checked else 4.0
        
        self.anim = QPropertyAnimation(self, b"thumb_pos")
        self.anim.setDuration(160)
        self.anim.setEasingCurve(QEasingCurve.InOutQuad)
        ThemeManager.instance().subscribe(lambda _: self.update())

    def _get_thumb_pos(self) -> float:
        return self._thumb_pos

    def _set_thumb_pos(self, pos: float):
        self._thumb_pos = float(pos)
        self.update()

    thumb_pos = Property(float, _get_thumb_pos, _set_thumb_pos)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        if self._checked != checked:
            self._checked = checked
            self.anim.stop()
            self.anim.setStartValue(self._thumb_pos)
            self.anim.setEndValue(24.0 if checked else 4.0)
            self.anim.start()
            self.toggled.emit(checked)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.setChecked(not self._checked)
        super().mousePressEvent(event)

    def paintEvent(self, event: QPaintEvent):
        c = ThemeManager.instance().colors
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        # Track
        track_color = QColor(c.accent if self._checked else c.input_border)
        p.setBrush(QBrush(track_color))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 2, 44, 20, 10, 10)
        
        # Thumb
        p.setBrush(QBrush(QColor("#FFFFFF")))
        p.drawEllipse(int(self._thumb_pos), 4, 16, 16)
        p.end()


class Badge(QFrame):
    """Pill badge for status, severity, and column types."""
    def __init__(self, text: str, variant: str = "info", parent=None):
        super().__init__(parent)
        self.setObjectName("Badge")
        self.setFixedHeight(22)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        
        self.lbl = QLabel(text)
        self.lbl.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
        layout.addWidget(self.lbl)
        
        self.variant = variant
        self._apply_style()
        ThemeManager.instance().subscribe(lambda _: self._apply_style())

    def set_text_and_variant(self, text: str, variant: str):
        self.lbl.setText(text)
        self.variant = variant
        self._apply_style()

    def _apply_style(self):
        c = ThemeManager.instance().colors
        styles = {
            "success": (c.success_bg, c.success),
            "warning": (c.warning_bg, c.warning),
            "danger": (c.danger_bg, c.danger),
            "info": (c.info_bg, c.info),
            "neutral": (c.surface_alt, c.text_secondary),
        }
        bg, fg = styles.get(self.variant, (c.surface_alt, c.text_secondary))
        self.setStyleSheet(f"""
            QFrame#Badge {{
                background-color: {bg};
                border-radius: 11px;
                border: 1px solid {bg};
            }}
            QLabel {{
                color: {fg};
                background: transparent;
            }}
        """)


class DropZone(QFrame):
    """Drag & drop zone with dashed accent border, hover state, and browse button."""
    file_dropped = Signal(str)
    browse_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(180)
        self._hover = False
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)
        
        self.icon_lbl = QLabel()
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.icon_lbl)
        
        self.text_title = QLabel("Drop your spreadsheet here")
        self.text_title.setFont(QFont("Segoe UI", 13, QFont.DemiBold))
        self.text_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.text_title)
        
        self.text_sub = QLabel("Works with Excel (.xlsx, .xls) and CSV files")
        self.text_sub.setObjectName("CardDesc")
        self.text_sub.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.text_sub)
        
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignCenter)
        self.browse_btn = PrimaryButton("Choose File from Computer", icon_name="folder-open")
        self.browse_btn.clicked.connect(self.browse_clicked.emit)
        btn_row.addWidget(self.browse_btn)
        layout.addLayout(btn_row)
        
        self._update_style()
        ThemeManager.instance().subscribe(lambda _: self._update_style())

    def _update_style(self):
        c = ThemeManager.instance().colors
        border_color = c.accent if self._hover else c.border
        bg_color = c.accent_subtle if self._hover else c.surface
        
        self.setStyleSheet(f"""
            QFrame#DropZone {{
                background-color: {bg_color};
                border: 2px dashed {border_color};
                border-radius: 12px;
            }}
            QLabel {{
                background: transparent;
                color: {c.text_primary};
            }}
        """)
        ico = get_icon("import", c.accent if self._hover else c.text_muted, 36)
        self.icon_lbl.setPixmap(ico.pixmap(36, 36))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(u.toLocalFile().lower().endswith((".csv", ".xlsx", ".xls")) for u in urls):
                self._hover = True
                self._update_style()
                event.acceptProposedAction()
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._hover = False
        self._update_style()
        event.accept()

    def dropEvent(self, event):
        self._hover = False
        self._update_style()
        for u in event.mimeData().urls():
            f = u.toLocalFile()
            if f.lower().endswith((".csv", ".xlsx", ".xls")):
                self.file_dropped.emit(f)
                event.acceptProposedAction()
                return
        event.ignore()


class EmptyState(QWidget):
    """Empty state illustration with icon, message, and call-to-action button."""
    action_clicked = Signal()

    def __init__(self, icon_name: str, title: str, description: str, button_text: Optional[str] = None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)
        
        self.icon_lbl = QLabel()
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        self.icon_name = icon_name
        layout.addWidget(self.icon_lbl)
        
        self.title_lbl = QLabel(title)
        self.title_lbl.setFont(QFont("Segoe UI", 14, QFont.DemiBold))
        self.title_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_lbl)
        
        self.desc_lbl = QLabel(description)
        self.desc_lbl.setObjectName("CardDesc")
        self.desc_lbl.setAlignment(Qt.AlignCenter)
        self.desc_lbl.setWordWrap(True)
        self.desc_lbl.setMaximumWidth(420)
        layout.addWidget(self.desc_lbl)
        
        if button_text:
            btn_row = QHBoxLayout()
            btn_row.setAlignment(Qt.AlignCenter)
            self.btn = PrimaryButton(button_text, icon_name="plus")
            self.btn.clicked.connect(self.action_clicked.emit)
            btn_row.addWidget(self.btn)
            layout.addLayout(btn_row)
        else:
            self.btn = None
            
        self._update_theme(ThemeManager.instance().colors)
        ThemeManager.instance().subscribe(self._update_theme)

    def _update_theme(self, c: ThemeColors):
        ico = get_icon(self.icon_name, c.text_muted, 48)
        self.icon_lbl.setPixmap(ico.pixmap(48, 48))
        self.title_lbl.setStyleSheet(f"color: {c.text_primary};")
        self.desc_lbl.setStyleSheet(f"color: {c.text_muted};")


class ToastNotification(QFrame):
    """Auto-dismissing toast snackbar notification at bottom right."""
    def __init__(self, message: str, variant: str = "success", parent=None, duration_ms: int = 3500):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedHeight(48)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(10)
        
        c = ThemeManager.instance().colors
        ico_name = {"success": "check", "error": "x", "warning": "warning"}.get(variant, "info")
        ico_col = {"success": c.success, "error": c.danger, "warning": c.warning}.get(variant, c.accent)
        
        ico_lbl = QLabel()
        ico_lbl.setPixmap(get_icon(ico_name, ico_col, 18).pixmap(18, 18))
        layout.addWidget(ico_lbl)
        
        msg_lbl = QLabel(message)
        msg_lbl.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        msg_lbl.setStyleSheet("color: #FFFFFF; background: transparent;")
        layout.addWidget(msg_lbl)
        
        close_btn = QPushButton("✕")
        close_btn.setObjectName("GhostButton")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet("color: #94A3B8; background: transparent; border: none; font-weight: bold;")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        
        self.setStyleSheet(f"""
            QFrame#Toast {{
                background-color: {c.sidebar_bg_top};
                border: 1px solid {c.sidebar_border};
                border-radius: 8px;
            }}
        """)
        
        # Auto-dismiss timer
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.close)
        self.timer.start(duration_ms)

    @classmethod
    def show_toast(cls, parent: QWidget, message: str, variant: str = "success"):
        if not parent:
            return
        toast = cls(message, variant, parent)
        toast.adjustSize()
        pw = parent.width()
        ph = parent.height()
        tw = toast.width()
        th = toast.height()
        toast.move(pw - tw - 24, ph - th - 36)
        toast.show()
