from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHBoxLayout, QHeaderView


def polish_dialog(
    dialog,
    form_layout=None,
    root_layout=None,
    min_width: int = 520,
) -> None:
    dialog.setMinimumWidth(min_width)

    if root_layout is not None:
        root_layout.setContentsMargins(22, 22, 22, 22)
        root_layout.setSpacing(16)

    if form_layout is not None:
        form_layout.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        form_layout.setHorizontalSpacing(14)
        form_layout.setVerticalSpacing(12)


def style_toolbar(layout: QHBoxLayout) -> None:
    layout.setContentsMargins(0, 0, 0, 12)
    layout.setSpacing(10)


def style_table(table, row_height: int = 42) -> None:
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(row_height)

    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.setWordWrap(False)

    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    header.setStretchLastSection(True)
    header.setDefaultAlignment(
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )