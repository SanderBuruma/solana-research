from rich.console import Console
from datetime import datetime, timedelta
from dotenv import load_dotenv
from rich.table import Table
import os
import sys
import re
import csv
import requests
import json
from rich.markdown import Markdown
from rich.panel import Panel

from utils.solscan import SolscanAPI, analyze_trades, display_transactions_table, filter_token_stats, format_token_address, format_token_amount

def is_sol_token(token: str) -> bool:
    """Check if a token address is SOL"""
    SOL_ADDRESSES = {
        "So11111111111111111111111111111111111111112",
        "So11111111111111111111111111111111111111111"
    }
    return token in SOL_ADDRESSES
    
def print_usage():
    """
    Display the README.md file with nice formatting in the terminal, but without emoji icons
    """
    console = Console()
    
    try:
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
    
    except FileNotFoundError:
        # Fallback if README.md not found
        console.print(Panel("[yellow]README.md file not found. Displaying basic usage information:[/yellow]", border_style="yellow"))
        console.print("\n[bold]Solana Research Tool Usage:[/bold]")
        console.print("-1 <address>     Get Account Balance")
        console.print("-2 <address>     View Transaction History")
        console.print("-3 <address>     View Balance History")
        console.print("-4 <address>     Detect Copy Traders")
        console.print("-5 <address>     View DeFi Summary for Wallets")
        console.print("-6 <token>       Get Holder Addresses using bullX")
        console.print("-7 <address>     Find Wallets Being Copied")
        console.print("\n[bold]Examples:[/bold]")
        console.print("python main.py -1 <address>")
        console.print("python main.py -2 <address>")
        console.print("python main.py -3 <address>")
        console.print("python main.py -4 <address>")
        console.print("python main.py -5 <address1> <address2> <address3>")
        console.print("python main.py -7 <address>")

    except Exception as e:
        # Handle any other errors gracefully
        console.print(f"[red]Error displaying README: {str(e)}[/red]")
        console.print("\n[bold]Solana Research Tool Usage:[/bold]")
        console.print("-1 <address>     Get Account Balance")
        console.print("-2 <address>     View Transaction History")
        console.print("-3 <address>     View Balance History")
        console.print("-4 <address>     Detect Copy Traders")
        console.print("-5 <address>     View DeFi Summary for Wallets")
        console.print("-6 <token>       Get Holder Addresses using bullX")
        console.print("-7 <address>     Find Wallets Being Copied")
        console.print("\n[bold]Examples:[/bold]")
        console.print("python main.py -1 <address>")
        console.print("python main.py -2 <address>")
        console.print("python main.py -3 <address>")
        console.print("python main.py -4 <address>")
        console.print("python main.py -5 <address1> <address2> <address3>")
        console.print("python main.py -7 <address>")

def option_1(api, console):       
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
        sys.exit(1)

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
            csv_filename = f"./reports/balance_{address}.csv"
            
            # Create CSV file with headers if it doesn't exist
            if not os.path.exists(csv_filename):
                with open(csv_filename, 'w') as f:
                    f.write("timestamp,sol_balance,token_balance,total_balance\n")
            
            # Append new balance data
            with open(csv_filename, 'a') as f:
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
def option_2(api, console):
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

def option_3(api, console):
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
    if not trades:
        api.console.print("[red]No DEX trading history found[/red]")
        return

    api.console.print(f"\nFound [green]{len(trades)}[/green] DEX trades\n")
    
    # Use the new analyze_trades function
    token_data, roi_data, tx_summary = analyze_trades(trades, api.console)
    
    # Apply filtering if specified
    if filter:
        # Convert token_data back to the format expected by filter_token_stats
        token_stats = {}
        for token in token_data:
            token_stats[token['address']] = {
                'trade_count': token['trades'],
                'hold_time': timedelta(seconds=token['hold_time']),
                'sol_invested': token['sol_invested'],
                'tokens_bought': 0,  # This will be fixed in analyze_trades
            }
        
        # Show the filter being applied
        console.print(f"\n[yellow]Applying filter: [cyan]{filter}[/cyan][/yellow]")
        filtered_stats = filter_token_stats(token_stats, filter)
        if not filtered_stats:
            console.print("[red]No tokens match the specified filter criteria[/red]")
            return
        # Filter token_data to match filtered_stats
        token_data = [t for t in token_data if t['address'] in filtered_stats]
        console.print(f"[green]{len(token_data)} tokens match the filter criteria[/green]\n")
    elif filter == "":
        # Show filter usage information
        filter_token_stats({}, None)
        return

    # Display token table
    table = Table(title="DEX Trading Summary")
    table.add_column("Token", style="dim")
    table.add_column("Hold Time", justify="right", style="blue")
    table.add_column("Last Trade", justify="right", style="cyan")
    table.add_column("First MC", justify="right", style="yellow")
    table.add_column("SOL Invested", justify="right", style="green")
    table.add_column("SOL Received", justify="right", style="green")
    table.add_column("SOL Profit", justify="right", style="green")
    table.add_column("Buy Fees", justify="right", style="red")
    table.add_column("Sell Fees", justify="right", style="red")
    table.add_column("Total Fees", justify="right", style="red")
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

    for token in token_data:
        # Format hold time
        hold_time_td = timedelta(seconds=token['hold_time'])
        if hold_time_td.days > 0:
            hold_time = f"{hold_time_td.days}d {hold_time_td.seconds//3600}h {(hold_time_td.seconds%3600)//60}m"
        elif hold_time_td.seconds//3600 > 0:
            hold_time = f"{hold_time_td.seconds//3600}h {(hold_time_td.seconds%3600)//60}m"
        else:
            hold_time = f"{(hold_time_td.seconds%3600)//60}m"

        # Format market cap with appropriate suffix and color
        mc = token['first_mc']
        if mc >= 1_000_000_000:
            mc_color = "red"
            mc_value = f"{mc/1_000_000_000:.1f}B"
        elif mc >= 200_000_000:
            mc_color = "yellow"
            mc_value = f"{mc/1_000_000:.1f}M"
        elif mc >= 1_000_000:
            mc_color = "green"
            mc_value = f"{mc/1_000_000:.1f}M"
        elif mc >= 250_000:
            mc_color = "green"
            mc_value = f"{mc/1_000:.1f}K"
        elif mc >= 25_000:
            mc_color = "yellow"
            mc_value = f"{mc/1_000:.1f}K"
        else:
            mc_color = "red"
            mc_value = f"{mc/1_000:.1f}K"

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
            f"{token['sol_invested']:.3f} ◎",
            f"{token['sol_received']:.3f} ◎",
            f"[{profit_color}]{token['sol_profit']:+.3f} ◎[/{profit_color}]",  # Already includes fees
            f"{token['buy_fees']:.3f} ◎",
            f"{token['sell_fees']:.3f} ◎",
            f"{token['total_fees']:.3f} ◎",
            f"{token['remaining_value']:.3f} ◎",
            f"[{total_profit_color}]{token['total_profit']:+.3f} ◎[/{total_profit_color}]",  # Already includes fees
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
        f"[bold]{total_buy_fees:.3f} ◎[/bold]",
        f"[bold]{total_sell_fees:.3f} ◎[/bold]",
        f"[bold]{total_fees:.3f} ◎[/bold]",
        f"[bold]{total_remaining:.3f} ◎[/bold]",
        f"[bold][{total_profit_style}]{(total_profit + total_remaining):+.3f} ◎[/{total_profit_style}][/bold]",  # Already includes fees
        "",
        f"[bold]{total_trades}[/bold]",
        end_section=True
    )

    console.print(table)

    # Display ROI table
    roi_table = Table(title="\nReturn on Investment (ROI)", show_header=True, header_style="bold")
    roi_table.add_column("Period", style="cyan")
    roi_table.add_column("SOL Invested", justify="right", style="green")
    roi_table.add_column("SOL Received", justify="right", style="red")
    roi_table.add_column("Profit/Loss", justify="right", style="yellow")
    roi_table.add_column("ROI %", justify="right", style="magenta")

    for period in ['24h', '7d', '30d']:
        period_data = roi_data[period]
        profit_color = "green" if period_data['profit'] >= 0 else "red"
        roi_color = "green" if period_data['roi_percent'] and period_data['roi_percent'] >= 0 else "red"
        
        roi_table.add_row(
            period.upper(),
            f"{period_data['invested']:.3f} ◎",
            f"{period_data['received']:.3f} ◎",
            f"[{profit_color}]{period_data['profit']:+.3f} ◎[/{profit_color}]",
            f"[{roi_color}]{period_data['roi_percent']:+.2f}%[/{roi_color}]" if period_data['roi_percent'] is not None else "N/A"
        )

    console.print(roi_table)

    # Display transaction summary table
    summary_table = Table(title="\nTransaction Summary", show_header=True, header_style="bold")
    summary_table.add_column("Transaction Type", style="cyan")
    summary_table.add_column("Count", justify="right", style="yellow")
    summary_table.add_column("Percentage", justify="right", style="green")

    summary_table.add_row(
        "Total DeFi Transactions",
        str(tx_summary['total_transactions']),
        "100%"
    )
    summary_table.add_row(
        "Non-SOL Token Swaps",
        str(tx_summary['non_sol_swaps']),
        f"{(tx_summary['non_sol_swaps']/tx_summary['total_transactions']*100):.1f}%" if tx_summary['total_transactions'] > 0 else "0%"
    )
    summary_table.add_row(
        "SOL-Involved Swaps",
        str(tx_summary['sol_swaps']),
        f"{(tx_summary['sol_swaps']/tx_summary['total_transactions']*100):.1f}%" if tx_summary['total_transactions'] > 0 else "0%"
    )

    # Add section for profit/loss statistics
    summary_table.add_section()
    win_rate_color = "green" if tx_summary['win_rate'] >= 50 else "red"
    win_rate = tx_summary['win_rate']
    summary_table.add_row(
        "Win Rate",
        f"[{win_rate_color}]{win_rate:.1f}%[/{win_rate_color}]",
        f"({tx_summary['win_rate_ratio']} tokens)"
    )
    summary_table.add_row(
        "Median Investment per Token",
        f"{tx_summary['median_investment']:.3f} ◎",
        ""
    )
    
    # Add the median ROI percentage
    summary_table.add_row(
        "Median ROI %",
        f"[{'green' if tx_summary['median_roi_percent'] >= 0 else 'red'}]{'+' if tx_summary['median_roi_percent'] >= 0 else ''}{tx_summary['median_roi_percent']:.1f}%[/{'green' if tx_summary['median_roi_percent'] >= 0 else 'red'}]",
        ""
    )
    

    median_hold_td = timedelta(seconds=tx_summary['median_hold_time'])
    if median_hold_td.days > 0:
        median_hold = f"{median_hold_td.days}d {median_hold_td.seconds//3600}h {(median_hold_td.seconds%3600)//60}m"
    elif median_hold_td.seconds//3600 > 0:
        median_hold = f"{median_hold_td.seconds//3600}h {(median_hold_td.seconds%3600)//60}m"
    else:
        median_hold = f"{(median_hold_td.seconds%3600)//60}m"

    summary_table.add_row(
        "Median Hold Time",
        median_hold,
        f"({tx_summary['win_rate_ratio']} tokens)"
    )

    # Add fee information
    summary_table.add_section()
    summary_table.add_row(
        "Total Buy Fees",
        f"[red]{total_buy_fees:.3f} ◎[/red]",
        f"({(total_buy_fees/total_invested*100):.1f}% of invested)" if total_invested > 0 else "N/A"
    )
    summary_table.add_row(
        "Total Sell Fees",
        f"[red]{total_sell_fees:.3f} ◎[/red]",
        f"({(total_sell_fees/total_received*100):.1f}% of received)" if total_received > 0 else "N/A"
    )
    summary_table.add_row(
        "Total Fees",
        f"[red]{total_fees:.3f} ◎[/red]",
        f"({(total_fees/(total_invested+total_received)*100):.1f}% of volume)" if (total_invested+total_received) > 0 else "N/A"
    )

    console.print("\n[bold]Transaction Summary[/bold]")
    console.print(summary_table)

    # Save to CSV
    os.makedirs('reports', exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d%H%M')
    csv_filename = f'reports/{address}.csv'
    
    with open(csv_filename, 'w') as f:
        f.write("Token,First Trade,Hold Time,Last Trade,First MC,SOL Invested,SOL Received,SOL Profit (after fees),Buy Fees,Sell Fees,Total Fees,Remaining Value,Total Profit (after fees),Token Price (USDT),Trades\n")
        for token in token_data:
            hold_time_td = timedelta(seconds=token['hold_time'])
            hold_time = f"{hold_time_td.days}d {hold_time_td.seconds//3600}h {(hold_time_td.seconds%3600)//60}m"
            f.write(f"{token['address']}," + 
                    f"{datetime.fromtimestamp(token['last_trade']).strftime('%Y-%m-%d %H:%M')}," +
                    f"{hold_time}," +
                    f"{datetime.fromtimestamp(token['last_trade']).strftime('%Y-%m-%d %H:%M')}," +
                    f"{token['first_mc']:.2f}," +
                    f"{token['sol_invested']:.3f}," +
                    f"{token['sol_received']:.3f}," +
                    f"{token['sol_profit']:.3f}," +  # Already includes fees
                    f"{token['buy_fees']:.3f}," +
                    f"{token['sell_fees']:.3f}," +
                    f"{token['total_fees']:.3f}," +
                    f"{token['remaining_value']:.3f}," +
                    f"{token['total_profit']:.3f}," +  # Already includes fees
                    f"{token['token_price']:.6f}," +
                    f"{token['trades']}\n")

        # Add totals to CSV
        total_overall_profit = total_profit + total_remaining  # Already includes fees
        f.write(f"TOTAL,,,," +
                f",{total_invested:.3f}," +
                f"{total_received:.3f}," +
                f"{total_profit:.3f}," +  # Already includes fees
                f"{total_buy_fees:.3f}," +
                f"{total_sell_fees:.3f}," +
                f"{total_fees:.3f}," +
                f"{total_remaining:.3f}," +
                f"{total_overall_profit:.3f},," +  # Already includes fees
                f"{total_trades}\n")

    console.print(f"\n[yellow]Report saved to {csv_filename}[/yellow]")

def option_5(api, console):
    if len(sys.argv) < 3:
        print("Error: At least one wallet address is required for option -5")
        print_usage()
        sys.exit(1)

    addresses = []
    first_arg = sys.argv[2]

    # Check if first argument is a .txt file
    if first_arg.endswith('.txt'):
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
    
    summary_table = Table(title="DeFi Summary for Wallets")
    summary_table.add_column("Address", style="cyan")
    summary_table.add_column("24H ROI %", justify="right", style="magenta")
    summary_table.add_column("7D ROI %", justify="right", style="magenta")
    summary_table.add_column("30D ROI %", justify="right", style="magenta")
    summary_table.add_column("30D ROI", justify="right", style="yellow")
    summary_table.add_column("Total Fees", justify="right", style="red")
    summary_table.add_column("Win Rate", justify="right", style="green")
    summary_table.add_column("Med Investment", justify="right", style="green")
    summary_table.add_column("Med ROI %", justify="right", style="magenta")
    summary_table.add_column("Med Hold Time", justify="right", style="blue")
    summary_table.add_column("nSol Swaps", justify="right", style="green")
    summary_table.add_column("Total Swaps", justify="right", style="green")
    
    total_wallets = len(addresses)
    for idx, addr in enumerate(addresses, 1):
        console.print(f"\n[yellow]Processing wallet {idx}/{total_wallets}: [cyan]{addr}[/cyan][/yellow]")
        trades = api.get_dex_trading_history(addr)
        if trades:
            console.print(f"Found [green]{len(trades)}[/green] DEX trades")
        else:
            console.print("[red]No DEX trading history found[/red]")
            continue

        # Use analyze_trades to get structured data
        token_data, roi_data, tx_summary = analyze_trades(trades, api.console)

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

        # Store result for CSV
        results.append({
            "Address": addr,
            "24H ROI %": f"{roi_data['24h']['roi_percent']:.2f}" if roi_data['24h']['roi_percent'] is not None else "N/A",
            "7D ROI %": f"{roi_data['7d']['roi_percent']:.2f}" if roi_data['7d']['roi_percent'] is not None else "N/A",
            "30D ROI %": f"{roi_data['30d']['roi_percent']:.2f}" if roi_data['30d']['roi_percent'] is not None else "N/A",
            "30D ROI": f"{roi_data['30d']['profit']:.3f}",  # Already includes fees
            "Total Fees": f"{total_fees:.3f}",
            "Buy Fees": f"{total_buy_fees:.3f}",
            "Sell Fees": f"{total_sell_fees:.3f}",
            "Win Rate": f"{tx_summary['win_rate']:.1f}",
            "Profitable/Total": tx_summary['win_rate_ratio'],
            "Median Investment": f"{tx_summary['median_investment']:.3f}",
            "Median ROI %": f"{'+' if tx_summary['median_roi_percent'] >= 0 else ''}{tx_summary['median_roi_percent']:.1f}%",
            "Median Hold Time": format_duration(timedelta(seconds=tx_summary['median_hold_time'])),
            "nSol Swaps": tx_summary['non_sol_swaps'],
            "Total Swaps": tx_summary['total_transactions']
        })
        
        # Color coding for display
        win_rate_color = "green" if tx_summary['win_rate'] >= 50 else "red"
        roi_24h = roi_data['24h']['roi_percent']  # Already includes fees
        roi_7d = roi_data['7d']['roi_percent']    # Already includes fees
        roi_30d = roi_data['30d']['roi_percent']  # Already includes fees
        
        # Color ROIs based on profit/loss (after fees)
        roi_24h_color = "green" if roi_24h and roi_24h > 0 else "red" if roi_24h and roi_24h < 0 else "white"
        roi_7d_color = "green" if roi_7d and roi_7d > 0 else "red" if roi_7d and roi_7d < 0 else "white"
        roi_30d_color = "green" if roi_30d and roi_30d > 0 else "red" if roi_30d and roi_30d < 0 else "white"
        
        summary_table.add_row(
            addr,
            f"[{roi_24h_color}]{roi_24h:+.2f}%[/{roi_24h_color}]" if roi_24h is not None else "N/A",
            f"[{roi_7d_color}]{roi_7d:+.2f}%[/{roi_7d_color}]" if roi_7d is not None else "N/A",
            f"[{roi_30d_color}]{roi_30d:+.2f}%[/{roi_30d_color}]" if roi_30d is not None else "N/A",
            f"{roi_data['30d']['profit']:.3f} SOL",  # Already includes fees
            f"[red]{total_fees:.3f} ◎[/red]",
            f"[{win_rate_color}]{tx_summary['win_rate']:.1f}% ({tx_summary['win_rate_ratio']})[/{win_rate_color}]",
            f"{tx_summary['median_investment']:.3f} ◎",
            f"{'+' if tx_summary['median_roi_percent'] >= 0 else ''}{tx_summary['median_roi_percent']:.1f}%",
            format_duration(timedelta(seconds=tx_summary['median_hold_time'])),
            str(tx_summary['non_sol_swaps']),
            str(tx_summary['total_transactions'])
        )
    
    # Print the table
    console.print(summary_table)
    
    # Save to CSV
    os.makedirs('reports', exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d%H%M')
    csv_filename = f'reports/{timestamp}-option5.csv'
    
    with open(csv_filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys() if results else [])
        writer.writeheader()
        writer.writerows(results)
    
    console.print(f"\n[yellow]Results saved to {csv_filename}[/yellow]")

def option_6(api, console):
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

def option_4(api, console):
    """
    Detect wallets that might be copy trading the target wallet
    
    Steps:
    1. Get the first 10 token buys for the target wallet
    2. For each token, get all trades and find wallets that bought within 30 seconds after the target
    3. Track wallets that show up multiple times (suggesting copy trading)
    4. Display summary of potential copy traders
    """
    if len(sys.argv) != 3:
        print("Error: Wallet address required for copy trader detection")
        print_usage()
        sys.exit(1)
    
    target_wallet = sys.argv[2]
    
    # Create a table to display results
    copy_traders_table = Table(title=f"Potential Copy Traders of {target_wallet}")
    copy_traders_table.add_column("Wallet Address", style="cyan")
    copy_traders_table.add_column("Copy Count", justify="right", style="yellow")
    copy_traders_table.add_column("Tokens", style="green")
    copy_traders_table.add_column("Avg Time Delay (s)", justify="right", style="magenta")
    
    # Dictionary to track potential copy traders
    copy_traders = {}  # Structure: {wallet_address: {'count': int, 'tokens': set, 'delays': list}}
    
    console.print(f"\n[yellow]Analyzing trading history for {target_wallet}...[/yellow]")
    trades = api.get_dex_trading_history(target_wallet)
    
    if not trades:
        console.print("[red]No DEX trading history found for this wallet[/red]")
        return
    
    console.print(f"Found [green]{len(trades)}[/green] DEX trades")
    
    # Get first buys for unique tokens (where target wallet bought a token using SOL)
    first_buys = {}  # {token_address: trade_data}
    for trade in trades:
        # Check if this is a buy (SOL -> token)
        if is_sol_token(trade.token1) and not is_sol_token(trade.token2):
            token = trade.token2
            if token not in first_buys:
                first_buys[token] = trade
                
                # Stop once we have 10 tokens
                if len(first_buys) >= 10:
                    break
    
    console.print(f"Analyzing first buys for [green]{len(first_buys)}[/green] unique tokens")
    
    # Track progress
    with console.status("[bold green]Scanning for copy traders...[/bold green]", spinner="dots") as status:
        # For each token, find wallets that bought within 30 seconds after the target
        for token, target_trade in first_buys.items():
            token_name = token[:5] + "..." + token[-5:]
            target_time = target_trade.block_time
            
            status.update(f"[bold green]Scanning transactions for token {token_name}...[/bold green]")
            
            # Get all trades for this token
            token_trades = api.get_dex_trading_history(token)
            
            # Find trades within 30 seconds after the target's trade
            for trade in token_trades:
                # Skip if it's not a buy (SOL -> token)
                if not is_sol_token(trade.token1) or is_sol_token(trade.token2):
                    continue
                    
                # Skip if it's the target wallet
                if trade.from_address == target_wallet:
                    continue
                
                # Check if the trade occurred within 30 seconds after the target's trade
                time_diff = trade.block_time - target_time
                if 0 < time_diff <= 30:
                    # Record this as a potential copy trade
                    if trade.from_address not in copy_traders:
                        copy_traders[trade.from_address] = {'count': 0, 'tokens': set(), 'delays': []}
                    
                    copy_traders[trade.from_address]['count'] += 1
                    copy_traders[trade.from_address]['tokens'].add(token)
                    copy_traders[trade.from_address]['delays'].append(time_diff)
    
    # Filter out wallets that only copied once
    copy_traders = {k: v for k, v in copy_traders.items() if v['count'] > 1}
    
    if not copy_traders:
        console.print("[yellow]No potential copy traders found[/yellow]")
        return
    
    # Sort by copy count (descending)
    sorted_copy_traders = sorted(copy_traders.items(), key=lambda x: x[1]['count'], reverse=True)
    
    # Add rows to the table
    for wallet, data in sorted_copy_traders:
        avg_delay = sum(data['delays']) / len(data['delays'])
        tokens_str = f"{len(data['tokens'])} unique tokens"
        
        copy_traders_table.add_row(
            wallet,
            str(data['count']),
            tokens_str,
            f"{avg_delay:.2f}"
        )
    
    console.print(copy_traders_table)
    
    # Save results to CSV
    os.makedirs('reports', exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d%H%M')
    csv_filename = f'reports/copy_traders_{target_wallet}_{timestamp}.csv'
    
    with open(csv_filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Wallet Address', 'Copy Count', 'Unique Tokens', 'Average Delay (s)'])
        
        for wallet, data in sorted_copy_traders:
            avg_delay = sum(data['delays']) / len(data['delays'])
            writer.writerow([
                wallet,
                data['count'],
                len(data['tokens']),
                f"{avg_delay:.2f}"
            ])
    
    console.print(f"\n[yellow]Results saved to {csv_filename}[/yellow]")

def option_7(api, console):
    """
    Detect wallets that the target wallet might be copy trading from
    
    Steps:
    1. Get the first 10 token buys for the target wallet
    2. For each token, get all trades and find wallets that bought within 30 seconds BEFORE the target
    3. Track wallets that show up multiple times (suggesting the target is copy trading them)
    4. Display summary of potential trading signals
    """
    if len(sys.argv) != 3:
        print("Error: Wallet address required for copy trading source detection")
        print_usage()
        sys.exit(1)
    
    target_wallet = sys.argv[2]
    
    # Create a table to display results
    copy_sources_table = Table(title=f"Wallets {target_wallet} Potentially Copy Trades From")
    copy_sources_table.add_column("Wallet Address", style="cyan")
    copy_sources_table.add_column("Copy Count", justify="right", style="yellow")
    copy_sources_table.add_column("Tokens", style="green")
    copy_sources_table.add_column("Avg Time Delay (s)", justify="right", style="magenta")
    
    # Dictionary to track potential copy sources
    copy_sources = {}  # Structure: {wallet_address: {'count': int, 'tokens': set, 'delays': list}}
    
    console.print(f"\n[yellow]Analyzing trading history for {target_wallet}...[/yellow]")
    trades = api.get_dex_trading_history(target_wallet)
    
    if not trades:
        console.print("[red]No DEX trading history found for this wallet[/red]")
        return
    
    console.print(f"Found [green]{len(trades)}[/green] DEX trades")
    
    # Get first buys for unique tokens (where target wallet bought a token using SOL)
    first_buys = {}  # {token_address: trade_data}
    for trade in trades:
        # Check if this is a buy (SOL -> token)
        if is_sol_token(trade.token1) and not is_sol_token(trade.token2):
            token = trade.token2
            if token not in first_buys:
                first_buys[token] = trade
                
                # Stop once we have 10 tokens
                if len(first_buys) >= 10:
                    break
    
    console.print(f"Analyzing first buys for [green]{len(first_buys)}[/green] unique tokens")
    
    # Track progress
    with console.status("[bold green]Scanning for trading signal sources...[/bold green]", spinner="dots") as status:
        # For each token, find wallets that bought within 30 seconds BEFORE the target
        for token, target_trade in first_buys.items():
            token_name = token[:5] + "..." + token[-5:]
            target_time = target_trade.block_time
            
            status.update(f"[bold green]Scanning transactions for token {token_name}...[/bold green]")
            
            # Get all trades for this token
            token_trades = api.get_dex_trading_history(token)
            
            # Find trades within 30 seconds BEFORE the target's trade
            for trade in token_trades:
                # Skip if it's not a buy (SOL -> token)
                if not is_sol_token(trade.token1) or is_sol_token(trade.token2):
                    continue
                    
                # Skip if it's the target wallet
                if trade.from_address == target_wallet:
                    continue
                
                # Check if the trade occurred within 30 seconds BEFORE the target's trade
                time_diff = target_time - trade.block_time
                if 0 < time_diff <= 30:
                    # Record this as a potential source trade
                    if trade.from_address not in copy_sources:
                        copy_sources[trade.from_address] = {'count': 0, 'tokens': set(), 'delays': []}
                    
                    copy_sources[trade.from_address]['count'] += 1
                    copy_sources[trade.from_address]['tokens'].add(token)
                    copy_sources[trade.from_address]['delays'].append(time_diff)
    
    # Filter out wallets that only appeared once
    copy_sources = {k: v for k, v in copy_sources.items() if v['count'] > 1}
    
    if not copy_sources:
        console.print("[yellow]No potential trading signal sources found[/yellow]")
        return
    
    # Sort by copy count (descending)
    sorted_copy_sources = sorted(copy_sources.items(), key=lambda x: x[1]['count'], reverse=True)
    
    # Add rows to the table
    for wallet, data in sorted_copy_sources:
        avg_delay = sum(data['delays']) / len(data['delays'])
        tokens_str = f"{len(data['tokens'])} unique tokens"
        
        copy_sources_table.add_row(
            wallet,
            str(data['count']),
            tokens_str,
            f"{avg_delay:.2f}"
        )
    
    console.print(copy_sources_table)
    
    # Save results to CSV
    os.makedirs('reports', exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d%H%M')
    csv_filename = f'reports/copy_sources_{target_wallet}_{timestamp}.csv'
    
    with open(csv_filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Wallet Address', 'Copy Count', 'Unique Tokens', 'Average Delay (s)'])
        
        for wallet, data in sorted_copy_sources:
            avg_delay = sum(data['delays']) / len(data['delays'])
            writer.writerow([
                wallet,
                data['count'],
                len(data['tokens']),
                f"{avg_delay:.2f}"
            ])
    
    console.print(f"\n[yellow]Results saved to {csv_filename}[/yellow]")

def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    # Load environment variables
    load_dotenv()
    
    api = SolscanAPI()
    console = Console()
    option = sys.argv[1]

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
    elif option == "-7":
        option_7(api, console)
    else:
        print(f"Error: Unknown option {option}")
        print_usage()
        sys.exit(1)

if __name__ == "__main__":
    main()
