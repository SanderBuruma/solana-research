from rich.console import Console
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

from utils.solscan import SolscanAPI, display_dex_trading_summary, display_transactions_table, filter_token_stats, format_token_amount

def is_sol_token(token: str) -> bool:
    """Check if a token address is SOL"""
    SOL_ADDRESSES = {
        "So11111111111111111111111111111111111111112",
        "So11111111111111111111111111111111111111111"
    }
    return token in SOL_ADDRESSES
    
def print_usage():
    """
    Print usage information
    """
    print("\nSolana Research Tool Usage:")
    print("==========================")
    print("-1 <address>     Get Account Balance")
    print("-2 <address>     View Transaction History")
    print("-3 <address>     View Balance History")
    print("-5 <address>     View DeFi Summary for Wallets")
    print("-6              Get Holder Addresses using bullX (must provide auth token from request headers findable through the network console)")
    print("\nExamples:")
    print("python main.py -1 <address>")
    print("python main.py -2 <address>")
    print("python main.py -3 <address>")
    print("python main.py -5 <address1> <address2> <address3>")
    print("==========================")

def main():
    import sys
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    # Load environment variables
    load_dotenv()
    
    api = SolscanAPI()
    console = Console()
    option = sys.argv[1]

    if option == "-1":
        if len(sys.argv) != 3:
            print("Error: Address required for account balance")
            print_usage()
            sys.exit(1)
        address = sys.argv[2]
        balance = api.get_account_balance(address)
        if balance is not None:
            api.console.print(f"\nAccount Balance: [green]{balance:.9f}[/green] SOL")
        else:
            api.console.print("[red]Failed to fetch account balance[/red]")

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
                
                # Display token table
                from rich.table import Table
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

    elif option == "-2":
        if len(sys.argv) != 3:
            print("Error: Address required for transaction history")
            print_usage()
            sys.exit(1)
        address = sys.argv[2]
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

    elif option == "-3":
        if len(sys.argv) <= 2:
            print("Error: Address required for balance history")
            print_usage()
            sys.exit(1)
        address = sys.argv[2]

        # Get the filter string wherever it appears if it appears
        filter = None
        for i, arg in enumerate(sys.argv):
            if arg == "-f":
                if not len(sys.argv) > i+1:
                    print("Error: Filter required")
                    filter_token_stats(None, '')
                    sys.exit(1)
                filter = sys.argv[i+1]
                break

        api.console.print("\nFetching DEX trading history...", style="yellow")
        trades = api.get_dex_trading_history(address)
        if trades:
            api.console.print(f"\nFound [green]{len(trades)}[/green] DEX trades\n")
            display_dex_trading_summary(trades, api.console, address, filter)
        else:
            api.console.print("[red]No DEX trading history found[/red]")

    elif option == "-5":
        if len(sys.argv) < 3:
            print("Error: At least one wallet address is required for option -5")
            print_usage()
            sys.exit(1)

        addresses = []
        first_arg = sys.argv[2]

        # Check if first argument is a .txt file
        if first_arg.endswith('.txt'):
            import re
            try:
                with open(first_arg, 'r') as f:
                    content = f.read()
                    # Find all Solana addresses (base58 strings of 43-44 characters)
                    found_addresses = re.findall(r'\b[a-zA-Z0-9]{43,44}\b', content)
                    if not found_addresses:
                        console.print(f"[red]No valid Solana addresses found in {first_arg}[/red]")
                        sys.exit(1)
                    addresses.extend(found_addresses)
                    console.print(f"[green]Found {len(addresses)} addresses in {first_arg}[/green]")
            except FileNotFoundError:
                console.print(f"[red]Error: File {first_arg} not found[/red]")
                sys.exit(1)
            except Exception as e:
                console.print(f"[red]Error reading file: {str(e)}[/red]")
                sys.exit(1)
        else:
            # Use command line arguments as addresses
            addresses = sys.argv[2:]

        # Store results for CSV export
        results = []
        
        from rich.table import Table
        summary_table = Table(title="DeFi Summary for Wallets")
        summary_table.add_column("Address", style="cyan")
        summary_table.add_column("24H ROI %", justify="right", style="magenta")
        summary_table.add_column("7D ROI %", justify="right", style="magenta")
        summary_table.add_column("30D ROI %", justify="right", style="magenta")
        summary_table.add_column("30D ROI", justify="right", style="yellow")
        summary_table.add_column("Win Rate", justify="right", style="green")
        summary_table.add_column("Med Investment", justify="right", style="green")
        summary_table.add_column("Med Profit", justify="right", style="green")
        summary_table.add_column("Med Loss", justify="right", style="red")
        summary_table.add_column("Med Hold Time", justify="right", style="blue")
        summary_table.add_column("nSol Swaps", justify="right", style="green")
        summary_table.add_column("Total Swaps", justify="right", style="green")
        SOL_ADDRESSES = {"So11111111111111111111111111111111111111112", "So11111111111111111111111111111111111111111"}
        now = datetime.now().timestamp()
        
        total_wallets = len(addresses)
        for idx, addr in enumerate(addresses, 1):
            console.print(f"\n[yellow]Processing wallet {idx}/{total_wallets}: [cyan]{addr}[/cyan][/yellow]")
            trades = api.get_dex_trading_history(addr)
            if trades:
                console.print(f"Found [green]{len(trades)}[/green] DEX trades")
            else:
                console.print("[red]No DEX trading history found[/red]")
                continue
                
            # Track token performance and period stats
            token_performance = {}  # {token: {"invested": 0, "received": 0, "first_trade": None, "last_trade": None}}
            period_stats = {
                "24h": {"invested": 0.0, "received": 0.0, "start": now - 86400},
                "7d": {"invested": 0.0, "received": 0.0, "start": now - 7 * 86400},
                "30d": {"invested": 0.0, "received": 0.0, "start": now - 30 * 86400}
            }
            non_sol_swaps = 0  # Initialize counter for non-SOL swaps
            
            for trade in trades:
                amount_info = trade.get('amount_info', {})
                if not amount_info:
                    continue
                token1 = amount_info.get('token1')
                token2 = amount_info.get('token2')
                token1_dec = amount_info.get('token1_decimals', 0)
                token2_dec = amount_info.get('token2_decimals', 0)
                try:
                    amt1 = float(amount_info.get('amount1', 0)) / (10 ** token1_dec)
                    amt2 = float(amount_info.get('amount2', 0)) / (10 ** token2_dec)
                except (ValueError, TypeError):
                    amt1 = 0
                    amt2 = 0
                trade_time = datetime.fromtimestamp(trade.get('block_time', 0))
                trade_timestamp = trade.get('block_time', 0)
                
                # Update period stats
                for period, stats in period_stats.items():
                    if trade_timestamp >= stats["start"]:
                        if token1 in SOL_ADDRESSES:
                            stats["invested"] += amt1
                        elif token2 in SOL_ADDRESSES:
                            stats["received"] += amt2
                
                # Track token performance
                if is_sol_token(token1) and token2:
                    # Buying token2 with SOL
                    if token2 not in token_performance:
                        token_performance[token2] = {"invested": 0, "received": 0, "first_trade": None, "last_trade": None}
                    token_performance[token2]["invested"] += amt1
                    token_performance[token2]["first_trade"] = min(trade_time, token_performance[token2]["first_trade"]) if token_performance[token2]["first_trade"] else trade_time
                    token_performance[token2]["last_trade"] = max(trade_time, token_performance[token2]["last_trade"]) if token_performance[token2]["last_trade"] else trade_time
                elif is_sol_token(token2) and token1:
                    # Selling token1 for SOL
                    if token1 not in token_performance:
                        token_performance[token1] = {"invested": 0, "received": 0, "first_trade": None, "last_trade": None}
                    token_performance[token1]["received"] += amt2
                    token_performance[token1]["first_trade"] = min(trade_time, token_performance[token1]["first_trade"]) if token_performance[token1]["first_trade"] else trade_time
                    token_performance[token1]["last_trade"] = max(trade_time, token_performance[token1]["last_trade"]) if token_performance[token1]["last_trade"] else trade_time
                
                if token1 and token2 and (token1 not in SOL_ADDRESSES and token2 not in SOL_ADDRESSES):
                    non_sol_swaps += 1
            
            # Calculate win rate
            profitable_tokens = 0
            unprofitable_tokens = 0
            profits = []
            losses = []
            investments = []  # Track all investments
            hold_times = []  # Track all hold times
            current_time = datetime.now()
            
            for token, perf in token_performance.items():
                sol_profit = perf["received"] - perf["invested"]
                investments.append(perf["invested"])  # Add investment to list
                if sol_profit > 0:
                    profitable_tokens += 1
                    profits.append(sol_profit)
                elif sol_profit < 0:
                    unprofitable_tokens += 1
                    losses.append(abs(sol_profit))
                
                # Calculate hold time if we have first trade
                if perf["first_trade"]:
                    # If no last trade or if tokens are still held (received < invested), use current time
                    end_time = perf["last_trade"] if perf["last_trade"] and perf["received"] >= perf["invested"] else current_time
                    if end_time:
                        duration = end_time - perf["first_trade"]
                        hold_times.append(duration)
                        perf["hold_time"] = duration  # Store for display
            
            total_traded_tokens = profitable_tokens + unprofitable_tokens
            win_rate = (profitable_tokens / total_traded_tokens * 100) if total_traded_tokens > 0 else 0
            
            # Calculate medians
            median_profit = sorted(profits)[len(profits)//2] if profits else 0
            median_loss = sorted(losses)[len(losses)//2] if losses else 0
            median_investment = sorted(investments)[len(investments)//2] if investments else 0
            median_hold_time = sorted(hold_times)[len(hold_times)//2] if hold_times else timedelta()
            
            # Calculate ROI percentages relative to median investment
            median_profit_roi = (median_profit / median_investment * 100) if median_investment > 0 else 0
            median_loss_roi = (median_loss / median_investment * 100) if median_investment > 0 else 0
            
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
            
            def calculate_roi(stats):
                """Calculate ROI relative to 0% (where 0% means no profit/loss), including remaining value"""
                if stats["invested"] > 0:
                    total_received = stats["received"] + stats.get("remaining_value", 0)
                    return ((total_received / stats["invested"]) - 1) * 100
                return 0.0
            
            # Store result for CSV
            results.append({
                "Address": addr,
                "24H ROI %": f"{calculate_roi(period_stats['24h']):.2f}",
                "7D ROI %": f"{calculate_roi(period_stats['7d']):.2f}",
                "30D ROI %": f"{calculate_roi(period_stats['30d']):.2f}",
                "30D ROI": f"{period_stats['30d']['received'] - period_stats['30d']['invested']:.3f}",
                "Win Rate": f"{win_rate:.1f}",
                "Profitable/Total": f"{profitable_tokens}/{total_traded_tokens}",
                "Median Investment": f"{median_investment:.3f}",
                "Median Profit": f"{median_profit:.3f} ({median_profit_roi:.1f}%)",
                "Median Loss": f"{median_loss:.3f} ({median_loss_roi:.1f}%)",
                "Median Hold Time": format_duration(median_hold_time),
                "nSol Swaps": non_sol_swaps,
                "Total Swaps": len(trades)
            })
            
            win_rate_color = "green" if win_rate >= 50 else "red"
            roi_24h = calculate_roi(period_stats['24h'])
            roi_7d = calculate_roi(period_stats['7d'])
            roi_30d = calculate_roi(period_stats['30d'])
            
            # Color ROIs based on profit/loss
            roi_24h_color = "green" if roi_24h > 0 else "red" if roi_24h < 0 else "white"
            roi_7d_color = "green" if roi_7d > 0 else "red" if roi_7d < 0 else "white"
            roi_30d_color = "green" if roi_30d > 0 else "red" if roi_30d < 0 else "white"
            
            summary_table.add_row(
                addr,
                f"[{roi_24h_color}]{roi_24h:+.2f}%[/{roi_24h_color}]",
                f"[{roi_7d_color}]{roi_7d:+.2f}%[/{roi_7d_color}]",
                f"[{roi_30d_color}]{roi_30d:+.2f}%[/{roi_30d_color}]",
                f"{period_stats['30d']['received'] - period_stats['30d']['invested']:.3f} SOL",
                f"[{win_rate_color}]{win_rate:.1f}% ({profitable_tokens}/{total_traded_tokens})[/{win_rate_color}]",
                f"{median_investment:.3f} ◎",
                f"+{median_profit:.3f} ◎ (+{median_profit_roi:.1f}%)" if median_profit > 0 else "N/A",
                f"-{median_loss:.3f} ◎ (-{median_loss_roi:.1f}%)" if median_loss > 0 else "N/A",
                format_duration(median_hold_time),
                str(non_sol_swaps),
                str(len(trades))
            )
        
        # Print the table
        console.print(summary_table)
        
        # Save to CSV
        import csv
        os.makedirs('reports', exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d%H%M')
        csv_filename = f'reports/{timestamp}-option5.csv'
        
        with open(csv_filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys() if results else [])
            writer.writeheader()
            writer.writerows(results)
        
        console.print(f"\n[yellow]Results saved to {csv_filename}[/yellow]")

    elif option == "-6":
        import requests
        import json

        if len(sys.argv) < 3:
            print("Error: One token contract address is required for option -6")
            print_usage()
            sys.exit(1)
        token_address = sys.argv[2:]
        
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
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            holders_data = response.json()
            
            # Save addresses to file
            with open("found_addresses_6.txt", "w") as f:
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
            
        except requests.exceptions.RequestException as e:
            console.print(f"[red]Error fetching data: {str(e)}[/red]")
            sys.exit(1)

    else:
        print(f"Error: Unknown option {option}")
        print_usage()
        sys.exit(1)

if __name__ == "__main__":
    main()
