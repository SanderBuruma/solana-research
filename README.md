# Solana Research Tool

A Python-based command-line tool for interacting with the Solana blockchain. Features include account balance checking, transaction history viewing, balance history analysis, vanity address generation, and DeFi trading summary analysis.

## Features

- **-1 <address>**: Get Account Balance
  - Input a Solana address to check its current SOL balance (displayed with 9 decimal precision).

- **-2 <address>**: View Transaction History
  - Retrieve the last 100 transactions of a Solana address.
  - Displays timestamp, transaction type, amount in SOL, from/to addresses, and USD value.

- **-3 <address>**: View Balance History
  - Analyze historical balance fluctuations of a Solana address based on its DEX trading activity.

- **-4 <pattern>**: Generate Vanity Address
  - Generate Solana addresses that match a custom regex pattern.
  - Utilizes multi-core processing, JIT compilation, and batch processing for faster generation.
  - Generates keypairs compatible with the Phantom wallet.
  - Found addresses are automatically saved to `found_addresses.txt`.

- **-5 <address> [<address> ...]**: View DeFi Summary for Wallets
  - Accept one or more wallet addresses and produce a summary table.
  - For each address, the table displays:
    - 24H ROI %
    - 7D ROI %
    - 30D ROI % and absolute 30D ROI (profit/loss in SOL)
    - Number of non-SOL swaps
    - Total number of swaps (overall DEX trading activity)

## Installation

1. Clone the repository:
```bash
git clone [your-repo-url]
cd solana-research
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
.\venv\Scripts\activate  # Windows
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

## Usage

Run the program:
```bash
.\venv\Scripts\python.exe main.py
```

### Example Commands

- Check account balance:
```bash
.\venv\Scripts\python.exe main.py -1 AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY
```

- View transaction history:
```bash
.\venv\Scripts\python.exe main.py -2 AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY
```

- View balance history:
```bash
.\venv\Scripts\python.exe main.py -3 AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY
```

- Generate vanity address:
```bash
.\venv\Scripts\python.exe main.py -4 "^Sol"
```

- View DeFi summary for multiple wallets:
```bash
.\venv\Scripts\python.exe main.py -5 walletAddr1 walletAddr2 walletAddr3
```

## Performance

The tool leverages advanced optimizations including multi-core processing, JIT compilation using Numba, and batch processing to improve performance, especially in the vanity address generator and DeFi summary calculation.

## Security

- Private keys are securely generated using Ed25519 cryptography and are saved locally in `found_addresses.txt`.
- No sensitive data is transmitted externally. Keep your private keys secure.

## Contributing

Feel free to submit issues and enhancement requests! 