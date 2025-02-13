# Solana Research Tool

A Python-based command-line tool for interacting with Solana blockchain. Features include account balance checking, transaction history viewing, balance history analysis, and vanity address generation.

## Features

- **Account Balance**: Check the SOL balance of any Solana address
- **Transaction History**: View detailed transaction history with timestamps, amounts, and USD values
- **Balance History**: Analyze historical balance changes over time
- **Vanity Address Generator**: Generate Solana addresses matching custom patterns
  - Multi-core processing for faster generation
  - Phantom wallet compatible keypair format
  - Regex pattern support
  - Progress tracking and statistics
  - Auto-saves found addresses

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

### Main Menu Options

1. **Get Account Balance**
   - Enter a Solana address to check its current SOL balance
   - Displays balance with 9 decimal precision

2. **View Transaction History**
   - Enter a Solana address to view its transaction history
   - Shows last 100 transactions with:
     - Timestamp
     - Transaction type
     - Amount (SOL)
     - From/To addresses
     - USD value

3. **View Balance History**
   - Enter a Solana address to see balance changes over time
   - Displays:
     - Historical balance changes
     - Transaction timestamps
     - Running balance
     - Current balance

4. **Generate Vanity Address**
   - Create Solana addresses matching a custom pattern
   - Supports regular expressions (regex)
   - Pattern Examples:
     - End pattern: 'abc$'
     - Start pattern: '^abc'
     - Numbers: '\d{3}'
     - Letters: '[a-f]{4}'
     - Complex: 'abc.*xyz'
   - Found addresses are saved to `found_addresses.txt`
   - Generated private keys are compatible with Phantom wallet

### Example Patterns

- `^Sol` - Address starting with "Sol"
- `[0-9]{3}$` - Address ending with 3 numbers
- `^[A-Z]{4}` - Address starting with 4 uppercase letters
- `abc.*xyz` - Address containing "abc" followed by "xyz"

## Performance

The vanity address generator utilizes:
- Multi-core processing
- JIT compilation
- Batch processing
- Optimized pattern matching

Performance varies based on:
- Pattern complexity
- CPU cores available
- System resources

## Security

- Private keys are generated securely using Ed25519 cryptography
- Keys are saved locally in `found_addresses.txt`
- No sensitive data is transmitted externally
- API calls are made only to public Solscan endpoints

## Dependencies

- `pynacl`: Ed25519 cryptography
- `base58`: Address encoding
- `rich`: Terminal UI
- `requests`: API communication
- `numpy`: Numerical operations
- `numba`: JIT compilation

## Notes

- Keep your private keys secure and never share them
- Generated addresses are fully compatible with Phantom wallet
- The tool respects Solscan API rate limits
- Progress can be interrupted safely with Ctrl+C

## Contributing

Feel free to submit issues and enhancement requests! 