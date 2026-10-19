
import sqlite3
from pathlib import Path


# Store portfolio data in the Windows user directory.
APP_DIR = Path.home() / "NSEPortfolioTracker"
APP_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = APP_DIR / "portfolio.db"


def get_connection():
    """Create and return a SQLite database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    """Create the stocks table if it does not already exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL UNIQUE,
                company_name TEXT NOT NULL,
                quantity REAL NOT NULL DEFAULT 0,
                average_cost REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)


def add_stock(symbol, company_name, quantity=0, average_cost=0):
    """Add a stock to the portfolio or watchlist."""
    symbol = symbol.strip().upper()
    company_name = company_name.strip()

    if not symbol:
        raise ValueError("Stock symbol cannot be empty.")

    if not company_name:
        raise ValueError("Company name cannot be empty.")

    if quantity < 0:
        raise ValueError("Quantity cannot be negative.")

    if average_cost < 0:
        raise ValueError("Average cost cannot be negative.")

    if quantity > 0 and average_cost <= 0:
        raise ValueError(
            "Average cost must be positive for owned holdings."
        )

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO stocks (
                symbol,
                company_name,
                quantity,
                average_cost
            )
            VALUES (?, ?, ?, ?)
        """, (
            symbol,
            company_name,
            quantity,
            average_cost
        ))


def get_all_stocks():
    """Return all saved stocks as a list of dictionaries."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                id,
                symbol,
                company_name,
                quantity,
                average_cost,
                created_at
            FROM stocks
            ORDER BY company_name COLLATE NOCASE
        """).fetchall()

        return [dict(row) for row in rows]


def get_stock_by_symbol(symbol):
    """Return one stock by its symbol, or None if not found."""
    symbol = symbol.strip().upper()

    with get_connection() as conn:
        row = conn.execute("""
            SELECT *
            FROM stocks
            WHERE symbol = ?
        """, (symbol,)).fetchone()

        return dict(row) if row else None


def remove_stock(stock_id):
    """Delete a stock using its database ID."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM stocks WHERE id = ?",
            (stock_id,)
        )

        return cursor.rowcount > 0


def update_holding(stock_id, quantity, average_cost):
    """Update the quantity and average purchase price."""
    if quantity < 0:
        raise ValueError("Quantity cannot be negative.")

    if average_cost < 0:
        raise ValueError("Average cost cannot be negative.")

    if quantity > 0 and average_cost <= 0:
        raise ValueError(
            "Average cost must be positive for owned holdings."
        )

    with get_connection() as conn:
        cursor = conn.execute("""
            UPDATE stocks
            SET quantity = ?,
                average_cost = ?
            WHERE id = ?
        """, (
            quantity,
            average_cost,
            stock_id
        ))

        return cursor.rowcount > 0


if __name__ == "__main__":
    initialize_database()

    print("Database initialized successfully.")
    print(f"Database location: {DB_PATH}")
    print(f"Saved stocks: {len(get_all_stocks())}")

    for stock in get_all_stocks():
        print(
            f"{stock['symbol']} | "
            f"{stock['company_name']} | "
            f"Quantity: {stock['quantity']} | "
            f"Average cost: ₹{stock['average_cost']:.2f}"
        )
