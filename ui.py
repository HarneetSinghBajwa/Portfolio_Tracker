
import sys
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QDialog, QFormLayout, QDoubleSpinBox,
    QDialogButtonBox, QAbstractItemView, QComboBox, QInputDialog
)

import database
import market_data


class AddStockDialog(QDialog):
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
        self.company_input.setPlaceholderText("Company name")
        form.addRow("Company name:", self.company_input)

        self.quantity_input = QDoubleSpinBox()
        self.quantity_input.setRange(0, 1000000000)
        self.quantity_input.setDecimals(4)
        form.addRow("Quantity owned:", self.quantity_input)

        self.cost_input = QDoubleSpinBox()
        self.cost_input.setRange(0, 100000000)
        self.cost_input.setDecimals(2)
        self.cost_input.setPrefix("₹ ")
        form.addRow("Average cost per share:", self.cost_input)

        layout.addLayout(form)

        note = QLabel(
            "Use quantity 0 for a watchlist entry. "
            "For owned shares, enter quantity and average purchase price."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.validate_form)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def validate_form(self):
        if not self.symbol_input.text().strip():
            QMessageBox.warning(self, "Missing symbol", "Enter a stock symbol.")
            return

        if self.quantity_input.value() > 0 and self.cost_input.value() <= 0:
            QMessageBox.warning(
                self, "Missing cost",
                "Enter an average purchase price greater than zero."
            )
            return

        self.accept()


class PortfolioUI(QWidget):
    def __init__(self):
        super().__init__()

        database.initialize_database()
        self.stocks = []
        self.quotes = {}
        self.current_portfolio_id = None
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
                color: white;
            }
            QLabel#subtitle { color: #aab5c5; }
            QLabel.summary {
                background-color: #222a38;
                border: 1px solid #354156;
                border-radius: 10px;
                padding: 15px;
                font-size: 15px;
                font-weight: bold;
            }
            QLineEdit, QComboBox, QDoubleSpinBox {
                background-color: #222a38;
                border: 1px solid #3a465a;
                border-radius: 6px;
                padding: 9px;
                color: white;
            }
            QPushButton {
                background-color: #2864dc;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #3978f0; }
            QPushButton:disabled { background-color: #526078; }
            QPushButton#removeButton { background-color: #9f303b; }
            QPushButton#secondaryButton { background-color: #45536a; }
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
                color: white;
                padding: 10px;
                border: none;
                font-weight: bold;
            }
            QDialog { background-color: #151922; }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 16)
        root.setSpacing(13)

        heading = QLabel("NSE Portfolio Tracker")
        heading.setObjectName("heading")
        root.addWidget(heading)

        subtitle = QLabel(
            "Manage separate portfolios and track their performance."
        )
        subtitle.setObjectName("subtitle")
        root.addWidget(subtitle)

        # Portfolio selection
        portfolio_row = QHBoxLayout()
        portfolio_row.addWidget(QLabel("Active portfolio:"))

        self.portfolio_combo = QComboBox()
        self.portfolio_combo.setMinimumWidth(220)
        self.portfolio_combo.currentIndexChanged.connect(
            self.change_portfolio
        )
        portfolio_row.addWidget(self.portfolio_combo)

        self.add_portfolio_button = QPushButton("+ Add Portfolio")
        self.add_portfolio_button.clicked.connect(self.add_portfolio)
        portfolio_row.addWidget(self.add_portfolio_button)

        self.rename_button = QPushButton("Rename")
        self.rename_button.setObjectName("secondaryButton")
        self.rename_button.clicked.connect(self.rename_portfolio)
        portfolio_row.addWidget(self.rename_button)

        self.delete_portfolio_button = QPushButton("Delete Portfolio")
        self.delete_portfolio_button.setObjectName("removeButton")
        self.delete_portfolio_button.clicked.connect(self.delete_portfolio)
        portfolio_row.addWidget(self.delete_portfolio_button)

        portfolio_row.addStretch()
        root.addLayout(portfolio_row)

        # Summary cards
        summary = QGridLayout()
        summary.setSpacing(14)

        self.value_card = QLabel("Portfolio Value\n—")
        self.invested_card = QLabel("Invested Amount\n₹0.00")
        self.pnl_card = QLabel("Unrealised P&L\n₹0.00")

        for card in (
            self.value_card, self.invested_card, self.pnl_card
        ):
            card.setProperty("class", "summary")
            card.setMinimumHeight(70)
            card.setAlignment(
                Qt.AlignmentFlag.AlignLeft |
                Qt.AlignmentFlag.AlignVCenter
            )

        summary.addWidget(self.value_card, 0, 0)
        summary.addWidget(self.invested_card, 0, 1)
        summary.addWidget(self.pnl_card, 0, 2)
        root.addLayout(summary)

        # Stock actions
        actions = QHBoxLayout()

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
            "Stock", "Quantity", "Average Cost",
            "Current Price", "Market Value", "Profit / Loss"
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
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 6):
            header.setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents
            )

        root.addWidget(self.table, 1)

        self.status_label = QLabel("Ready.")
        self.status_label.setObjectName("subtitle")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.load_portfolios()

        self.timer = QTimer(self)
        self.timer.setInterval(60000)
        self.timer.timeout.connect(self.refresh_prices)
        self.timer.start()

    def load_portfolios(self, select_id=None):
        portfolios = database.get_all_portfolios()

        if not portfolios:
            database.add_portfolio("My Portfolio")
            portfolios = database.get_all_portfolios()

        self.portfolio_combo.blockSignals(True)
        self.portfolio_combo.clear()

        for portfolio in portfolios:
            self.portfolio_combo.addItem(
                portfolio["name"], portfolio["id"]
            )

        target_id = (
            select_id
            if select_id is not None
            else self.current_portfolio_id
        )

        selected_index = 0
        for index in range(self.portfolio_combo.count()):
            if self.portfolio_combo.itemData(index) == target_id:
                selected_index = index
                break

        self.portfolio_combo.setCurrentIndex(selected_index)
        self.portfolio_combo.blockSignals(False)

        self.current_portfolio_id = self.portfolio_combo.currentData()
        self.update_portfolio_buttons()
        self.load_stocks()
        QTimer.singleShot(200, self.refresh_prices)

    def update_portfolio_buttons(self):
        self.delete_portfolio_button.setEnabled(
            self.portfolio_combo.count() > 1
        )

    def change_portfolio(self, index):
        if index < 0:
            return

        portfolio_id = self.portfolio_combo.itemData(index)
        if portfolio_id == self.current_portfolio_id:
            return

        self.current_portfolio_id = portfolio_id
        self.quotes.clear()
        self.load_stocks()
        self.update_portfolio_buttons()
        self.status_label.setText(
            f"Switched to {self.portfolio_combo.currentText()}."
        )
        self.refresh_prices()

    def add_portfolio(self):
        name, ok = QInputDialog.getText(
            self, "Add Portfolio", "Enter a portfolio name:"
        )
        if not ok:
            return

        name = name.strip()
        if not name:
            QMessageBox.warning(
                self, "Invalid name", "Portfolio name cannot be empty."
            )
            return

        try:
            portfolio_id = database.add_portfolio(name)
            self.quotes.clear()
            self.current_portfolio_id = portfolio_id
            self.load_portfolios(select_id=portfolio_id)
            self.status_label.setText(f"Created portfolio: {name}")
        except Exception as error:
            QMessageBox.warning(
                self, "Could not add portfolio",
                f"Use a name that is not already taken.\n\n{error}"
            )

    def rename_portfolio(self):
        portfolio_id = self.current_portfolio_id
        if portfolio_id is None:
            return

        old_name = self.portfolio_combo.currentText()
        name, ok = QInputDialog.getText(
            self, "Rename Portfolio",
            "New portfolio name:", text=old_name
        )
        if not ok:
            return

        try:
            database.rename_portfolio(portfolio_id, name)
            self.load_portfolios(select_id=portfolio_id)
            self.status_label.setText(f"Portfolio renamed to {name.strip()}.")
        except Exception as error:
            QMessageBox.warning(
                self, "Rename failed",
                f"Enter a unique, non-empty name.\n\n{error}"
            )

    def delete_portfolio(self):
        if self.portfolio_combo.count() <= 1:
            QMessageBox.information(
                self, "Cannot delete",
                "At least one portfolio must remain."
            )
            return

        portfolio_id = self.current_portfolio_id
        name = self.portfolio_combo.currentText()

        answer = QMessageBox.question(
            self, "Delete Portfolio",
            f"Delete '{name}' and all its stocks?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            database.remove_portfolio(portfolio_id)
            self.quotes.clear()
            self.current_portfolio_id = None
            self.load_portfolios()
            self.status_label.setText(f"Deleted portfolio: {name}")
        except Exception as error:
            QMessageBox.warning(
                self, "Delete failed", str(error)
            )

    def add_stock(self):
        dialog = AddStockDialog(self)

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

            database.add_stock(
                symbol,
                company or symbol,
                quantity,
                average_cost,
                portfolio_id=self.current_portfolio_id
            )

            self.search_input.clear()
            self.load_stocks()
            self.status_label.setText(
                f"Added {symbol} to {self.portfolio_combo.currentText()}."
            )
            self.refresh_prices()

        except Exception as error:
            QMessageBox.warning(
                self, "Could not add stock",
                f"Could not add {raw_symbol} to this portfolio.\n\n{error}"
            )

    def load_stocks(self):
        self.stocks = database.get_all_stocks(
            self.current_portfolio_id
        )
        self.render_table()
        self.update_summary()

    def remove_selected(self):
        row = self.table.currentRow()

        if row < 0 or row >= len(self.stocks):
            QMessageBox.information(
                self, "Select a stock",
                "Select a stock row first."
            )
            return

        stock = self.stocks[row]
        answer = QMessageBox.question(
            self, "Remove Stock",
            f"Remove {stock['symbol']} from this portfolio?",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        database.remove_stock(stock["id"])
        self.quotes.pop(stock["symbol"], None)
        self.load_stocks()
        self.status_label.setText(f"Removed {stock['symbol']}.")

    def refresh_prices(self):
        if self.refreshing:
            return

        if not self.stocks:
            self.render_table()
            self.update_summary()
            self.status_label.setText(
                f"{self.portfolio_combo.currentText()}: no stocks yet."
            )
            return

        self.refreshing = True
        self.refresh_button.setEnabled(False)
        self.status_label.setText("Fetching latest available prices...")
        QApplication.processEvents()

        errors = []

        try:
            for stock in self.stocks:
                symbol = stock["symbol"]
                try:
                    self.quotes[symbol] = market_data.get_stock_quote(symbol)
                except Exception as error:
                    errors.append(symbol)
                    print(
                        f"Quote failed for {symbol}: {error}",
                        file=sys.stderr,
                        flush=True
                    )

            self.render_table()
            self.update_summary()
            stamp = datetime.now().strftime("%H:%M:%S")

            if errors:
                self.status_label.setText(
                    f"Checked at {stamp}; failed quotes: "
                    f"{', '.join(errors)}. See terminal for details."
                )
            else:
                self.status_label.setText(
                    f"{self.portfolio_combo.currentText()} | "
                    f"Prices checked at {stamp}. Data may be delayed."
                )

        except Exception as error:
            self.status_label.setText(f"Refresh failed: {error}")
            print(error, file=sys.stderr, flush=True)

        finally:
            self.refreshing = False
            self.refresh_button.setEnabled(True)

    def render_table(self):
        self.table.setRowCount(len(self.stocks))

        for row, stock in enumerate(self.stocks):
            symbol = stock["symbol"]
            quantity = stock["quantity"]
            cost = stock["average_cost"]
            quote = self.quotes.get(symbol, {})
            price = quote.get("price")

            market_value = (
                price * quantity if price is not None else None
            )
            pnl = (
                market_value - cost * quantity
                if market_value is not None and quantity > 0
                else None
            )

            values = [
                f"{stock['company_name']} ({symbol})",
                f"{quantity:g}",
                f"₹{cost:,.2f}" if cost else "—",
                f"₹{price:,.2f}" if price is not None else "Unavailable",
                f"₹{market_value:,.2f}" if market_value is not None else "—",
                f"₹{pnl:+,.2f}" if pnl is not None else "—",
            ]

            for col, value in enumerate(values):
                item = QTableWidgetItem(value)

                if col > 0:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight |
                        Qt.AlignmentFlag.AlignVCenter
                    )

                if col == 5 and pnl is not None:
                    if pnl > 0:
                        item.setForeground(Qt.GlobalColor.green)
                    elif pnl < 0:
                        item.setForeground(Qt.GlobalColor.red)

                self.table.setItem(row, col, item)

    def update_summary(self):
        value = 0.0
        invested = 0.0
        has_price = False

        for stock in self.stocks:
            quantity = stock["quantity"]
            cost = stock["average_cost"]
            price = self.quotes.get(stock["symbol"], {}).get("price")

            if price is not None and quantity > 0:
                value += price * quantity
                invested += cost * quantity
                has_price = True

        pnl = value - invested

        self.value_card.setText(
            f"Portfolio Value\n₹{value:,.2f}"
            if has_price else "Portfolio Value\n—"
        )
        self.invested_card.setText(
            f"Invested Amount\n₹{invested:,.2f}"
        )
        self.pnl_card.setText(
            f"Unrealised P&L\n₹{pnl:+,.2f}"
        )

        color = (
            "#42d392" if pnl > 0
            else "#ff707b" if pnl < 0
            else "#edf2f7"
        )
        self.pnl_card.setStyleSheet(
            f"color: {color}; background-color: #222a38;"
            "border: 1px solid #354156; border-radius: 10px;"
            "padding: 15px; font-size: 15px; font-weight: bold;"
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = QDialog()
    window.setWindowTitle("NSE Portfolio Tracker")
    window.resize(1400, 820)

    layout = QVBoxLayout(window)
    layout.addWidget(PortfolioUI())

    window.show()
    sys.exit(app.exec())
