from rich.console import Console
from datetime import datetime, timedelta
from dotenv import load_dotenv
from rich.table import Table
import os
import sys
import re
import csv
import cloudscraper
import json
from rich.markdown import Markdown
from rich.panel import Panel

from utils.solscan import SolscanAPI, analyze_trades, display_transactions_table, filter_token_stats, format_token_address, format_token_amount, format_number_for_csv

def format_number_for_csv(number: float) -> str:
    """Format a number with comma as decimal separator for CSV files."""
    if isinstance(number, (int, float)):
        # Always use 2 decimal places for non-integer numbers
        return f"{number:.2f}".replace('.', ',')
    return str(number)

def update_stats_csv(timestamp: str, address: str, roi_data: dict, tx_summary: dict, token_data: list, console: Console) -> None:
    """
    Update or create stats.csv with trading statistics for a wallet.
    
    Args:
        timestamp (str): Current timestamp in yyyy-mm-dd:hh-mm format
        address (str): Wallet address
        roi_data (dict): ROI data from analyze_trades
        tx_summary (dict): Transaction summary from analyze_trades
        token_data (list): Token data from analyze_trades
        console (Console): Rich console for output
    """
    stats_file = 'reports/stats.csv'
    fieldnames = [
        'Timestamp', 'Address', '24H ROI %', '7D ROI %', '30D ROI %', '60D ROI %', 
        '60D ROI', 'Win Rate', 'Unique Tokens Traded', 'Median Investment', 
        'Med ROI %', 'ROI % Std Dev', 'Median Hold Time', 'Median Market Entry', 'Median Market Cap % at Entry'
    ]
    
    # Create reports directory if it doesn't exist
    os.makedirs('reports', exist_ok=True)
    
    # Count unique tokens
    unique_tokens = len(set(token['address'] for token in token_data))
    
    # Prepare row data
    row_data = {
        'Timestamp': timestamp,
        'Address': address,
        '24H ROI %': format_number_for_csv(roi_data['24h']['roi_percent']) if roi_data['24h']['roi_percent'] is not None else "N/A",
        '7D ROI %': format_number_for_csv(roi_data['7d']['roi_percent']) if roi_data['7d']['roi_percent'] is not None else "N/A",
        '30D ROI %': format_number_for_csv(roi_data['30d']['roi_percent']) if roi_data['30d']['roi_percent'] is not None else "N/A",
        '60D ROI %': format_number_for_csv(roi_data['60d']['roi_percent']) if roi_data['60d']['roi_percent'] is not None else "N/A",
        '60D ROI': format_number_for_csv(roi_data['60d']['profit']),
        'Win Rate': format_number_for_csv(tx_summary['win_rate']),
        'Unique Tokens Traded': str(unique_tokens),
        'Median Investment': format_number_for_csv(tx_summary['median_investment']),
        'Med ROI %': format_number_for_csv(tx_summary['median_roi_percent']),
        'ROI % Std Dev': format_number_for_csv(tx_summary['roi_std_dev']),
        'Median Hold Time': format_seconds(tx_summary['median_hold_time']),
        'Median Market Entry': format_mc(tx_summary['median_market_entry']),
        'Median Market Cap % at Entry': format_number_for_csv(tx_summary['median_mc_percentage'])
    }
    
    try:
        # Read existing data if file exists
        existing_data = []
        if os.path.exists(stats_file):
            with open(stats_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')  # Using semicolon for LibreOffice compatibility
                existing_data = list(reader)
        
        # Update or add new row
        updated = False
        for row in existing_data:
            if row['Address'] == address:
                row.update(row_data)
                updated = True
                break
        
        if not updated:
            existing_data.append(row_data)
        
        # Write all data back to file
        with open(stats_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')  # Using semicolon for LibreOffice compatibility
            writer.writeheader()
            writer.writerows(existing_data)
        
        console.print(f"[green]Updated stats.csv with data for {address}[/green]")
        
    except Exception as e:
        console.print(f"[red]Error updating stats.csv: {str(e)}[/red]")
        raise e

def get_addresses_from_args(args) -> list[str]:
    """
    Get addresses from command line arguments.
    
    Args:
        args (List[str]): Command line arguments

    """
    args = sys.argv[2:]
    addresses = []
    for arg in args:
        # find all matches of the regex pattern in each arg
        m = re.findall(r'[a-zA-Z0-9]{43,44}', arg)
        if m:
            print(f"Found {len(m)} addresses in {arg}")
            addresses.extend(m)

    # Deduplicate addresses
    return list(set(addresses))

def generate_aggregate_filename(addresses, file_type, include_timestamp=True, batch_idx=None, include_timestamp_str=True):
    """
    Generate a standardized filename for aggregate results based on wallet addresses.
    
    Args:
        addresses (List[str]): List of wallet addresses to process
        file_type (str): Type of the file (e.g., 'dex-trades', 'balance', 'option5')
        include_timestamp (bool): Whether to include timestamp in filename
        batch_idx (int, optional): Batch index number, if applicable
        include_timestamp_str (bool, optional): Whether to include timestamp string in filename
        
    Returns:
        str: Path to the aggregate file
    """
    # Extract first two characters from each address
    prefixes = []
    for addr in addresses:
        if len(addr) >= 2:  # Ensure address is long enough
            prefixes.append(addr[:2])
    
    # Sort and join the prefixes with hyphens
    prefix_str = "-".join(sorted(prefixes)) if prefixes else "unknown"
    
    # Generate timestamp if needed
    timestamp_str = ""
    if include_timestamp:
        timestamp_str = f"-{datetime.now().strftime('%Y-%m-%d-%H-%M')}"
    
    # Add batch info if provided
    batch_str = ""
    if batch_idx is not None:
        batch_str = f"-batch{batch_idx}"
    
    # Create reports directory if it doesn't exist
    os.makedirs("reports", exist_ok=True)
    
    if include_timestamp_str:
        return f"reports/aggregate-{prefix_str}-{file_type}{batch_str}{timestamp_str}.csv"
    else:
        return f"reports/aggregate-{prefix_str}-{file_type}{batch_str}.csv"

def is_sol_token(token: str) -> bool:
    """Check if a token address is SOL"""
    SOL_ADDRESSES = {
        "So11111111111111111111111111111111111111112",
        "So11111111111111111111111111111111111111111"
    }
    return token in SOL_ADDRESSES
    

def format_mc(mc):
    """Format a market cap value with appropriate suffix and return the formatted string."""
    if mc >= 1_000_000_000:
        return f"{mc/1_000_000_000:.1f}".replace('.', ',') + "B"
    elif mc >= 1_000_000:
        return f"{mc/1_000_000:.1f}".replace('.', ',') + "M"
    elif mc >= 1_000:
        return f"{mc/1_000:.1f}".replace('.', ',') + "K"
    else:
        return f"{mc:.1f}".replace('.', ',')

def format_seconds(seconds):
    """Format seconds into a human-readable string (days, hours, minutes, seconds)."""
    seconds_td = timedelta(seconds=seconds)
    if seconds_td.days > 0:
        return f"{seconds_td.days}d {seconds_td.seconds//3600}h {(seconds_td.seconds%3600)//60}m"
    elif seconds_td.seconds//3600 > 0:
        return f"{seconds_td.seconds//3600}h {(seconds_td.seconds%3600)//60}m"
    else:
        return f"{(seconds_td.seconds%3600)//60}m {seconds_td.seconds%60}s"

def print_usage():
    """
    Display the README.md file with nice formatting in the terminal, but without emoji icons
    """
    console = Console()
    
    # Get the path to README.md relative to the script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    readme_path = os.path.join(script_dir, "README.md")
    
    # Read the README file
    with open(readme_path, 'r', encoding='utf-8') as readme_file:
        readme_content = readme_file.read()
    
    # Remove emoji characters using regex
    # This regex pattern matches common emoji unicode ranges
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F700-\U0001F77F"  # alchemical symbols
        "\U0001F780-\U0001F7FF"  # Geometric Shapes
        "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        "\U0001FA00-\U0001FA6F"  # Chess Symbols
        "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        "\U00002702-\U000027B0"  # Dingbats
        "\U000024C2-\U0001F251" 
        "]+"
    )
    
    # Clean the readme content by removing emojis
    clean_readme = emoji_pattern.sub('', readme_content)
    
    # Create a Markdown renderer and display the content
    markdown = Markdown(clean_readme)
    console.print(Panel(markdown, title="Solana Research Tool - Documentation", border_style="green", expand=False))

def process_single_balance(api, console, address):
    """Process balance for a single address"""
    balance = api.get_account_balance(address)
    if balance is not None:
        console.print(f"Account Balance: [green]{balance:.9f}[/green] SOL")
    else:
        console.print("[red]Failed to fetch account balance[/red]")
        return

    sol_price_data = api.get_token_price("So11111111111111111111111111111111111111112")
    sol_price = sol_price_data.get("price_usdt", 0) if sol_price_data else 0

    # Fetch held token accounts for the address and aggregate token SOL value
    token_data = api.get_token_accounts(address)
    total_tokens_value = 0.0
    tokens_to_display = []
    if token_data and token_data.get("success") and token_data.get("data"):
        tokens = token_data["data"].get("tokenAccounts", [])
        if tokens:
            for token in tokens:
                token_name = token.get("tokenName", "Unknown")
                token_symbol = token.get("tokenSymbol", "Unknown")
                token_address = token.get("tokenAddress", "Unknown")
                balance_token = int(float(token.get("balance", 0)))  # Round down to integer
                usd_value = token.get("value", 0)
                true_value_in_sol = (usd_value / sol_price) if sol_price > 0 else usd_value
                if balance_token == 0 or true_value_in_sol < 0.01:
                    continue
                total_tokens_value += true_value_in_sol
                tokens_to_display.append((token_name, token_symbol, token_address, balance_token, true_value_in_sol))
            
            # Sort tokens by SOL value, descending
            tokens_to_display.sort(key=lambda x: x[4], reverse=True)
            
            # Compute total SOL balance and percentages
            total_sol = (balance if balance is not None else 0) + total_tokens_value
            sol_percentage = (balance / total_sol * 100) if total_sol > 0 else 0
            token_percentage = (total_tokens_value / total_sol * 100) if total_sol > 0 else 0
            
            # Print summary with aligned numbers and percentages
            summary = (f"\nAccount SOL: {balance:15.9f} SOL ([cyan]{sol_percentage:.1f}%[/cyan])\n"
                        f"Token SOL:   {total_tokens_value:15.9f} SOL ([cyan]{token_percentage:.1f}%[/cyan])\n"
                        f"Total SOL:   {total_sol:15.9f} SOL ([green]100%[/green])")
            console.print(summary)
            
            # Save balance information to CSV
            timestamp = datetime.now().strftime('%Y-%m-%d:%H-%M-%S')
            
            # Create directory for this wallet address
            wallet_dir = f"./reports/{address}"
            os.makedirs(wallet_dir, exist_ok=True)
            
            csv_filename = f"{wallet_dir}/balance.csv"
            
            # Create CSV file with headers if it doesn't exist
            if not os.path.exists(csv_filename):
                with open(csv_filename, 'w', encoding='utf-8') as f:
                    f.write("timestamp,sol_balance,token_balance,total_balance\n")
            
            # Append new balance data
            with open(csv_filename, 'a', encoding='utf-8') as f:
                f.write(f"{timestamp},{balance:.9f},{total_tokens_value:.9f},{total_sol:.9f}\n")
            
            console.print(f"\n[yellow]Balance data saved to {csv_filename}[/yellow]")
            
            # Display token table
            token_table = Table(title="\nHeld Tokens")
            token_table.add_column("Token Address", style="dim")
            token_table.add_column("Token Name", style="cyan")
            token_table.add_column("Token Symbol", style="magenta")
            token_table.add_column("Balance", justify="right", style="yellow")
            token_table.add_column("Value in SOL", justify="right", style="green")
            token_table.add_column("% of Total", justify="right", style="cyan")
            
            for token_name, token_symbol, token_address, balance_token, true_value_in_sol in tokens_to_display:
                # Format balance with k/m/b suffix
                formatted_balance = format_token_amount(balance_token)
                # Calculate percentage of total portfolio
                token_percent = (true_value_in_sol / total_sol * 100) if total_sol > 0 else 0
                token_table.add_row(
                    token_address,
                    token_name,
                    token_symbol,
                    formatted_balance,
                    f"{true_value_in_sol:.3f}",
                    f"{token_percent:.1f}%"
                )
            console.print(token_table)
    else:
        console.print("[yellow]No token account data found.[/yellow]")

def process_aggregate_balances(api, console, addresses):
    """Process multiple addresses and show aggregate balance"""
    total_sol = 0
    total_token_sol = 0
    token_balances = {}
    
    # Create reports directory if it doesn't exist
    os.makedirs('reports', exist_ok=True)
    
    # Generate filename using the standardized format
    csv_file = generate_aggregate_filename(addresses, "balance", include_timestamp_str=False)
    
    # Create CSV file with headers if it doesn't exist
    if not os.path.exists(csv_file):
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            f.write("timestamp,SOL balance,token SOL value,total SOL\n")
    
    # Process each address
    for address in addresses:
        try:
            # Get SOL balance
            sol_balance = api.get_account_balance(address)
            if sol_balance is not None:
                total_sol += sol_balance
            
            # Get token accounts
            token_data = api.get_token_accounts(address)
            if token_data and token_data.get("success") and token_data.get("data"):
                tokens = token_data["data"].get("tokenAccounts", [])
                for token in tokens:
                    token_name = token.get("tokenName", "Unknown")
                    token_symbol = token.get("tokenSymbol", "Unknown")
                    token_address = token.get("tokenAddress", "Unknown")
                    balance_token = int(float(token.get("balance", 0)))
                    usd_value = token.get("value", 0)
                    
                    # Get SOL price for conversion
                    sol_price_data = api.get_token_price("So11111111111111111111111111111111111111112")
                    sol_price = sol_price_data.get("price_usdt", 0) if sol_price_data else 0
                    
                    if sol_price > 0:
                        token_sol_value = (usd_value / sol_price)
                        total_token_sol += token_sol_value
                        
                        # Track token balances
                        if token_address in token_balances:
                            token_balances[token_address]['amount'] += balance_token
                            token_balances[token_address]['sol_value'] += token_sol_value
                        else:
                            token_balances[token_address] = {
                                'amount': balance_token,
                                'sol_value': token_sol_value,
                                'name': token_name,
                                'symbol': token_symbol
                            }
        
        except Exception as e:
            console.print(f"[red]Error processing address {address}: {str(e)}[/red]")
            continue
    
    # Calculate total
    total = total_sol + total_token_sol
    
    # Save to CSV
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(csv_file, 'a', newline='', encoding='utf-8') as f:
        f.write(f"{timestamp},{total_sol:.4f},{total_token_sol:.4f},{total:.4f}\n")
    
    # Display results
    console.print("\n[bold]Aggregate Balance Summary[/bold]")
    console.print(f"Total SOL Balance: [green]{total_sol:.4f} ◎[/green]")
    console.print(f"Total Token Value: [yellow]{total_token_sol:.4f} ◎[/yellow]")
    console.print(f"Total Value: [bold cyan]{total:.4f} ◎[/bold cyan]")
    
    if token_balances:
        console.print("\n[bold]Token Balances[/bold]")
        token_table = Table(show_header=True, header_style="bold")
        token_table.add_column("Token", style="dim")
        token_table.add_column("Amount", justify="right", style="cyan")
        token_table.add_column("Value (SOL)", justify="right", style="yellow")
        
        for token_address, data in token_balances.items():
            token_name = data['name'] or token_address[:8] + "..."
            token_table.add_row(
                token_name,
                f"{data['amount']:.4f}",
                f"{data['sol_value']:.4f} ◎"
            )
        
        console.print(token_table)
    
    console.print(f"\n[yellow]Report saved to {csv_file}[/yellow]")

def option_1(api, console):       
    if len(sys.argv) < 3:
        print("Error: Address required for account balance")
        print_usage()
        sys.exit(1)
    
    # Parse arguments
    args = sys.argv[2:]
    aggregate_mode = False
    addresses = get_addresses_from_args(sys.argv)
    
    # Check for aggregation flag
    if "-a" in args:
        aggregate_mode = True
        args.remove("-a")
    
    if not addresses:
        console.print("[red]No valid addresses provided[/red]")
        sys.exit(1)
    
    # Process in aggregate mode or individual mode
    if aggregate_mode:
        console.print(f"[yellow]Processing {len(addresses)} addresses in aggregate mode[/yellow]")
        process_aggregate_balances(api, console, addresses)
    else:
        # Process each address individually
        for address in addresses:
            console.print(f"\n[yellow]Processing address: [cyan]{address}[/cyan][/yellow]")
            process_single_balance(api, console, address)
def option_2(api, console):
    if len(sys.argv) != 3:
        print("Error: Address required for transaction history")
        print_usage()
        sys.exit(1)
    addresses = get_addresses_from_args(sys.argv)
    if len(addresses) != 1: raise ValueError("Error: Address required for transaction history")
    address = addresses[0]

    page_size = 10
    all_transactions = []
    page = 1
    max_transactions = 100
    api.console.print("\nFetching transactions...", style="yellow")
    while len(all_transactions) < max_transactions:
        transactions = api.get_account_transactions(address, page, page_size)
        if not transactions:
            break
        all_transactions.extend(transactions)
        if len(transactions) < page_size:
            break
        page += 1
    if all_transactions:
        api.console.print(f"\nFound [green]{len(all_transactions)}[/green] transactions\n")
        display_transactions_table(all_transactions, api.console, address)
    else:
        api.console.print("[red]Failed to fetch transactions or no transactions found[/red]")

def option_3(api, console):
    if len(sys.argv) <= 2:
        print("Error: Address required for balance history")
        print_usage()
        sys.exit(1)
    
    # Check if we're aggregating multiple addresses
    aggregate_mode = False
    addresses = get_addresses_from_args(sys.argv)
    
    # Parse arguments and extract command flags
    defi_days = None
    args = sys.argv[2:]  # Skip the program name and option flag
    
    # Extract parameters and addresses
    i = 0
    while i < len(args):
        if args[i].startswith('--defi_days='):
            try:
                defi_days = int(args[i].split('=')[1])
                console.print(f"[yellow]Filtering transactions to the last {defi_days} days[/yellow]")
            except (ValueError, IndexError):
                console.print("[red]Error: --defi_days parameter must be an integer (e.g., --defi_days=7)[/red]")
                sys.exit(1)
        elif args[i] == "-f" and i+1 < len(args):
            # Skip the -f parameter and its value
            i += 1
        i += 1
    
    # If no addresses were found, use the first argument as a single address
    if not addresses:
        addresses = [sys.argv[2]]
    
    # Get the filter string wherever it appears
    filter_str = None
    for i, arg in enumerate(sys.argv):
        if arg == "-f":
            if not len(sys.argv) > i+1:
                print("Error: Filter required")
                filter_token_stats(None, '')
                sys.exit(1)
            filter_str = sys.argv[i+1]
            break

    # Collect all trades
    all_trades = []
    
    for address in addresses:
        api.console.print(f"\nFetching DEX trading history for {address}...", style="yellow")
        trades = api.get_dex_trading_history(address, defi_days=defi_days)
        if trades:
            api.console.print(f"Found [green]{len(trades)}[/green] DEX trades for {address}")
            all_trades.extend(trades)
    
    if not all_trades:
        api.console.print("[red]No DEX trading history found[/red]")
        return

    api.console.print(f"\nTotal: [green]{len(all_trades)}[/green] DEX trades across {len(addresses)} {'addresses' if len(addresses) > 1 else 'address'}\n")
    
    # Use the analyze_trades function
    token_data, roi_data, tx_summary = analyze_trades(all_trades, api.console)
    
    # Apply filtering if specified
    if filter_str:
        # Convert token_data back to the format expected by filter_token_stats
        token_stats = {}
        for token in token_data:
            token_stats[token['address']] = {
                'trade_count': token['trades'],
                'hold_time': timedelta(seconds=token['hold_time']),
                'sol_invested': token['sol_invested'],
                'tokens_bought': 0,  # This will be fixed in analyze_trades
                'market_cap': token['first_mc'],  # Add market cap for filtering
                'median_market_entry': tx_summary['median_market_entry'],  # Add median market entry
                'median_mc_percentage': tx_summary['median_mc_percentage']  # Add median % of market cap at entry
            }
        
        # Show the filter being applied
        console.print(f"\n[yellow]Applying filter: [cyan]{filter_str}[/cyan][/yellow]")
        filtered_stats = filter_token_stats(token_stats, filter_str)
        if not filtered_stats:
            console.print("[red]No tokens match the specified filter criteria[/red]")
            return
        # Filter token_data to match filtered_stats
        token_data = [t for t in token_data if t['address'] in filtered_stats]
        console.print(f"[green]{len(token_data)} tokens match the filter criteria[/green]\n")
    elif filter_str == "":
        # Show filter usage information
        filter_token_stats({}, None)
        return

    # Update stats.csv if no time filters are applied AND we're not in aggregate mode
    if not defi_days and len(addresses) == 1:
        timestamp = datetime.now().strftime('%Y-%m-%d:%H-%M')
        update_stats_csv(timestamp, addresses[0], roi_data, tx_summary, token_data, console)

    # Display token table
    table = Table(title="DEX Trading Summary")
    table.add_column("Token", style="dim")
    table.add_column("Hold Time", justify="right", style="blue")
    table.add_column("Last Trade", justify="right", style="cyan")
    table.add_column("First MC", justify="right", style="yellow")
    table.add_column("SOL Invested", justify="right", style="green")
    table.add_column("SOL Received", justify="right", style="green")
    table.add_column("SOL Profit", justify="right", style="green")
    table.add_column("Fees", justify="right", style="red")
    table.add_column("Remaining", justify="right", style="yellow")
    table.add_column("Total Profit", justify="right", style="green")
    table.add_column("Token Price", justify="right", style="magenta")
    table.add_column("Trades", justify="right", style="cyan")
    
    # Track totals
    total_invested = 0
    total_received = 0
    total_profit = 0
    total_remaining = 0
    total_trades = 0
    total_buy_fees = 0
    total_sell_fees = 0
    total_fees = 0
    
    # Add rows to the table
    for token in token_data:
        # Format hold time
        hold_time_td = timedelta(seconds=token['hold_time'])
        hold_time = f"{hold_time_td.days}d {hold_time_td.seconds//3600}h {(hold_time_td.seconds%3600)//60}m"
        
        # Format market cap
        mc = token['first_mc']
        if mc >= 1_000_000_000:
            mc_color = "green"
            mc_value = f"{mc/1_000_000_000:.1f}".replace('.', ',') + "B"
        elif mc >= 1_000_000:
            mc_color = "yellow"
            mc_value = f"{mc/1_000_000:.1f}".replace('.', ',') + "M"
        elif mc >= 1_000:
            mc_color = "red"
            mc_value = f"{mc/1_000:.1f}".replace('.', ',') + "K"
        else:
            mc_color = "red"
            mc_value = f"{mc/1_000:.1f}".replace('.', ',') + "K"

        profit_color = "green" if token['sol_profit'] >= 0 else "red"
        total_profit_color = "green" if token['total_profit'] >= 0 else "red"
        
        # Update totals
        total_invested += token['sol_invested']
        total_received += token['sol_received']
        total_profit += token['sol_profit']  # Already includes fees
        total_remaining += token['remaining_value']
        total_trades += token['trades']
        total_buy_fees += token['buy_fees']
        total_sell_fees += token['sell_fees']
        total_fees += token['total_fees']
        
        table.add_row(
            format_token_address(token['address']),
            hold_time,
            datetime.fromtimestamp(token['last_trade']).strftime('%Y-%m-%d %H:%M'),
            f"[{mc_color}]{mc_value}[/{mc_color}]",
            f"{token['sol_invested']:.3f} SOL",
            f"{token['sol_received']:.3f} SOL",
            f"[{profit_color}]{token['sol_profit']:+.3f} SOL[/{profit_color}]",  # Already includes fees
            f"{token['total_fees']:.3f} SOL",
            f"{token['remaining_value']:.3f} SOL",
            f"[{total_profit_color}]{token['total_profit']:+.3f} SOL[/{total_profit_color}]",  # Already includes fees
            f"${token['token_price']:.6f}" if token['token_price'] > 0 else "N/A",
            str(token['trades'])
        )

    # Add totals row to table
    profit_style = "green" if total_profit >= 0 else "red"
    total_profit_style = "green" if (total_profit + total_remaining) >= 0 else "red"
    table.add_row(
        "[bold]TOTAL[/bold]",
        "",
        "",
        "",
        f"[bold]{total_invested:.3f} ◎[/bold]",
        f"[bold]{total_received:.3f} ◎[/bold]",
        f"[bold][{profit_style}]{total_profit:+.3f} ◎[/{profit_style}][/bold]",  # Already includes fees
        f"[bold]{total_fees:.3f} ◎[/bold]",
        f"[bold]{total_remaining:.3f} ◎[/bold]",
        f"[bold][{total_profit_style}]{(total_profit + total_remaining):+.3f} ◎[/{total_profit_style}][/bold]",  # Already includes fees
        "",
        f"[bold]{total_trades}[/bold]",
        end_section=True
    )

    console.print(table)

    # Display period-based ROI in a table
    roi_table = Table(title="Return on Investment (ROI)")
    roi_table.add_column("Period", style="yellow")
    roi_table.add_column("SOL Invested", justify="right", style="green")
    roi_table.add_column("SOL Received", justify="right", style="green")
    roi_table.add_column("Profit/Loss", justify="right", style="green")
    roi_table.add_column("ROI %", justify="right", style="magenta")

    for period in ['24h', '7d', '30d', '60d']:
        period_data = roi_data[period]
        profit_color = "green" if period_data['profit'] >= 0 else "red"
        roi_color = "green" if period_data['roi_percent'] and period_data['roi_percent'] >= 0 else "red"
        roi_table.add_row(
            period.upper(),
            f"{period_data['invested']:.3f} SOL",
            f"{period_data['received']:.3f} SOL",
            f"[{profit_color}]{'+' if period_data['profit'] >= 0 else ''}{period_data['profit']:.3f} SOL[/{profit_color}]",
            f"[{roi_color}]{'+' if period_data['roi_percent'] and period_data['roi_percent'] >= 0 else ''}{period_data['roi_percent']:.2f}%[/{roi_color}]" if period_data['roi_percent'] is not None else "N/A"
        )

    console.print()
    console.print(roi_table)

    # Display Transaction Summary
    transactions_table = Table(title="Transaction Summary")
    transactions_table.add_column("Transaction Type", style="yellow")
    transactions_table.add_column("Count", justify="right", style="green")
    transactions_table.add_column("Percentage", justify="right", style="blue")

    # Calculate percentages
    non_sol_percentage = (tx_summary['non_sol_swaps'] / tx_summary['total_transactions']) * 100 if tx_summary['total_transactions'] > 0 else 0
    sol_percentage = (tx_summary['sol_swaps'] / tx_summary['total_transactions']) * 100 if tx_summary['total_transactions'] > 0 else 0
    buy_fee_percentage = (total_buy_fees / total_invested) * 100 if total_invested > 0 else 0
    sell_fee_percentage = (total_sell_fees / total_received) * 100 if total_received > 0 else 0
    total_fee_percentage = (total_fees / (total_invested + total_received)) * 100 if (total_invested + total_received) > 0 else 0

    # Add rows to the table
    transactions_table.add_row("Total DeFi Transactions", f"{tx_summary['total_transactions']:,}", "100%")
    transactions_table.add_row("Non-SOL Token Swaps", f"{tx_summary['non_sol_swaps']:,}", f"{non_sol_percentage:.1f}%")
    transactions_table.add_row("SOL-Involved Swaps", f"{tx_summary['sol_swaps']:,}", f"{sol_percentage:.1f}%")
    transactions_table.add_row("", "", "")
    transactions_table.add_row("Win Rate", f"{tx_summary['win_rate']:.1f}%", f"({tx_summary['win_rate_ratio']} tokens)")
    transactions_table.add_row("Median Investment per Token", f"{tx_summary['median_investment']:.3f} ◎", "")
    transactions_table.add_row("Median ROI %", f"{tx_summary['median_roi_percent']:.1f}%", "")
    transactions_table.add_row("ROI % Standard Deviation", f"{tx_summary['roi_std_dev']:.1f}%", "")
    transactions_table.add_row("Median Hold Time", f"{format_seconds(tx_summary['median_hold_time'])}", "")
    transactions_table.add_row("Median Market Entry", f"{format_mc(tx_summary['median_market_entry'])}", "")
    transactions_table.add_row("Median % of Market Cap at Entry", f"{tx_summary['median_mc_percentage']:.4f}%", "")
    transactions_table.add_row("", "", "")
    transactions_table.add_row("Total Buy Fees", f"{total_buy_fees:.3f} SOL", f"({buy_fee_percentage:.1f}% of invested)")
    transactions_table.add_row("Total Sell Fees", f"{total_sell_fees:.3f} SOL", f"({sell_fee_percentage:.1f}% of received)")
    transactions_table.add_row("Total Fees", f"{total_fees:.3f} ◎", f"({total_fee_percentage:.1f}% of volume)")

    console.print()
    console.print(transactions_table)
    
    # Create directory for this wallet address
    wallet_dir = f"./reports/{address}"
    os.makedirs(wallet_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M')
    if aggregate_mode and len(addresses) > 1:
        csv_filename = generate_aggregate_filename(addresses, "dex-trades")
    else:
        csv_filename = f'{wallet_dir}/dex-trades-{timestamp}.csv'

    # Save to CSV
    with open(csv_filename, 'w', encoding='utf-8') as f:
        f.write("Token;First Trade;Hold Time;Last Trade;First MC;SOL Invested;SOL Received;SOL Profit (after fees);Buy Fees;Sell Fees;Total Fees;Remaining Value;Total Profit (after fees);Token Price (USDT);Trades\n")
        for token in token_data:
            hold_time_td = timedelta(seconds=token['hold_time'])
            hold_time = f"{hold_time_td.days}d {hold_time_td.seconds//3600}h {(hold_time_td.seconds%3600)//60}m"
            f.write(f"{token['address']};" + 
                    f"{datetime.fromtimestamp(token['first_trade']).strftime('%Y-%m-%d %H:%M')};" +
                    f"{hold_time};" +
                    f"{datetime.fromtimestamp(token['last_trade']).strftime('%Y-%m-%d %H:%M')};" +
                    f"{token['first_mc']:.2f};" +
                    f"{token['sol_invested']:.3f};" +
                    f"{token['sol_received']:.3f};" +
                    f"{token['sol_profit']:.3f};" +  # Already includes fees
                    f"{token['buy_fees']:.3f};" +
                    f"{token['sell_fees']:.3f};" +
                    f"{token['total_fees']:.3f};" +
                    f"{token['remaining_value']:.3f};" +
                    f"{token['total_profit']:.3f};" +  # Already includes fees
                    f"{token['token_price']:.6f};" +
                    f"{token['trades']}\n")

        # Add totals to CSV
        total_overall_profit = total_profit + total_remaining  # Already includes fees
        f.write(f"TOTAL;;;;" +
                f";{total_invested:.3f};" +
                f"{total_received:.3f};" +
                f"{total_profit:.3f};" +  # Already includes fees
                f"{total_buy_fees:.3f};" +
                f"{total_sell_fees:.3f};" +
                f"{total_fees:.3f};" +
                f"{total_remaining:.3f};" +
                f"{total_overall_profit:.3f};;" +  # Already includes fees
                f"{total_trades}\n")

    if aggregate_mode and len(addresses) > 1:
        console.print(f"\n[yellow]Aggregate report saved to {csv_filename}[/yellow]")
    else:
        console.print(f"\n[yellow]Report saved to {csv_filename}[/yellow]")

def read_copy_traders_csv():
    """
    Read existing copy_traders.csv into a dictionary.
    Returns a dictionary with (wallet, target) as key and (count, timestamp) as value.
    """
    copy_traders_file = 'reports/copy_traders.csv'
    copy_traders = {}
    
    # Create file with headers if it doesn't exist
    if not os.path.exists(copy_traders_file):
        with open(copy_traders_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Timestamp', 'Copyer', 'Copyee', 'Count'])
        return copy_traders
    
    # Read existing entries
    with open(copy_traders_file, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row['Copyer'], row['Copyee'])
            copy_traders[key] = (int(row['Count']), row['Timestamp'])
    
    return copy_traders

def update_copy_traders_csv(copy_traders, new_entries, console):
    """
    Update copy_traders.csv with new entries.
    
    Args:
        copy_traders (dict): Existing entries from read_copy_traders_csv()
        new_entries (list): List of (copyer, copyee, count) tuples
        console (Console): Rich console for output
    """
    copy_traders_file = 'reports/copy_traders.csv'
    current_timestamp = datetime.now().strftime('%Y-%m-%d:%H-%M')
    
    # Update existing entries and add new ones
    for copyer, copyee, count in new_entries:
        key = (copyer, copyee)
        if key in copy_traders:
            # Update existing entry with new count and timestamp
            copy_traders[key] = (count, current_timestamp)
        else:
            # Add new entry
            copy_traders[key] = (count, current_timestamp)
    
    # Write all entries back to file
    with open(copy_traders_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Timestamp', 'Copyer', 'Copyee', 'Count'])
        for (copyer, copyee), (count, timestamp) in copy_traders.items():
            writer.writerow([timestamp, copyer, copyee, count])
    
    console.print(f"[green]Updated copy_traders.csv with {len(new_entries)} new/updated entries[/green]")

def option_4(api, console):
    """
    Detect wallets that bought the same tokens as the target wallet
    
    Shows a table with wallets and counts of:
    - Number of unique tokens bought ≤30 seconds BEFORE the target
    - Number of unique tokens bought ≤30 seconds AFTER the target
    """
    if len(sys.argv) < 3:
        print("Error: Wallet address required for wallets analysis")
        print_usage()
        sys.exit(1)
    
    # Parse arguments for parameters
    defi_days = None
    args = sys.argv[2:]  # Skip the program name and option flag
    
    # Lists to store addresses and parameters
    target_wallets = get_addresses_from_args(sys.argv)
    
    # Extract parameters and addresses
    i = 0
    while i < len(args):
        if args[i].startswith('--defi_days='):
            try:
                defi_days = int(args[i].split('=')[1])
                console.print(f"[yellow]Filtering transactions to the last {defi_days} days[/yellow]")
            except (ValueError, IndexError):
                console.print("[red]Error: --defi_days parameter must be an integer (e.g., --defi_days=7)[/red]")
                sys.exit(1)
        i += 1
    
    # If no addresses found, use the first argument
    if not target_wallets:
        target_wallets = [sys.argv[2]]
    
    # Read existing copy traders data
    copy_traders = read_copy_traders_csv()
    
    # Process each wallet address
    for target_wallet in target_wallets:
        console.print(f"\n[yellow]Analyzing trading history for {target_wallet}...[/yellow]")
        
        # Create a table to display results
        wallets_table = Table(title=f"Wallets Trading Same Tokens as {target_wallet}")
        wallets_table.add_column("Wallet Address", style="cyan")
        wallets_table.add_column("Before (≤30s)", justify="right", style="yellow")
        wallets_table.add_column("After (≤30s)", justify="right", style="green")
        wallets_table.add_column("Med Buy-in", justify="right", style="yellow")
        wallets_table.add_column("Avg Buy-in", justify="right", style="green")
        
        # Dictionary to track wallet stats
        wallets = {}  # Structure: {wallet_address: {'before': {'tokens': set(), 'buy_ins': []}, 'after': {'tokens': set(), 'buy_ins': []}}}
        
        trades = api.get_dex_trading_history(target_wallet, quiet=True, defi_days=defi_days)
        
        if not trades:
            console.print("[red]No DEX trading history found for this wallet[/red]")
            continue
        
        console.print(f"Found [green]{len(trades)}[/green] DEX trades")
        
        # Get token buys (where target wallet bought a token using SOL)
        target_buys = []  # List of (token, trade) tuples
        for trade in trades:
            # Check if this is a buy (SOL -> token)
            if is_sol_token(trade.token1) and not is_sol_token(trade.token2):
                token = trade.token2
                target_buys.append((token, trade))
        
        # Sort by timestamp (newest first)
        target_buys.sort(key=lambda x: x[1].block_time, reverse=True)

        # Take unique tokens
        seen_tokens = set()
        recent_buys = {}  # {token_address: trade_data}
        for token, trade in target_buys:
            if token not in seen_tokens:
                seen_tokens.add(token)
                recent_buys[token] = trade

        # Reduce recent buys to 10 most recent trades
        recent_buys = dict(list(recent_buys.items())[:50])
        
        console.print(f"Analyzing [green]{len(recent_buys)}[/green] unique token buys")
        
        # Print token addresses being analyzed
        console.print("\n[bold yellow]Tokens being analyzed:[/bold yellow]")
        for i, token in enumerate(recent_buys.keys(), 1):
            console.print(f"{i}. [cyan]{token}[/cyan]")
        console.print("")
        
        # Track progress
        with console.status("[bold green]Scanning for wallets trading same tokens...[/bold green]", spinner="dots") as status:
            # For each token, find wallets that bought within 30 seconds before/after the target
            for token, target_trade in recent_buys.items():
                token_name = token[:5] + "..." + token[-5:]
                target_time = target_trade.block_time
                
                status.update(f"[bold green]Scanning transactions for token {token_name} (±30s window)...[/bold green]")
                
                # Calculate the time window: 30 seconds before and after the target trade
                from_time = target_time - 30  # 30 seconds before target's trade
                to_time = target_time + 30    # 30 seconds after target's trade
                
                # Get trades only within the time window using timestamp filtering
                token_trades = api.get_dex_trading_history(
                    token, 
                    quiet=True,
                    from_time=from_time,
                    to_time=to_time
                )
                
                # Find trades within the time window
                for trade in token_trades:
                    # Skip if it's not a buy (SOL -> token)
                    if not is_sol_token(trade.token1) or is_sol_token(trade.token2):
                        continue
                        
                    # Skip if it's the target wallet
                    if trade.from_address == target_wallet:
                        continue
                    
                    # Check timing relative to target's trade
                    time_diff = trade.block_time - target_time
                    
                    # Initialize wallet data if not seen before
                    if trade.from_address not in wallets:
                        wallets[trade.from_address] = {
                            'before': {'tokens': set(), 'buy_ins': []},
                            'after': {'tokens': set(), 'buy_ins': []}
                        }
                    
                    # Extract buy-in amount (SOL amount)
                    try:
                        amount1 = float(trade.amount1) / (10 ** trade.token1_decimals)
                        amount2 = float(trade.amount2) / (10 ** trade.token2_decimals)
                        buy_in = amount1 if is_sol_token(trade.token1) else amount2
                    except (ValueError, TypeError):
                        buy_in = 0
                    
                    # Add token and buy-in amount to the appropriate set based on timing
                    if -30 <= time_diff < 0:  # Bought before target (within 30 seconds)
                        wallets[trade.from_address]['before']['tokens'].add(token)
                        wallets[trade.from_address]['before']['buy_ins'].append(buy_in)
                    elif 0 < time_diff <= 30:  # Bought after target (within 30 seconds)
                        wallets[trade.from_address]['after']['tokens'].add(token)
                        wallets[trade.from_address]['after']['buy_ins'].append(buy_in)
        
        # Filter out wallets with no matches
        wallets = {k: v for k, v in wallets.items() if v['before'] or v['after']}
        
        if not wallets:
            console.print("[yellow]No wallets found trading the same tokens within the 30-second window[/yellow]")
            continue
        
        # Sort by total count (before + after), then by after count, then by before count
        sorted_wallets = sorted(
            wallets.items(), 
            key=lambda x: (
                1 if len(x[1]['before']['tokens']) > len(x[1]['after']['tokens']) else 0, # Primary sort: whether before > after
                len(x[1]['after']['tokens']),   # Secondary sort: number of "after" trades
                len(x[1]['before']['tokens'])  # Tertiary sort: number of "before" trades
            ),
            reverse=True
        )
        
        # Track new entries for copy_traders.csv
        new_entries = []
        
        # Add rows to the table
        for wallet, data in sorted_wallets:
            before_count = len(data['before']['tokens'])
            after_count = len(data['after']['tokens'])

            # Only show wallets with at least 5 trades before and after
            if before_count < 5 and after_count < 5:
                continue
            
            # Calculate median and average buy-in amounts
            before_buy_ins = sorted(data['before']['buy_ins'])
            after_buy_ins = sorted(data['after']['buy_ins'])
            
            before_median = before_buy_ins[len(before_buy_ins)//2] if before_buy_ins else 0
            after_median = after_buy_ins[len(after_buy_ins)//2] if after_buy_ins else 0
            median_buy_in = (before_median + after_median) / 2 if before_buy_ins or after_buy_ins else 0
            
            before_avg = sum(before_buy_ins) / len(before_buy_ins) if before_buy_ins else 0
            after_avg = sum(after_buy_ins) / len(after_buy_ins) if after_buy_ins else 0
            avg_buy_in = (before_avg + after_avg) / 2 if before_buy_ins or after_buy_ins else 0
            
            wallets_table.add_row(
                wallet,
                str(before_count),
                str(after_count),
                f"{median_buy_in:.3f} ◎",
                f"{avg_buy_in:.3f} ◎"
            )
            
            # Add to new_entries if meets criteria
            if before_count > 5 and before_count > after_count:
                new_entries.append((target_wallet, wallet, before_count))
            elif after_count > 5 and after_count > before_count:
                new_entries.append((wallet, target_wallet, after_count))
        
        console.print(wallets_table)
        
        # Save results to CSV
        # Create directory for this wallet address
        wallet_dir = f'reports/{target_wallet}'
        os.makedirs(wallet_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M')
        csv_filename = f'{wallet_dir}/same_token_traders_{timestamp}.csv'
        
        with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Wallet Address', 'Unique Tokens Before', 'Unique Tokens After', 'Median Buy-in', 'Average Buy-in'])
            
            for wallet, data in sorted_wallets:
                before_count = len(data['before']['tokens'])
                after_count = len(data['after']['tokens'])
                
                # Calculate median and average buy-in amounts
                before_buy_ins = sorted(data['before']['buy_ins'])
                after_buy_ins = sorted(data['after']['buy_ins'])
                
                before_median = before_buy_ins[len(before_buy_ins)//2] if before_buy_ins else 0
                after_median = after_buy_ins[len(after_buy_ins)//2] if after_buy_ins else 0
                median_buy_in = (before_median + after_median) / 2 if before_buy_ins or after_buy_ins else 0
                
                before_avg = sum(before_buy_ins) / len(before_buy_ins) if before_buy_ins else 0
                after_avg = sum(after_buy_ins) / len(after_buy_ins) if after_buy_ins else 0
                avg_buy_in = (before_avg + after_avg) / 2 if before_buy_ins or after_buy_ins else 0
                
                writer.writerow([
                    wallet,
                    before_count,
                    after_count,
                    format_number_for_csv(median_buy_in),
                    format_number_for_csv(avg_buy_in)
                ])
        
        console.print(f"\n[yellow]Results for {target_wallet} saved to {csv_filename}[/yellow]")
        
        # Update copy_traders.csv with new entries
        if new_entries:
            update_copy_traders_csv(copy_traders, new_entries, console)

def option_5(api, console):
    if len(sys.argv) < 3:
        print("Error: At least one wallet address is required for option -5")
        print_usage()
        sys.exit(1)

    addresses = get_addresses_from_args(sys.argv)
    if len(addresses) == 0:
        print("Error: At least one wallet address is required for option -5")
        print_usage()
        sys.exit(1)
    
    # Parse arguments for parameter flags
    days_filter = None
    defi_days_filter = None
    args = sys.argv[2:]  # Skip the program name and option flag
    
    # Extract parameters
    i = 0
    while i < len(args):
        if args[i].startswith('--days='):
            try:
                days_filter = int(args[i].split('=')[1])
                console.print(f"[yellow]Filtering tokens to those first bought within the last {days_filter} days[/yellow]")
            except (ValueError, IndexError):
                console.print("[red]Error: --days parameter must be an integer (e.g., --days=7)[/red]")
                sys.exit(1)
        elif args[i].startswith('--defi_days='):
            try:
                defi_days_filter = int(args[i].split('=')[1])
                console.print(f"[yellow]Filtering transactions to the last {defi_days_filter} days[/yellow]")
            except (ValueError, IndexError):
                console.print("[red]Error: --defi_days parameter must be an integer (e.g., --defi_days=7)[/red]")
                sys.exit(1)
        i += 1

    # Update args after removing parameters
    args = [arg for arg in args if not arg.startswith('--')]
    if args:
        first_arg = args[0]
    else:
        print("Error: At least one wallet address is required for option -5")
        print_usage()
        sys.exit(1)

    # Create the base timestamp for all batch files
    timestamp = datetime.now().strftime('%Y-%m-%d:%H-%M')
    
    # Create the reports directory if it doesn't exist
    os.makedirs('reports', exist_ok=True)
    
    # Create master CSV filename
    master_csv_filename = generate_aggregate_filename(addresses, "option5-master")
    
    # Store all results for master CSV
    all_results = []
    
    # Split addresses into batches of 100
    batch_size = 100
    address_batches = [addresses[i:i+batch_size] for i in range(0, len(addresses), batch_size)]
    
    total_batches = len(address_batches)
    console.print(f"[bold yellow]Processing {len(addresses)} addresses in {total_batches} batches of {batch_size}[/bold yellow]")
    
    # Process each batch
    for batch_idx, batch_addresses in enumerate(address_batches, 1):
        console.print(f"\n[bold cyan]===== Processing Batch {batch_idx}/{total_batches} =====\n[/bold cyan]")
        
        # Store results for this batch
        batch_results = []
        
        summary_table = Table(title=f"DeFi Summary for Wallets (Batch {batch_idx}/{total_batches})")
        summary_table.add_column("Address", style="cyan")
        summary_table.add_column("24H ROI %", justify="right", style="magenta")
        summary_table.add_column("7D ROI %", justify="right", style="magenta")
        summary_table.add_column("30D ROI %", justify="right", style="magenta")
        summary_table.add_column("60D ROI %", justify="right", style="magenta")
        summary_table.add_column("60D ROI", justify="right", style="yellow")
        summary_table.add_column("Total Fees", justify="right", style="red")
        summary_table.add_column("Win Rate", justify="right", style="green")
        summary_table.add_column("Med Investment", justify="right", style="green")
        summary_table.add_column("Med ROI %", justify="right", style="magenta")
        summary_table.add_column("ROI % Std Dev", justify="right", style="magenta")
        summary_table.add_column("Med Hold Time", justify="right", style="blue")
        summary_table.add_column("Med Market Entry", justify="right", style="yellow")
        summary_table.add_column("Med MC %", justify="right", style="cyan")
        
        total_wallets_in_batch = len(batch_addresses)
        for idx, addr in enumerate(batch_addresses, 1):
            console.print(f"[yellow]Processing wallet {idx}/{total_wallets_in_batch} in batch {batch_idx}/{total_batches}: [cyan]{addr}[/cyan][/yellow]")
            trades = api.get_dex_trading_history(addr, days=days_filter, defi_days=defi_days_filter)
            if trades:
                console.print(f"Found [green]{len(trades)}[/green] DEX trades")
            else:
                console.print("[red]No DEX trading history found[/red]")
                continue

            # Use analyze_trades to get structured data
            token_data, roi_data, tx_summary = analyze_trades(trades, api.console)

            # Update stats.csv if no time filters are applied
            if not defi_days_filter and not days_filter:
                update_stats_csv(timestamp, addr, roi_data, tx_summary, token_data, console)

            # Calculate total fees from token data
            total_fees = sum(token['total_fees'] for token in token_data)
            total_buy_fees = sum(token['buy_fees'] for token in token_data)
            total_sell_fees = sum(token['sell_fees'] for token in token_data)

            def format_duration(td):
                days = td.days
                hours = td.seconds // 3600
                minutes = (td.seconds % 3600) // 60
                if days > 0:
                    return f"{days}d {hours}h {minutes}m"
                elif hours > 0:
                    return f"{hours}h {minutes}m"
                else:
                    return f"{minutes}m"

            # Create result record
            result = {
                "Address": addr,
                "24H ROI %": format_number_for_csv(roi_data['24h']['roi_percent']) if roi_data['24h']['roi_percent'] is not None else "N/A",
                "7D ROI %": format_number_for_csv(roi_data['7d']['roi_percent']) if roi_data['7d']['roi_percent'] is not None else "N/A",
                "30D ROI %": format_number_for_csv(roi_data['30d']['roi_percent']) if roi_data['30d']['roi_percent'] is not None else "N/A",
                "60D ROI %": format_number_for_csv(roi_data['60d']['roi_percent']) if roi_data['60d']['roi_percent'] is not None else "N/A",
                "60D ROI": format_number_for_csv(roi_data['60d']['profit']),  # Already includes fees
                "Total Fees": format_number_for_csv(total_fees),
                "Buy Fees": format_number_for_csv(total_buy_fees),
                "Sell Fees": format_number_for_csv(total_sell_fees),
                "Win Rate": format_number_for_csv(tx_summary['win_rate']),
                "Profitable/Total": tx_summary['win_rate_ratio'],
                "Median Investment": format_number_for_csv(tx_summary['median_investment']),
                "Median ROI %": format_number_for_csv(tx_summary['median_roi_percent']),
                "ROI % Std Dev": format_number_for_csv(tx_summary['roi_std_dev']),
                "Median Hold Time": format_seconds(tx_summary['median_hold_time']),
                "win_rate": tx_summary['win_rate'],
                "med_investment": tx_summary['median_investment'],
                "med_roi": tx_summary['median_roi_percent'],
                "roi_std_dev": tx_summary['roi_std_dev'],
                "med_hold_time": tx_summary['median_hold_time'],
                "med_market_entry": tx_summary['median_market_entry'],
                "med_mc_percentage": tx_summary['median_mc_percentage'],
                "Batch": batch_idx
            }

            # Add to batch results and all results
            batch_results.append(result)
            all_results.append(result)
            
            # Color coding for display
            win_rate_color = "green" if tx_summary['win_rate'] >= 50 else "red"
            roi_24h = roi_data['24h']['roi_percent']  # Already includes fees
            roi_7d = roi_data['7d']['roi_percent']    # Already includes fees
            roi_30d = roi_data['30d']['roi_percent']  # Already includes fees
            roi_60d = roi_data['60d']['roi_percent']  # Already includes fees
            
            # Color ROIs based on profit/loss (after fees)
            roi_24h_color = "green" if roi_24h and roi_24h > 0 else "red"
            roi_7d_color = "green" if roi_7d and roi_7d > 0 else "red"
            roi_30d_color = "green" if roi_30d and roi_30d > 0 else "red"
            roi_60d_color = "green" if roi_60d and roi_60d > 0 else "red"
            
            summary_table.add_row(
                addr,
                f"[{roi_24h_color}]{roi_24h:+.2f}%[/{roi_24h_color}]" if roi_24h is not None else "N/A",
                f"[{roi_7d_color}]{roi_7d:+.2f}%[/{roi_7d_color}]" if roi_7d is not None else "N/A",
                f"[{roi_30d_color}]{roi_30d:+.2f}%[/{roi_30d_color}]" if roi_30d is not None else "N/A",
                f"[{roi_60d_color}]{roi_60d:+.2f}%[/{roi_60d_color}]" if roi_60d is not None else "N/A",
                f"{roi_data['60d']['profit']:.3f} SOL",  # Already includes fees
                f"[red]{total_fees:.3f} ◎[/red]",
                f"[{win_rate_color}]{tx_summary['win_rate']:.1f}% ({tx_summary['win_rate_ratio']})[/{win_rate_color}]",
                f"{tx_summary['median_investment']:.3f} ◎",
                f"{'+' if tx_summary['median_roi_percent'] >= 0 else ''}{tx_summary['median_roi_percent']:.1f}%",
                f"{tx_summary['roi_std_dev']:.1f}%",
                format_seconds(tx_summary['median_hold_time']),
                format_mc(tx_summary['median_market_entry']),
                f"{tx_summary['median_mc_percentage']:.4f}%",
            )
        
        # Print the batch table
        console.print(summary_table)
        
        # Save batch to CSV
        if batch_results:
            batch_csv_filename = generate_aggregate_filename(batch_addresses, "option5", batch_idx=batch_idx)
            
            with open(batch_csv_filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=batch_results[0].keys(), delimiter=';')  # Using semicolon for LibreOffice compatibility
                writer.writeheader()
                writer.writerows(batch_results)
            
            console.print(f"\n[yellow]Batch {batch_idx} results saved to {batch_csv_filename}[/yellow]")
    
    # Save master CSV with all results
    if all_results:
        with open(master_csv_filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=all_results[0].keys(), delimiter=';')  # Using semicolon for LibreOffice compatibility
            writer.writeheader()
            writer.writerows(all_results)
        
        console.print(f"\n[bold green]All results saved to {master_csv_filename}[/bold green]")
    else:
        console.print("\n[red]No results to save[/red]")

def option_6(api, console):
    if len(sys.argv) < 3:
        print("Error: One token contract address is required for option -6")
        print_usage()
        sys.exit(1)
    token_address = get_addresses_from_args(sys.argv)
    if len(token_address) != 1:
        print("Error: One token contract address is required for option -6")
        print_usage()
        sys.exit(1)
    token_address = token_address[0]
    
    # Load environment variables
    load_dotenv()
    auth_token = os.getenv('BULLX_AUTH_TOKEN')
    if not auth_token:
        console.print("[red]Error: BULLX_AUTH_TOKEN not found in .env file[/red]")
        sys.exit(1)
    
    url = "https://api-neo.bullx.io/v2/api/holdersSummaryV2"
    
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-GB,en;q=0.9",
        "authorization": f"Bearer {auth_token}",
        "content-type": "application/json",
        "origin": "https://neo.bullx.io",
        "referer": "https://neo.bullx.io/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
    }
    
    data = {
        "name": "holdersSummaryV2",
        "data": {
            "tokenAddress": token_address,
            "sortBy": "pnlUSD",
            "chainId": 1399811149,
            "filters": {
                "tagsFilters": []
            }
        }
    }
    
    try:
        scraper = cloudscraper.create_scraper()
        response = scraper.post(url, headers=headers, json=data)
        response.raise_for_status()
        holders_data = response.json()
        
        # Save addresses to file
        with open("found_addresses_6.txt", "w", encoding='utf-8') as f:
            f.write(f"Token Holder Addresses for {token_address}\n")
            f.write("=" * 50 + "\n")
            f.write(f"Found at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}:\n\n")
            for entry in holders_data:
                f.write(f"{entry['address']}\n")
            f.write("\n" + "=" * 50 + "\n")
            f.write(f"Total Addresses Found: {len(holders_data)}\n")
        
        console.print("\n[yellow]Found Holder Addresses:[/yellow]")
        for entry in holders_data:
            console.print(f"[cyan]{entry['address']}[/cyan]")
        
        console.print(f"\n[green]Total Addresses Found: {len(holders_data)}[/green]")
        console.print(f"[yellow]Addresses have been saved to found_addresses_6.txt[/yellow]")
        
    except (cloudscraper.exceptions.CloudflareChallengeError) as e:
        console.print(f"[red]Error fetching data: {str(e)}[/red]")
        sys.exit(1)

def option_8(api, console):
    """
    Generate a heatmap visualization of DeFi activity by hour and day of week
    
    This function creates a 7x24 grid (days x hours) where each cell represents
    the amount of DeFi activity that occurred during that specific day/hour combination.
    The intensity of the color represents the relative amount of activity.
    """
    if len(sys.argv) < 3:
        print("Error: Wallet address required for activity heatmap")
        print_usage()
        sys.exit(1)
    
    # Parse arguments for parameters
    defi_days = None
    args = sys.argv[2:]  # Skip the program name and option flag
    
    target_wallet = get_addresses_from_args(sys.argv)
    if len(target_wallet) != 1:
        print("Error: Wallet address required for activity heatmap")
        print_usage()
        sys.exit(1)
    target_wallet = target_wallet[0]
    
    # Extract parameters
    i = 0
    while i < len(args):
        if args[i].startswith('--defi_days='):
            try:
                defi_days = int(args[i].split('=')[1])
                console.print(f"[yellow]Filtering transactions to the last {defi_days} days[/yellow]")
            except (ValueError, IndexError):
                console.print("[red]Error: --defi_days parameter must be an integer (e.g., --defi_days=7)[/red]")
                sys.exit(1)
        elif not args[i].startswith('--'):
            # This is the target wallet address
            target_wallet = args[i]
        i += 1
    
    if not target_wallet:
        target_wallet = sys.argv[2]  # Fallback to first argument
    
    # Import required rich components for visualization
    from rich.text import Text
    from rich.box import SIMPLE
    
    # Define day names for labels
    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    
    console.print(f"\n[yellow]Fetching DeFi trading history for {target_wallet}...[/yellow]")
    trades = api.get_dex_trading_history(target_wallet, defi_days=defi_days)
    
    if not trades:
        console.print("[red]No DeFi trading history found for this wallet[/red]")
        return
    
    console.print(f"Found [green]{len(trades)}[/green] DeFi transactions")
    
    # Create a 7x24 grid to count activity by day and hour
    activity_grid = [[0 for _ in range(24)] for _ in range(7)]
    
    # Count transactions by day of week and hour
    for trade in trades:
        # Convert Unix timestamp to datetime
        trade_time = datetime.fromtimestamp(trade.block_time)
        # Get day of week (0 = Monday, 6 = Sunday)
        day_of_week = trade_time.weekday()
        # Get hour of day (0-23)
        hour_of_day = trade_time.hour
        
        # Increment the counter for this day/hour combination
        activity_grid[day_of_week][hour_of_day] += 1
    
    # Find maximum activity count for scaling
    max_activity = max(max(row) for row in activity_grid)
    
    if max_activity == 0:
        console.print("[yellow]No activity data to display[/yellow]")
        return
    
    # Create a table for visualization
    heatmap_table = Table(
        title=f"DeFi Activity Heatmap for {target_wallet}",
        show_header=True,
        header_style="bold magenta",
        box=SIMPLE,
        expand=False,
        padding=0
    )
    
    # Add hour columns
    heatmap_table.add_column("Day", style="cyan", justify="right")
    for hour in range(24):
        heatmap_table.add_column(f"{hour}", justify="center", width=3)
    
    # Add a row for the total activity per hour
    hour_totals = [sum(activity_grid[day][hour] for day in range(7)) for hour in range(24)]
    total_cells = []
    
    for hour in range(24):
        # Calculate intensity (0-255) based on activity level
        if hour_totals[hour] > 0:
            intensity = min(255, int((hour_totals[hour] / max_activity) * 255))
            # Create color based on intensity
            # Using a grayscale from black (low) to white (high)
            color_value = f"#{intensity:02x}{intensity:02x}{intensity:02x}"
            total_cells.append(Text("■", style=f"on {color_value}"))
        else:
            total_cells.append(Text("■", style="on black"))
    
    heatmap_table.add_row("Total", *total_cells, end_section=True)
    
    # Fill the table with activity data
    for day_idx, day_name in enumerate(days_of_week):
        day_cells = []
        
        for hour in range(24):
            activity_count = activity_grid[day_idx][hour]
            
            # Calculate intensity (0-255) based on activity level
            if activity_count > 0:
                intensity = min(255, int((activity_count / max_activity) * 255))
                # Create color based on intensity
                # Using a grayscale from black (low) to white (high)
                color_value = f"#{intensity:02x}{intensity:02x}{intensity:02x}"
                day_cells.append(Text("■", style=f"on {color_value}"))
            else:
                day_cells.append(Text("■", style="on black"))
        
        heatmap_table.add_row(day_name, *day_cells)
    
    console.print(heatmap_table)
    
    # Display summary statistics
    day_totals = [sum(row) for row in activity_grid]
    most_active_day_idx = day_totals.index(max(day_totals))
    most_active_day = days_of_week[most_active_day_idx]
    
    most_active_hour = hour_totals.index(max(hour_totals))
    most_active_hour_formatted = f"{most_active_hour:02d}:00 - {(most_active_hour+1) % 24:02d}:00"
    
    console.print(f"\n[bold]Activity Summary:[/bold]")
    console.print(f"Most active day: [green]{most_active_day}[/green] with [green]{sum(activity_grid[most_active_day_idx])}[/green] transactions")
    console.print(f"Most active hour: [green]{most_active_hour_formatted}[/green] with [green]{max(hour_totals)}[/green] transactions")
    
    # Analyze timezone based on inactivity patterns
    console.print("\n[bold]Timezone Analysis:[/bold]")
    
    # Create a normalized inactivity score (where 1 = completely inactive, 0 = most active)
    max_hour_activity = max(hour_totals) if max(hour_totals) > 0 else 1
    inactivity_scores = [1 - (count / max_hour_activity) for count in hour_totals]
    
    # Define common timezone offsets with regions
    timezones = {
        "UTC-12 to UTC-11 (Baker Island, Samoa)": {"offset": -12, "probability": 0, "explanation": ""},
        "UTC-10 (Hawaii)": {"offset": -10, "probability": 0, "explanation": ""},
        "UTC-9 (Alaska)": {"offset": -9, "probability": 0, "explanation": ""},
        "UTC-8 (Pacific US)": {"offset": -8, "probability": 0, "explanation": ""},
        "UTC-7 (Mountain US)": {"offset": -7, "probability": 0, "explanation": ""},
        "UTC-6 (Central US)": {"offset": -6, "probability": 0, "explanation": ""},
        "UTC-5 (Eastern US)": {"offset": -5, "probability": 0, "explanation": ""},
        "UTC-4 (Atlantic Canada)": {"offset": -4, "probability": 0, "explanation": ""},
        "UTC-3 (Brazil, Argentina)": {"offset": -3, "probability": 0, "explanation": ""},
        "UTC-2 to UTC-1 (Mid-Atlantic)": {"offset": -2, "probability": 0, "explanation": ""},
        "UTC+0 (UK, Portugal)": {"offset": 0, "probability": 0, "explanation": ""},
        "UTC+1 (Central Europe)": {"offset": 1, "probability": 0, "explanation": ""},
        "UTC+2 (Eastern Europe)": {"offset": 2, "probability": 0, "explanation": ""},
        "UTC+3 (Moscow, Middle East)": {"offset": 3, "probability": 0, "explanation": ""},
        "UTC+4 to UTC+5 (Dubai, Pakistan)": {"offset": 4, "probability": 0, "explanation": ""},
        "UTC+5:30 (India)": {"offset": 5.5, "probability": 0, "explanation": ""},
        "UTC+6 to UTC+7 (Bangladesh, Thailand)": {"offset": 6, "probability": 0, "explanation": ""},
        "UTC+8 (China, Singapore)": {"offset": 8, "probability": 0, "explanation": ""},
        "UTC+9 (Japan, Korea)": {"offset": 9, "probability": 0, "explanation": ""},
        "UTC+10 (Australia Eastern)": {"offset": 10, "probability": 0, "explanation": ""},
        "UTC+11 to UTC+12 (New Zealand)": {"offset": 11, "probability": 0, "explanation": ""},
    }
    
    # Define what hours are typically sleep hours (e.g., 11 PM to 7 AM local time)
    typical_sleep_hours = list(range(23, 24)) + list(range(0, 7))
    
    # Identify longest consecutive inactive period
    inactive_runs = []
    current_run = []
    
    # Find runs of low activity hours (normalized score > 0.8)
    for hour in range(24):
        if inactivity_scores[hour] > 0.8:
            current_run.append(hour)
        else:
            if current_run:
                inactive_runs.append(current_run)
                current_run = []
    
    if current_run:  # Don't forget the last run
        inactive_runs.append(current_run)
    
    # Handle case where inactivity wraps around midnight
    if inactive_runs and len(inactive_runs) > 1:
        if inactive_runs[0][0] == 0 and inactive_runs[-1][-1] == 23:
            inactive_runs = [inactive_runs[-1] + inactive_runs[0]] + inactive_runs[1:-1]
    
    longest_inactive_period = max(inactive_runs, key=len) if inactive_runs else []
    
    # For each timezone, check if the inactive hours match sleep hours
    for tz_name, tz_data in timezones.items():
        offset = tz_data["offset"]
        sleep_hours_local = []
        
        # Calculate sleep hours in UTC based on timezone offset
        for local_hour in typical_sleep_hours:
            utc_hour = int((local_hour - offset) % 24)  # Convert to integer for indexing
            sleep_hours_local.append(utc_hour)
        
        # Calculate typical awake hours
        awake_hours_local = [h for h in range(24) if h not in sleep_hours_local]
        
        # Sleep match: high inactivity during sleep hours
        sleep_inactivity = sum(inactivity_scores[int(h)] for h in sleep_hours_local) / len(sleep_hours_local)
        
        # Awake match: low inactivity during awake hours
        awake_activity = 1 - sum(inactivity_scores[int(h)] for h in awake_hours_local) / len(awake_hours_local)
        
        # Calculate overall match score (weighted average)
        overall_score = (sleep_inactivity * 0.7) + (awake_activity * 0.3)
        
        # Convert to a percentage and round to nearest 5%
        probability = min(95, max(5, round(overall_score * 100 / 5) * 5))
        
        # If we have a longest inactive period, check if it aligns with this timezone's expected sleep time
        if longest_inactive_period:
            local_inactive_start = int((longest_inactive_period[0] + offset) % 24)
            local_inactive_end = int((longest_inactive_period[-1] + offset) % 24)
            
            # If the inactive period aligns with typical sleep hours (evening to morning), boost the probability
            typical_sleep_start = 22  # 10 PM
            typical_sleep_end = 8     # 8 AM
            
            if ((local_inactive_start >= typical_sleep_start or local_inactive_start <= 3) and
                (local_inactive_end >= 5 and local_inactive_end <= typical_sleep_end)):
                # This is a good match - boost probability
                probability = min(95, probability + 15)
                
                # Generate explanation
                local_start = f"{local_inactive_start:02d}:00"
                local_end = f"{(local_inactive_end + 1) % 24:02d}:00"
                tz_data["explanation"] = f"Inactive {local_start}-{local_end} local time, aligns with typical sleep hours"
            else:
                # Generate explanation for less clear matches
                local_start = f"{local_inactive_start:02d}:00"
                local_end = f"{(local_inactive_end + 1) % 24:02d}:00"
                tz_data["explanation"] = f"Inactive {local_start}-{local_end} local time"
        else:
            # No clear inactive period
            tz_data["explanation"] = "No clear inactive period identified"
            probability = 10  # Low probability for inconsistent patterns
        
        tz_data["probability"] = probability
    
    # Display timezone probability table
    tz_table = Table(title="Probable Timezones Based on Inactivity Patterns")
    tz_table.add_column("Timezone", style="cyan")
    tz_table.add_column("Probability", style="green", justify="right")
    tz_table.add_column("Explanation", style="yellow")
    
    # Sort timezones by probability
    sorted_timezones = sorted(timezones.items(), key=lambda x: x[1]['probability'], reverse=True)
    
    # Show top 3 most likely timezones
    for tz, data in sorted_timezones[:3]:
        tz_table.add_row(
            tz,
            f"{data['probability']}%",
            data['explanation']
        )
    
    console.print(tz_table)
    
    # Write data to CSV
    timestamp = datetime.now().strftime('%Y%m%d%H%M')
    csv_filename = f'reports/activity_heatmap_{target_wallet}_{timestamp}.csv'
    
    with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=';')  # Using semicolon for LibreOffice compatibility
        # Write header with hours
        header = ['Day'] + [f"{hour:02d}:00" for hour in range(24)]
        writer.writerow(header)
        
        # Write data rows
        for day_idx, day_name in enumerate(days_of_week):
            row = [day_name] + [activity_grid[day_idx][hour] for hour in range(24)]
            writer.writerow(row)
        
        # Write totals
        writer.writerow(['TOTAL'] + hour_totals)
        
        # Write timezone data
        writer.writerow([])
        writer.writerow(['Timezone Analysis'])
        writer.writerow(['Timezone', 'Probability', 'Explanation'])
        for tz, data in sorted_timezones:
            writer.writerow([tz, f"{data['probability']}%", data['explanation']])
    
    console.print(f"\n[yellow]Activity data saved to {csv_filename}[/yellow]")

    # Write data to CSV
    # Create directory for this wallet address
    wallet_dir = f'reports/{target_wallet}'
    os.makedirs(wallet_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d%H%M')
    csv_filename = f'{wallet_dir}/activity_heatmap_{timestamp}.csv'
    
    with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=';')  # Using semicolon for LibreOffice compatibility
        # Write header with hours
        header = ['Day'] + [f"{hour:02d}:00" for hour in range(24)]
        writer.writerow(header)
        
        # Write data rows
        for day_idx, day_name in enumerate(days_of_week):
            row = [day_name] + [activity_grid[day_idx][hour] for hour in range(24)]
            writer.writerow(row)
        
        # Write totals
        writer.writerow(['TOTAL'] + hour_totals)
        
        # Write timezone data
        writer.writerow([])
        writer.writerow(['Timezone Analysis'])
        writer.writerow(['Timezone', 'Probability', 'Explanation'])
        for tz, data in sorted_timezones:
            writer.writerow([tz, f"{data['probability']}%", data['explanation']])
    
    console.print(f"\n[yellow]Activity data saved to {csv_filename}[/yellow]")

def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    # Load environment variables
    load_dotenv()
    
    api = SolscanAPI()
    console = Console()
    option = sys.argv[1]

    # Define csv_filename based on aggregation mode
    os.makedirs('reports', exist_ok=True)

    if option == "-1":
        option_1(api, console)
    elif option == "-2":
        option_2(api, console)
    elif option == "-3":
        option_3(api, console)
    elif option == "-4":
        option_4(api, console)
    elif option == "-5":
        option_5(api, console)
    elif option == "-6":
        option_6(api, console)
    elif option == "-8":
        option_8(api, console)
    else:
        print(f"Error: Unknown option {option}")
        print_usage()
        sys.exit(1)

if __name__ == "__main__":
    main()
