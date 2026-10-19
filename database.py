
import sqlite3
from pathlib import Path

APP_DIR = Path.home() / "NSEPortfolioTracker"
APP_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = APP_DIR / "portfolio.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS portfolios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create the new schema if this is a fresh database.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                company_name TEXT NOT NULL,
                quantity REAL NOT NULL DEFAULT 0,
                average_cost REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                portfolio_id INTEGER
            )
        """)

        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(stocks)").fetchall()
        }

        # Add portfolio_id to databases created by the original app.
        if "portfolio_id" not in columns:
            conn.execute("ALTER TABLE stocks ADD COLUMN portfolio_id INTEGER")

        # Ensure the default portfolio exists.
        default = conn.execute(
            "SELECT id FROM portfolios WHERE name = ?",
            ("My Portfolio",)
        ).fetchone()

        if default:
            default_id = default["id"]
        else:
            cursor = conn.execute(
                "INSERT INTO portfolios (name) VALUES (?)",
                ("My Portfolio",)
            )
            default_id = cursor.lastrowid

        # Existing holdings are assigned to My Portfolio.
        conn.execute(
            "UPDATE stocks SET portfolio_id = ? WHERE portfolio_id IS NULL",
            (default_id,)
        )

        # Remove the old global UNIQUE(symbol) constraint if it exists.
        # This lets the same stock exist in multiple portfolios.
        indexes = conn.execute("PRAGMA index_list(stocks)").fetchall()
        has_global_symbol_unique = False

        for index in indexes:
            if not index["unique"]:
                continue
            index_columns = conn.execute(
                f"PRAGMA index_info('{index['name']}')"
            ).fetchall()
            names = [col["name"] for col in index_columns]
            if names == ["symbol"]:
                has_global_symbol_unique = True
                break

        if has_global_symbol_unique:
            conn.execute("""
                CREATE TABLE stocks_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    company_name TEXT NOT NULL,
                    quantity REAL NOT NULL DEFAULT 0,
                    average_cost REAL NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    portfolio_id INTEGER
                )
            """)

            conn.execute("""
                INSERT INTO stocks_new
                    (id, symbol, company_name, quantity, average_cost,
                     created_at, portfolio_id)
                SELECT id, symbol, company_name, quantity, average_cost,
                       created_at, portfolio_id
                FROM stocks
            """)

            conn.execute("DROP TABLE stocks")
            conn.execute("ALTER TABLE stocks_new RENAME TO stocks")

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_stocks_portfolio
            ON stocks(portfolio_id)
        """)
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_stocks_portfolio_symbol
            ON stocks(portfolio_id, symbol)
        """)


def get_all_portfolios():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, name, created_at
            FROM portfolios
            ORDER BY name COLLATE NOCASE
        """).fetchall()
        return [dict(row) for row in rows]


def add_portfolio(name):
    name = name.strip()
    if not name:
        raise ValueError("Enter a portfolio name.")
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO portfolios (name) VALUES (?)",
            (name,)
        )
        return cursor.lastrowid


def rename_portfolio(portfolio_id, name):
    name = name.strip()
    if not name:
        raise ValueError("Enter a portfolio name.")
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE portfolios SET name = ? WHERE id = ?",
            (name, portfolio_id)
        )
        return cursor.rowcount > 0


def remove_portfolio(portfolio_id):
    with get_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM portfolios"
        ).fetchone()["n"]

        if count <= 1:
            raise ValueError("At least one portfolio must remain.")

        conn.execute(
            "DELETE FROM stocks WHERE portfolio_id = ?",
            (portfolio_id,)
        )
        cursor = conn.execute(
            "DELETE FROM portfolios WHERE id = ?",
            (portfolio_id,)
        )
        return cursor.rowcount > 0


def add_stock(symbol, company_name, quantity=0, average_cost=0,
              portfolio_id=None):
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
        raise ValueError("Average cost must be greater than zero.")

    with get_connection() as conn:
        if portfolio_id is None:
            row = conn.execute(
                "SELECT id FROM portfolios ORDER BY id LIMIT 1"
            ).fetchone()
            if row is None:
                cursor = conn.execute(
                    "INSERT INTO portfolios (name) VALUES (?)",
                    ("My Portfolio",)
                )
                portfolio_id = cursor.lastrowid
            else:
                portfolio_id = row["id"]

        conn.execute("""
            INSERT INTO stocks
                (symbol, company_name, quantity, average_cost, portfolio_id)
            VALUES (?, ?, ?, ?, ?)
        """, (symbol, company_name, quantity, average_cost, portfolio_id))


def get_all_stocks(portfolio_id=None):
    with get_connection() as conn:
        if portfolio_id is None:
            rows = conn.execute("""
                SELECT id, symbol, company_name, quantity, average_cost,
                       created_at, portfolio_id
                FROM stocks
                ORDER BY company_name COLLATE NOCASE
            """).fetchall()
        else:
            rows = conn.execute("""
                SELECT id, symbol, company_name, quantity, average_cost,
                       created_at, portfolio_id
                FROM stocks
                WHERE portfolio_id = ?
                ORDER BY company_name COLLATE NOCASE
            """, (portfolio_id,)).fetchall()

        return [dict(row) for row in rows]


def get_stock_by_symbol(symbol, portfolio_id=None):
    symbol = symbol.strip().upper()
    with get_connection() as conn:
        if portfolio_id is None:
            row = conn.execute(
                "SELECT * FROM stocks WHERE symbol = ? ORDER BY id LIMIT 1",
                (symbol,)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM stocks WHERE symbol = ? AND portfolio_id = ?",
                (symbol, portfolio_id)
            ).fetchone()

        return dict(row) if row else None


def remove_stock(stock_id):
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM stocks WHERE id = ?",
            (stock_id,)
        )
        return cursor.rowcount > 0


def update_holding(stock_id, quantity, average_cost):
    if quantity < 0 or average_cost < 0:
        raise ValueError("Quantity and average cost cannot be negative.")
    if quantity > 0 and average_cost <= 0:
        raise ValueError("Average cost must be greater than zero.")

    with get_connection() as conn:
        cursor = conn.execute("""
            UPDATE stocks
            SET quantity = ?, average_cost = ?
            WHERE id = ?
        """, (quantity, average_cost, stock_id))
        return cursor.rowcount > 0


if __name__ == "__main__":
    initialize_database()
    print("Database initialized successfully.")
    print(f"Database: {DB_PATH}")
    for portfolio in get_all_portfolios():
        print(f"\n{portfolio['name']}:")
        for stock in get_all_stocks(portfolio["id"]):
            print(
                f"  {stock['symbol']} | {stock['company_name']} | "
                f"Quantity: {stock['quantity']} | "
                f"Average cost: ₹{stock['average_cost']:.2f}"
            )
