
import database

# Create the database and its table
database.initialize_database()
print("Database initialized successfully.")

# Add a test stock
try:
    database.add_stock(
        symbol="RELIANCE.NS",
        company_name="Reliance Industries",
        quantity=2,
        average_cost=1400
    )
    print("Test stock added successfully.")
except Exception as error:
    print(f"Note: {error}")

# Display saved stocks
stocks = database.get_all_stocks()

print("\nStocks stored in database:")
for stock in stocks:
    print(stock)

print("\nDatabase test completed.")
