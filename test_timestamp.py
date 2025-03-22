import time
from datetime import datetime, timedelta
from utils.solscan import SolscanAPI

# Create API instance
api = SolscanAPI()

# Set a test address - using a more active Solana address for better results
test_address = "AyhPRvf8EuGRtm49ZnNNAgQ9yBvLJJfQd9xTuhWY2mv"  # Solana: more active address

# Calculate timestamps for a specific date range (e.g., last 30 days)
now = datetime.now()
thirty_days_ago = now - timedelta(days=30)
from_time = int(thirty_days_ago.timestamp())
to_time = int(now.timestamp())

print(f"Fetching DEX trading history for address: {test_address}")
print(f"From: {datetime.fromtimestamp(from_time).strftime('%Y-%m-%d %H:%M:%S')}")
print(f"To: {datetime.fromtimestamp(to_time).strftime('%Y-%m-%d %H:%M:%S')}")

# Call the method with timestamp parameters
print("Calling get_dex_trading_history with timestamp parameters...")
trades = api.get_dex_trading_history(
    address=test_address,
    from_time=from_time,
    to_time=to_time
)

# Display results
print(f"\nFound {len(trades)} trades in the specified time range.")

if trades:
    print("\nSample of trades found:")
    for i, trade in enumerate(trades[:5]):  # Show first 5 trades
        trade_time = datetime.fromtimestamp(trade.block_time)
        print(f"{i+1}. {trade_time.strftime('%Y-%m-%d %H:%M:%S')} - Token1: {trade.token1[:8]}... Token2: {trade.token2[:8]}...")
else:
    print("\nNo trades found. Test with another address or wider date range if needed.")

# Also test without timestamp parameters for comparison
print("\n---------------------")
print("Testing without timestamp parameters:")
regular_trades = api.get_dex_trading_history(
    address=test_address
)
print(f"Found {len(regular_trades)} trades without timestamp filtering.") 