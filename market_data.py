
import yfinance as yf


def normalize_symbol(symbol: str) -> str:
    """Convert a bare NSE ticker into Yahoo Finance format."""
    symbol = symbol.strip().upper()

    if not symbol:
        raise ValueError("Stock symbol cannot be empty.")

    if not symbol.endswith((".NS", ".BO")):
        symbol += ".NS"

    return symbol


def get_stock_quote(symbol: str) -> dict:
    """
    Return the latest available quote.
    Yahoo Finance data may be delayed or unavailable.
    """
    symbol = normalize_symbol(symbol)
    ticker = yf.Ticker(symbol)

    price = None
    previous_close = None

    try:
        info = ticker.fast_info
        price = info.get("lastPrice")
        previous_close = info.get("previousClose")
    except Exception:
        pass

    # Fallback if fast_info does not provide enough data.
    if price is None:
        history = ticker.history(
            period="5d",
            interval="1d",
            auto_adjust=False
        )

        if history.empty:
            raise ValueError(
                f"No price data found for {symbol}. "
                "Check the ticker or try again later."
            )

        price = float(history["Close"].iloc[-1])

        if previous_close is None and len(history) >= 2:
            previous_close = float(history["Close"].iloc[-2])

    price = float(price)

    if previous_close is not None:
        previous_close = float(previous_close)

    change_percent = None

    if previous_close and previous_close != 0:
        change_percent = (
            (price - previous_close) / previous_close
        ) * 100

    return {
        "symbol": symbol,
        "price": price,
        "previous_close": previous_close,
        "change_percent": change_percent,
    }


if __name__ == "__main__":
    symbol = input("Enter an NSE stock symbol: ")

    try:
        quote = get_stock_quote(symbol)
        print("\nQuote received:")
        print(f"Symbol: {quote['symbol']}")
        print(f"Latest available price: ₹{quote['price']:.2f}")

        if quote["previous_close"] is not None:
            print(
                f"Previous close: "
                f"₹{quote['previous_close']:.2f}"
            )

        if quote["change_percent"] is not None:
            print(
                f"Change vs previous close: "
                f"{quote['change_percent']:+.2f}%"
            )

    except Exception as error:
        print(f"Unable to fetch quote: {error}")
