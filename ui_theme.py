# -*- coding: utf-8 -*-
"""Element UI 风格的桌宠面板主题（颜色与组件样式）。"""

from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import QGraphicsDropShadowEffect

COLOR_PRIMARY = "#409EFF"
COLOR_PRIMARY_HOVER = "#66B1FF"
COLOR_PRIMARY_ACTIVE = "#3A8EE6"
COLOR_DANGER = "#F56C6C"
COLOR_DANGER_HOVER = "#F78989"
COLOR_INFO = "#909399"
COLOR_TEXT = "#303133"
COLOR_TEXT_REGULAR = "#606266"
COLOR_TEXT_SECONDARY = "#909399"
COLOR_BORDER = "#DCDFE6"
COLOR_BORDER_LIGHT = "#E4E7ED"
COLOR_BG = "#FFFFFF"
COLOR_BG_PAGE = "#F5F7FA"
COLOR_PRIMARY_LIGHT = "#ECF5FF"
COLOR_DANGER_LIGHT = "#FEF0F0"
COLOR_SUCCESS = "#67C23A"


def ui_font(size=12, bold=False):
    weight = QFont.Bold if bold else QFont.Normal
    return QFont("Microsoft YaHei", size, weight)


def apply_card_shadow(widget):
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(24)
    effect.setOffset(0, 6)
    effect.setColor(QColor(0, 0, 0, 36))
    widget.setGraphicsEffect(effect)


def panel_stylesheet():
    return f"""
    QWidget#elCard {{
        background: {COLOR_BG};
        border: 1px solid {COLOR_BORDER_LIGHT};
        border-radius: 8px;
    }}
    QLabel#elTitle {{
        color: {COLOR_TEXT};
        font-size: 15px;
        font-weight: 600;
        background: transparent;
        border: none;
    }}
    QLabel#elHint {{
        color: {COLOR_DANGER};
        font-size: 12px;
        background: transparent;
        border: none;
        min-height: 16px;
    }}
    QLineEdit {{
        background: {COLOR_BG};
        border: 1px solid {COLOR_BORDER};
        border-radius: 4px;
        padding: 7px 11px;
        color: {COLOR_TEXT};
        selection-background-color: {COLOR_PRIMARY_LIGHT};
    }}
    QLineEdit:hover {{
        border-color: {COLOR_INFO};
    }}
    QLineEdit:focus {{
        border-color: {COLOR_PRIMARY};
    }}
    QListWidget {{
        background: {COLOR_BG};
        border: 1px solid {COLOR_BORDER};
        border-radius: 4px;
        outline: none;
        padding: 4px;
        color: {COLOR_TEXT};
    }}
    QListWidget::item {{
        border-radius: 4px;
        padding: 8px 10px;
        margin: 1px 0;
    }}
    QListWidget::item:hover {{
        background: {COLOR_BG_PAGE};
    }}
    QListWidget::item:selected {{
        background: {COLOR_PRIMARY_LIGHT};
        color: {COLOR_PRIMARY};
    }}
    QPushButton#elPrimary {{
        background: {COLOR_PRIMARY};
        color: white;
        border: 1px solid {COLOR_PRIMARY};
        border-radius: 4px;
        padding: 8px 16px;
        font-weight: 500;
        min-height: 20px;
    }}
    QPushButton#elPrimary:hover {{
        background: {COLOR_PRIMARY_HOVER};
        border-color: {COLOR_PRIMARY_HOVER};
    }}
    QPushButton#elPrimary:pressed {{
        background: {COLOR_PRIMARY_ACTIVE};
        border-color: {COLOR_PRIMARY_ACTIVE};
    }}
    QPushButton#elDefault {{
        background: {COLOR_BG};
        color: {COLOR_TEXT_REGULAR};
        border: 1px solid {COLOR_BORDER};
        border-radius: 4px;
        padding: 8px 16px;
        min-height: 20px;
    }}
    QPushButton#elDefault:hover {{
        color: {COLOR_PRIMARY};
        border-color: {COLOR_PRIMARY_HOVER};
        background: {COLOR_PRIMARY_LIGHT};
    }}
    QPushButton#elDanger {{
        background: {COLOR_DANGER};
        color: white;
        border: 1px solid {COLOR_DANGER};
        border-radius: 4px;
        padding: 8px 16px;
        min-height: 20px;
    }}
    QPushButton#elDanger:hover {{
        background: {COLOR_DANGER_HOVER};
        border-color: {COLOR_DANGER_HOVER};
    }}
    QPushButton#elText {{
        background: transparent;
        color: {COLOR_TEXT_SECONDARY};
        border: none;
        border-radius: 4px;
        padding: 4px 8px;
        min-width: 28px;
        font-size: 16px;
    }}
    QPushButton#elText:hover {{
        color: {COLOR_PRIMARY};
        background: {COLOR_BG_PAGE};
    }}
    QPushButton#elTextDanger {{
        background: transparent;
        color: {COLOR_INFO};
        border: none;
        border-radius: 4px;
        padding: 4px 8px;
        min-width: 28px;
    }}
    QPushButton#elTextDanger:hover {{
        color: {COLOR_DANGER};
        background: {COLOR_DANGER_LIGHT};
    }}
    QCheckBox {{
        spacing: 6px;
        color: {COLOR_TEXT_REGULAR};
        background: transparent;
    }}
    QCheckBox::indicator {{
        width: 14px;
        height: 14px;
        border: 1px solid {COLOR_BORDER};
        border-radius: 2px;
        background: {COLOR_BG};
    }}
    QCheckBox::indicator:hover {{
        border-color: {COLOR_PRIMARY};
    }}
    QCheckBox::indicator:checked {{
        background: {COLOR_PRIMARY};
        border-color: {COLOR_PRIMARY};
    }}
    """
