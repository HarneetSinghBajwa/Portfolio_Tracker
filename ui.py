
import sys
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox,
    QDialog, QFormLayout, QDoubleSpinBox, QDialogButtonBox,
    QApplication, QAbstractItemView
)

import database
import market_data


class AddStockDialog(QDialog):
    """A single form for adding a stock."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Stock")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.symbol_input = QLineEdit()
        self.symbol_input.setPlaceholderText("e.g. RELIANCE or TCS")
        form.addRow("Stock symbol:", self.symbol_input)

        self.company_input = QLineEdit()
        self.company_input.setPlaceholderText("e.g. Reliance Industries")
        form.addRow("Company name:", self.company_input)

        self.quantity_input = QDoubleSpinBox()
        self.quantity_input.setRange(0, 1000000000)
        self.quantity_input.setDecimals(4)
        self.quantity_input.setValue(0)
        form.addRow("Quantity owned:", self.quantity_input)

        self.cost_input = QDoubleSpinBox()
        self.cost_input.setRange(0, 100000000)
        self.cost_input.setDecimals(2)
        self.cost_input.setPrefix("₹ ")
        self.cost_input.setValue(0)
        form.addRow("Average cost per share:", self.cost_input)

        layout.addLayout(form)

        note = QLabel(
            "Set quantity to 0 to add a stock to your watchlist. "
            "For holdings, enter your quantity and average purchase price."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.symbol_input.setFocus()

    def validate_and_accept(self):
        symbol = self.symbol_input.text().strip()
        company = self.company_input.text().strip()
        quantity = self.quantity_input.value()
        average_cost = self.cost_input.value()

        if not symbol:
            QMessageBox.warning(self, "Missing symbol", "Enter a stock symbol.")
            self.symbol_input.setFocus()
            return

        if quantity > 0 and average_cost <= 0:
            QMessageBox.warning(
                self,
                "Missing purchase price",
                "Enter an average purchase price greater than zero "
                "when you own shares."
            )
            self.cost_input.setFocus()
            return

        self.accept()


class PortfolioUI(QWidget):
    def __init__(self):
        super().__init__()

        database.initialize_database()
        self.stocks = []
        self.quotes = {}
        self.refreshing = False

        self.setStyleSheet("""
            QWidget {
                background-color: #151922;
                color: #edf2f7;
                font-size: 13px;
            }
            QLabel#heading {
                font-size: 27px;
                font-weight: bold;
                color: #ffffff;
            }
            QLabel#subtitle {
                color: #aab5c5;
                font-size: 13px;
            }
            QLabel.summary {
                background-color: #222a38;
                border: 1px solid #354156;
                border-radius: 10px;
                padding: 15px;
                font-size: 15px;
                font-weight: bold;
            }
            QLineEdit, QDoubleSpinBox {
                background-color: #222a38;
                border: 1px solid #3a465a;
                border-radius: 6px;
                padding: 10px;
                color: #ffffff;
            }
            QPushButton {
                background-color: #2864dc;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3978f0;
            }
            QPushButton:disabled {
                background-color: #526078;
            }
            QPushButton#removeButton {
                background-color: #9f303b;
            }
            QTableWidget {
                background-color: #1c2330;
                alternate-background-color: #222a38;
                gridline-color: #354156;
                border: 1px solid #354156;
                border-radius: 8px;
                selection-background-color: #315da8;
                selection-color: white;
            }
            QHeaderView::section {
                background-color: #293448;
                color: #ffffff;
                padding: 10px;
                border: none;
                font-weight: bold;
            }
            QDialog {
                background-color: #151922;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 16)
        root.setSpacing(14)

        heading = QLabel("NSE Portfolio Tracker")
        heading.setObjectName("heading")
        root.addWidget(heading)

        subtitle = QLabel(
            "Track your holdings, market value and unrealised performance."
        )
        subtitle.setObjectName("subtitle")
        root.addWidget(subtitle)

        # Portfolio summary
        summary_layout = QGridLayout()
        summary_layout.setSpacing(14)

        self.value_card = QLabel("Portfolio Value\n₹0.00")
        self.invested_card = QLabel("Invested Amount\n₹0.00")
        self.pnl_card = QLabel("Unrealised P&L\n₹0.00")

        for card in (
            self.value_card,
            self.invested_card,
            self.pnl_card,
        ):
            card.setProperty("class", "summary")
            card.setMinimumHeight(72)
            card.setAlignment(
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignVCenter
            )

        summary_layout.addWidget(self.value_card, 0, 0)
        summary_layout.addWidget(self.invested_card, 0, 1)
        summary_layout.addWidget(self.pnl_card, 0, 2)
        root.addLayout(summary_layout)

        # Search and actions
        actions = QHBoxLayout()
        actions.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Enter a stock symbol, e.g. RELIANCE, TCS, INFY"
        )
        self.search_input.returnPressed.connect(self.add_stock)
        actions.addWidget(self.search_input, 1)

        self.add_button = QPushButton("+ Add Stock")
        self.add_button.clicked.connect(self.add_stock)
        actions.addWidget(self.add_button)

        self.refresh_button = QPushButton("Refresh Prices")
        self.refresh_button.clicked.connect(self.refresh_prices)
        actions.addWidget(self.refresh_button)

        self.remove_button = QPushButton("Remove Selected")
        self.remove_button.setObjectName("removeButton")
        self.remove_button.clicked.connect(self.remove_selected)
        actions.addWidget(self.remove_button)

        root.addLayout(actions)

        # Holdings table
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Stock",
            "Quantity",
            "Average Cost",
            "Current Price",
            "Market Value",
            "Profit / Loss",
        ])

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.verticalHeader().setVisible(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        for column in range(1, 6):
            header.setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )

        root.addWidget(self.table, 1)

        self.status_label = QLabel("Ready — add a stock to start tracking.")
        self.status_label.setObjectName("subtitle")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        # Automatic price refresh
        self.timer = QTimer(self)
        self.timer.setInterval(60_000)
        self.timer.timeout.connect(self.refresh_prices)
        self.timer.start()

        self.load_stocks()
        QTimer.singleShot(500, self.refresh_prices)

    def add_stock(self):
        """Open the stock form and save the entry."""

        print("Add Stock button clicked", flush=True)

        dialog = AddStockDialog(self)

        # Use any ticker already typed in the main search field.
        typed_symbol = self.search_input.text().strip()
        if typed_symbol:
            dialog.symbol_input.setText(typed_symbol.upper())

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        raw_symbol = dialog.symbol_input.text().strip().upper()
        company = dialog.company_input.text().strip()
        quantity = dialog.quantity_input.value()
        average_cost = dialog.cost_input.value()

        try:
            symbol = market_data.normalize_symbol(raw_symbol)

            if not company:
                company = symbol

            database.add_stock(
                symbol,
                company,
                quantity,
                average_cost,
            )

            self.search_input.clear()
            self.load_stocks()

            self.status_label.setText(
                f"Added {company} ({symbol}). Fetching price..."
            )

            # Immediately fetch a quote for the new stock.
            self.refresh_prices()

        except Exception as error:
            QMessageBox.warning(
                self,
                "Could not add stock",
                f"Unable to add {raw_symbol}.\n\n"
                f"Details: {error}\n\n"
                "If this stock is already in your list, remove it "
                "or use a different symbol."
            )

    def load_stocks(self):
        try:
            self.stocks = database.get_all_stocks()
            self.render_table()
            self.update_summary()
        except Exception as error:
            QMessageBox.critical(
                self,
                "Database error",
                f"Could not load saved stocks.\n\n{error}"
            )

    def remove_selected(self):
        row = self.table.currentRow()

        if row < 0 or row >= len(self.stocks):
            QMessageBox.information(
                self,
                "Select a stock",
                "Click a stock row first, then click Remove Selected."
            )
            return

        stock = self.stocks[row]

        answer = QMessageBox.question(
            self,
            "Remove stock",
            f"Remove {stock['company_name']} ({stock['symbol']}) "
            "from your portfolio?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            database.remove_stock(stock["id"])
            self.quotes.pop(stock["symbol"], None)
            self.load_stocks()
            self.status_label.setText(
                f"Removed {stock['symbol']}."
            )
        except Exception as error:
            QMessageBox.warning(
                self,
                "Remove failed",
                str(error)
            )

    def refresh_prices(self):
        """Fetch available quotes and update the table."""

        if self.refreshing:
            return

        if not self.stocks:
            self.render_table()
            self.update_summary()
            self.status_label.setText(
                "Ready — add a stock to start tracking."
            )
            return

        self.refreshing = True
        self.refresh_button.setEnabled(False)
        self.status_label.setText(
            "Fetching latest available prices..."
        )
        QApplication.processEvents()

        errors = []

        try:
            for stock in self.stocks:
                symbol = stock["symbol"]

                try:
                    quote = market_data.get_stock_quote(symbol)
                    self.quotes[symbol] = quote
                except Exception as error:
                    errors.append(f"{symbol}: {error}")
                    print(
                        f"Quote failed for {symbol}: {error}",
                        file=sys.stderr,
                        flush=True,
                    )

            self.render_table()
            self.update_summary()

            timestamp = datetime.now().strftime("%H:%M:%S")

            if errors:
                self.status_label.setText(
                    f"Last refresh: {timestamp}. "
                    f"{len(errors)} quote(s) failed; see terminal "
                    "for details. Existing saved stocks are unchanged."
                )
            else:
                self.status_label.setText(
                    f"Prices checked at {timestamp}. "
                    "Market data may be delayed."
                )

        except Exception as error:
            self.status_label.setText(
                f"Refresh failed: {error}"
            )
            print(
                f"Refresh failed: {error}",
                file=sys.stderr,
                flush=True,
            )

        finally:
            self.refreshing = False
            self.refresh_button.setEnabled(True)

    def render_table(self):
        self.table.setRowCount(len(self.stocks))

        for row, stock in enumerate(self.stocks):
            symbol = stock["symbol"]
            quantity = stock["quantity"]
            average_cost = stock["average_cost"]

            quote = self.quotes.get(symbol, {})
            price = quote.get("price")

            market_value = (
                price * quantity
                if price is not None
                else None
            )

            pnl = (
                market_value - average_cost * quantity
                if market_value is not None and quantity > 0
                else None
            )

            values = [
                f"{stock['company_name']} ({symbol})",
                f"{quantity:g}",
                f"₹{average_cost:,.2f}" if average_cost else "—",
                f"₹{price:,.2f}" if price is not None else "Unavailable",
                f"₹{market_value:,.2f}" if market_value is not None else "—",
                f"₹{pnl:+,.2f}" if pnl is not None else "—",
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)

                if column > 0:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter
                    )

                if column == 5 and pnl is not None:
                    if pnl > 0:
                        item.setForeground(Qt.GlobalColor.green)
                    elif pnl < 0:
                        item.setForeground(Qt.GlobalColor.red)

                self.table.setItem(row, column, item)

    def update_summary(self):
        portfolio_value = 0.0
        invested_amount = 0.0
        has_any_price = False

        for stock in self.stocks:
            quantity = stock["quantity"]
            average_cost = stock["average_cost"]
            quote = self.quotes.get(stock["symbol"], {})
            price = quote.get("price")

            if price is not None and quantity > 0:
                portfolio_value += price * quantity
                invested_amount += average_cost * quantity
                has_any_price = True

        pnl = portfolio_value - invested_amount

        value_text = (
            f"Portfolio Value\n₹{portfolio_value:,.2f}"
            if has_any_price
            else "Portfolio Value\n—"
        )

        self.value_card.setText(value_text)
        self.invested_card.setText(
            f"Invested Amount\n₹{invested_amount:,.2f}"
        )
        self.pnl_card.setText(
            f"Unrealised P&L\n₹{pnl:+,.2f}"
        )

        if pnl > 0:
            self.pnl_card.setStyleSheet(
                "color: #42d392; background-color: #222a38;"
                "border: 1px solid #354156; border-radius: 10px;"
                "padding: 15px; font-size: 15px; font-weight: bold;"
            )
        elif pnl < 0:
            self.pnl_card.setStyleSheet(
                "color: #ff707b; background-color: #222a38;"
                "border: 1px solid #354156; border-radius: 10px;"
                "padding: 15px; font-size: 15px; font-weight: bold;"
            )
        else:
            self.pnl_card.setStyleSheet("")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PortfolioUI()
    window.setWindowTitle("NSE Portfolio Tracker")
    window.resize(1400, 800)
    window.show()
    sys.exit(app.exec())
