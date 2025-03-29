# Solana Research Tool

A powerful Python-based command-line tool for comprehensive analysis of Solana blockchain data. This tool helps you analyze wallets, track DEX trading activity, monitor token performance, and gather detailed information about Solana tokens and addresses.

## 🚀 Features

### 🔍 Wallet Analysis

- **-1 <address>**: Get Account Balance and Token Holdings
  - Displays current SOL balance with 9 decimal precision
  - Shows all token holdings with USD values
  - Calculates total portfolio value in SOL and USD
  - Saves balance data to CSV for historical tracking, adding one row per run

- **-2 <address>**: View Detailed Transaction History
  - Retrieves the last 100 transactions for a Solana address
  - Displays timestamp, transaction type, amount, and counterparties
  - Shows USD value of transactions at time of execution
  - Color-coded for easy identification of transaction types

- **-3 <address>**: Analyze DEX Trading History
  - Comprehensive breakdown of all DEX trading activity
  - Token-by-token profit/loss analysis
  - Detailed metrics including:
    - SOL invested and received
    - Buy/sell fees breakdown
    - Remaining token value
    - Total profit/loss calculations
    - Hold time statistics
  - Advanced filtering with the `-f` flag (see below)
  - Period-based ROI analysis (24h, 7d, 30d)
  - Filtering transactions by age with `--defi_days` parameter
  - Saves detailed reports to CSV files
  - When multiple addresses are added they are aggregated together and treated as one

- **-4 <address1>: Detect Copy Traders
  - Makes a list of copy traders and those they copy. 
  - 50 tokens recently traded by the target are analyzed 
  - A list is returned of addresses that traded the same token before or after the target.

- **-5 <address> [<address> ...]**: Comparative DeFi Summary
  - Analyze multiple wallets simultaneously
  - Read addresses from command line or text file
  - Auto-extracts Solana addresses from text using regex
  - Comparative metrics across wallets including:
    - ROI percentages (24h, 7d, 30d)
    - Win rates and median statistics
    - Fee analysis and efficiency metrics
    - Trade volume and activity levels
  - Filtering by token age with `--days` parameter
  - Filtering transactions by age with `--defi_days` parameter
  - Color-coded performance indicators
  - Exports comprehensive CSV report

- **-6 <token_address>**: Token Holder Analytics
  - Fetch detailed holder statistics for any Solana token
  - Categorized holder breakdown by wallet size
  - Analysis of token distribution and concentration
  - Whale monitoring and distribution metrics
  - Saves holder data to CSV with timestamp

- **-7 <address>**: Find Copy Trading Sources
  - Reverse of option -4: identifies wallets that the target wallet may be copying
  - Analyzes the first 10 token buys from the target wallet
  - Detects wallets that bought the same tokens within 30 seconds BEFORE the target
  - Identifies potential trading signal sources for the target wallet
  - Tracks frequency, token diversity, and timing patterns
  - Filtering transactions by age with `--defi_days` parameter
  - Quantifies the target wallet's copy trading behavior
  - Exports findings to a timestamped CSV report

- **-8 <address>**: Activity Heatmap by Day/Hour
  - Generates a 7x24 grid visualization of trading activity
  - Shows most active days and hours for trading
  - Analyzes probable timezone based on activity patterns
  - Displays intensity-based heatmap with day/hour breakdown
  - Filtering transactions by age with `--defi_days` parameter
  - Provides timezone probability analysis
  - Exports all data to CSV for further analysis

## 🛠️ Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/solana-research.git
   cd solana-research
   ```

2. **Create and activate a virtual environment:**
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # macOS/Linux
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install required packages:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   - Create a `.env` file in the project root
   - Copy the content from `.env.example` to your `.env` file
   - Add your SolScan authorization token:
     ```
     SOLSCAN_SOL_AUT=your_token_here
     ```
   - Add your BullX authentication token for option -6:
     ```
     BULLX_AUTH_TOKEN=your_token_here
     ```
   - Customize fee settings if needed:
     ```
     BUY_FIXED_FEE=0.002
     SELL_FIXED_FEE=0.002
     BUY_PERCENT_FEE=0.022912
     SELL_PERCENT_FEE=0.063
     ```

## 📋 Usage Examples

### Account Balance (-1)

Basic usage:
```bash
python main.py -1 AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY
```

### Transaction History (-2)

Basic usage:
```bash
python main.py -2 AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY
```

### DEX Trading Analysis (-3)

Basic usage:
```bash
python main.py -3 AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY
```

With time filtering:
```bash
# Filter to transactions from the last 7 days only
python main.py -3 AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY --defi_days=7
```

With token filtering:
```bash
# Show only tokens with more than 10 trades and positive ROI
python main.py -3 AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY -f "t:>10;30droip:>0"

# Show tokens with market cap > $50,000
python main.py -3 AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY -f "fmc:>50000"

# Show tokens with median hold time > 1 day (86400 seconds)
python main.py -3 AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY -f "mht:>86400"

# Multiple complex filters
python main.py -3 AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY -f "t:>5;mht:>3600;30droip:>15"
```

Display help for filtering options:
```bash
python main.py -3 AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY -f ""
```

### Copy Trader Detection (-4)

Basic usage:
```bash
python main.py -4 AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY
```

With multiple wallets:
```bash
python main.py -4 AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY BRydcUkGf88X1dAoYJVwiMHaL5hC4Vz1VbLLfX3CHXLH D2VUDgoMuRUhjizAM2jaQyrmHPeTmuCXwkKKnLvCBT32
```

With time filtering:
```bash
# Filter to transactions from the last 7 days only
python main.py -4 AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY --defi_days=7
```

Example output:
```
Potential Copy Traders of AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY
┌────────────────────────────────────┬───────────┬──────────────┬──────────────────┐
│ Wallet Address                      │ Copy Count │ Tokens       │ Avg Time Delay (s) │
├────────────────────────────────────┼───────────┼──────────────┼──────────────────┤
│ 5K3XU2uxuH962Ru2kZ3WXzgsMFZDTy7FHXZMQgowVqEA │ 7         │ 5 unique tokens │ 12.45              │
│ D4SuNZhPPArHpoH1LzrBTYgm3r3eSf3WWDoJJAGrdmXv │ 4         │ 4 unique tokens │ 6.32               │
│ 8FE27ioQh5H4HpUts2MauL1xmzUtEWnPzH9iXptVrYZZ │ 3         │ 3 unique tokens │ 18.91              │
└────────────────────────────────────┴───────────┴──────────────┴──────────────────┘

Results for AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY saved to reports/AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY/same_token_traders_2024-06-15-12-20.csv
```

This command will:
- Analyze each target wallet's first 10 token buys
- Find other wallets that bought the same tokens within 30 seconds
- Display wallets that copied more than once
- Show the number of tokens copied and average time delay
- Save results to a CSV file for each wallet for further analysis

### Find Copy Trading Sources (-7)

Basic usage:
```bash
python main.py -7 AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY
```

With time filtering:
```bash
# Filter to transactions from the last 7 days only
python main.py -7 AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY --defi_days=7
```

Example output:
```
Wallets AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY Potentially Copy Trades From
┌────────────────────────────────────┬───────────┬──────────────┬──────────────────┐
│ Wallet Address                      │ Copy Count │ Tokens       │ Avg Time Delay (s) │
├────────────────────────────────────┼───────────┼──────────────┼──────────────────┤
│ Gq7GW5ffnP3NSLdz3UG3nbuRVMm6kAe9KNcbA2QWBoPt │ 5         │ 4 unique tokens │ 7.83               │
│ 3Jbm9PYPaZ7JR9zQkxiKvFZYLjmk6MTRTNzY5cDUWE9V │ 3         │ 3 unique tokens │ 12.21              │
│ F4cHwzFsXS2mEpD9pv8R4QHGDxBq89ogx2Wt4pcnDczB │ 2         │ 2 unique tokens │ 23.15              │
└────────────────────────────────────┴───────────┴──────────────┴──────────────────┘

Results saved to reports/copy_sources_AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY_202406151345.csv
```

### Activity Heatmap (-8)

Basic usage:
```bash
python main.py -8 AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY
```

With time filtering:
```bash
# Filter to transactions from the last 7 days only
python main.py -8 AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY --defi_days=7
```

This command will:
- Generate a visual heatmap of trading activity by day and hour
- Analyze patterns to detect probable timezone
- Show most active trading periods
- Export data to CSV for additional analysis

### Multi-Wallet Analysis (-5)

Analysis for multiple addresses:
```bash
python main.py -5 AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY D2VUDgoMuRUhjizAM2jaQyrmHPeTmuCXwkKKnLvCBT32
```

Analysis from a text file with addresses:
```bash
python main.py -5 addresses.txt
```

With filtering:
```bash
# Filter tokens to those first purchased in the last 7 days
python main.py -5 AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY --days=7

# Filter transactions to the last 30 days
python main.py -5 AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY --defi_days=30

# Combine both filters
python main.py -5 AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY --days=7 --defi_days=30
```

### Token Holder Analysis (-6)

Basic usage:
```bash
python main.py -6 7LyN1qLLAVZWLcm6XscRve6SrnmbU5YtdA6axv6Rpump
```

## 🔍 Available Filters for Option -3

When using the `-3` option, you can filter tokens using the `-f` flag followed by filter criteria:

| Key     | Description                | Example                    |
|---------|----------------------------|----------------------------|
| 30droip | 30 Day ROI Percentage      | `-f "30droip:>50"`         |
| wr      | Win Rate                   | `-f "wr:>75"`              |
| mi      | Median Investment          | `-f "mi:<0.1"`             |
| ml      | Median Loss                | `-f "ml:<0.05"`            |
| mw      | Median Winnings            | `-f "mw:>0.1"`             |
| mlp     | Median Loss Percentage     | `-f "mlp:<25"`             |
| mwp     | Median Winnings Percentage | `-f "mwp:>100"`            |
| mht     | Median Hold Time (seconds) | `-f "mht:>86400"`          |
| t       | SOL Swaps Count            | `-f "t:>10"`               |
| tps     | Tokens per SOL (at invest) | `-f "tps:>1000000"`        |
| fmc     | First Market Cap           | `-f "fmc:>50000"`          |
| MC      | Market Cap                 | `-f "MC:>50000"`           |

You can combine multiple filters using semicolons:
```bash
python main.py -3 AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY -f "t:>5;30droip:>0;mht:>3600"
```

This would show only tokens with:
- More than 5 trades
- Positive 30-day ROI
- Held for more than an hour (3600 seconds)

## 📊 CSV Reports

The tool automatically generates CSV reports in the `reports/` directory:

- **Option -1**: Balance snapshot with token holdings
- **Option -3**: Detailed DEX trading history by token
- **Option -4**: Wallets potentially copy trading the target wallet
- **Option -5**: Multi-wallet comparison with performance metrics
- **Option -6**: Token holder distribution data
- **Option -7**: Wallets the target wallet potentially copy trades from
- **Option -8**: Activity heatmap data with timezone analysis

## 🔒 Security Notes

- API tokens are stored in the `.env` file and not committed to version control
- No sensitive data is transmitted outside necessary API calls
- All reports are stored locally in the `reports/` directory

## 🤝 Contributing

Contributions are welcome! Feel free to submit issues and enhancement requests.

If you find this tool useful, consider donating Solana or other tokens to:
`yWtV6SeVJkhM4vLAQsP8rBoWf6B8TZ9QvNAdApcubit`

## 📜 License

This project is released under the MIT License.