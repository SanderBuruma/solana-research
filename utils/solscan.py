import requests
import os
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from typing import Dict, Any, Optional, List, Tuple

class SolscanAPI:
    def __init__(self):
        self.base_url = 'https://api-v2.solscan.io/v2'
        self.headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en-GB,en;q=0.8',
            'origin': 'https://solscan.io',
            'priority': 'u=1, i',
            'referer': 'https://solscan.io/',
            'sec-ch-ua': '"Not(A:Brand";v="99", "Brave";v="133", "Chromium";v="133"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'sec-gpc': '1',
            'sol-aut': os.getenv('SOLSCAN_SOL_AUT'),
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36'
        }
        self.console = Console()

    def _make_request(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """
        Make a request to the Solscan API
        """
        url = f'{self.base_url}/{endpoint}'
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error making request: {e}")
            return None

    def get_account_balance(self, address: str) -> Optional[float]:
        """
        Get the balance of a Solana account in SOL
        """
        data = self._make_request(f'account?address={address}')
        if data and data.get('success'):
            lamports = int(data['data'].get('lamports', 0))
            sol_balance = lamports / 1_000_000_000  # Convert to SOL
            return sol_balance
        return None

    def get_account_transactions(self, address: str, page: int = 1, page_size: int = 10) -> Optional[List[Dict[str, Any]]]:
        """
        Get transaction history for a Solana account
        """
        endpoint = f'account/transfer?address={address}&page={page}&page_size={page_size}&remove_spam=true&exclude_amount_zero=true'
        data = self._make_request(endpoint)
        
        if data and data.get('success'):
            return data.get('data', [])
        return None

    def get_dex_trading_history(self, address: str) -> List[Dict[str, Any]]:
        """
        Get complete DEX trading history for an account, up to 1 month old
        """
        page = 1
        page_size = 100
        all_trades = []
        one_month_ago = datetime.now().timestamp() - (30 * 86400)  # 30 days in seconds
        
        while True:
            endpoint = f'account/activity/dextrading?address={address}&page={page}&page_size={page_size}&activity_type[]=ACTIVITY_TOKEN_SWAP'
            data = self._make_request(endpoint)
            
            if not data or not data.get('success') or not data.get('data'):
                break
                
            trades = data['data']
            if not trades:
                break
            
            # Check each trade's timestamp before adding
            for trade in trades:
                if trade['block_time'] < one_month_ago:
                    # Stop gathering data if we reach trades older than a month
                    return all_trades
                all_trades.append(trade)
            
            if len(trades) < page_size:
                break
                
            page += 1
        
        return all_trades

    def get_token_price(self, token_address: str) -> Optional[Dict[str, Any]]:
        """
        Get token price and metadata from Solscan API
        Returns a dictionary containing price in USDT and other token information
        """
        data = self._make_request(f'account?address={token_address}')
        if data and data.get('success'):
            metadata = data.get('metadata', {})
            token_info = data.get('data', {}).get('tokenInfo', {})
            token_metadata = data.get('metadata', {}).get('tokens', {}).get(token_address, {})
            
            return {
                'price_usdt': token_metadata.get('price_usdt', 0),
                'decimals': token_info.get('decimals', 0),
                'name': metadata.get('data', {}).get('name', ''),
                'symbol': metadata.get('data', {}).get('symbol', '')
            }
        return None

    def get_token_accounts(self, address: str) -> Optional[Dict[str, Any]]:
        """Get token accounts for a given Solana address."""
        endpoint = f'account/tokenaccounts?address={address}&page=1&page_size=480&type=token&hide_zero=true'
        return self._make_request(endpoint)

def display_transactions_table(transactions: List[Dict[str, Any]], console: Console, input_address: str):
    """
    Display transactions in a rich table format
    """
    table = Table(title="Transaction History")
    
    # Add columns
    table.add_column("Time", justify="left", style="cyan")
    table.add_column("Type", justify="center", style="magenta")
    table.add_column("Amount (SOL)", justify="right", style="green")
    table.add_column("From", justify="right")
    table.add_column("To", justify="left")
    table.add_column("Value (USD)", justify="right", style="yellow")
    
    # Add rows
    for tx in transactions:
        timestamp = datetime.fromtimestamp(tx['block_time']).strftime('%Y-%m-%d %H:%M')
        amount = float(tx['amount']) / (10 ** tx['token_decimals'])
        direction = "→" if tx['flow'] == 'out' else "←"
        
        # Format addresses with styles inline
        from_addr = f"[dim]{f'...{tx['from_address'][-5:]}'}" if tx['from_address'] == input_address else f"[blue]{f'...{tx['from_address'][-5:]}'}"
        to_addr = f"[dim]{f'...{tx['to_address'][-5:]}'}" if tx['to_address'] == input_address else f"[blue]{f'...{tx['to_address'][-5:]}'}"
        
        table.add_row(
            timestamp,
            tx['activity_type'].replace('ACTIVITY_', ''),
            f"{amount:.4f} {direction}",
            from_addr,
            to_addr,
            f"${tx.get('value', 0):.2f}",
            end_section=True  # Add subtle separator between rows
        )
    
    console.print(table)

def display_balance_history(transactions: List[Dict[str, Any]], current_balance: float, console: Console, input_address: str):
    """
    Display balance history by analyzing transactions
    """
    table = Table(title="Balance History")
    
    # Add columns
    table.add_column("Time", justify="left", style="cyan")
    table.add_column("Transaction", justify="center", style="magenta")
    table.add_column("Change", justify="right", style="green")
    table.add_column("Balance", justify="right", style="yellow")
    
    # Calculate balance changes starting from current balance
    balance = current_balance
    balance_history: List[Tuple[datetime, str, float, float]] = []
    
    for tx in reversed(transactions):  # Process oldest to newest
        timestamp = datetime.fromtimestamp(tx['block_time'])
        amount = float(tx['amount']) / (10 ** tx['token_decimals'])
        
        if tx['flow'] == 'out':
            old_balance = balance + amount
            change = f"-{amount:.4f}"
        else:
            old_balance = balance - amount
            change = f"+{amount:.4f}"
            
        balance_history.append((timestamp, tx['activity_type'].replace('ACTIVITY_', ''), amount, old_balance))
        balance = old_balance
    
    # Display in chronological order
    for timestamp, tx_type, amount, bal in balance_history:
        change_color = "red" if amount < 0 else "green"
        table.add_row(
            timestamp.strftime('%Y-%m-%d %H:%M'),
            tx_type,
            f"[{change_color}]{'+' if amount > 0 else '-'}{abs(amount):.4f}[/{change_color}]",
            f"{bal:.4f}",
            end_section=True
        )
    
    # Add current balance as last row
    table.add_row(
        "[bold]Current[/bold]",
        "",
        "",
        f"[bold yellow]{current_balance:.4f}[/bold yellow]"
    )
    
    console.print(table)

def format_token_amount(amount: float) -> str:
    """Format token amount in k/m/b format"""
    if amount >= 1_000_000_000:
        return f"{amount/1_000_000_000:.1f}B"
    elif amount >= 1_000_000:
        return f"{amount/1_000_000:.1f}M"
    elif amount >= 1_000:
        return f"{amount/1_000:.1f}k"
    else:
        return f"{amount:.0f}"

def format_token_address(address: str) -> str:
    """Format token address to show first 4 and last 4 characters"""
    if address == "So11111111111111111111111111111111111111112" or address == "So11111111111111111111111111111111111111111":
        return "SOL"
    return f"{address[:4]}...{address[-4:]}"

def format_time_difference(first: datetime, last: datetime) -> str:
    """Format time difference between two dates in a human-readable format"""
    diff = last - first
    days = diff.days
    hours = diff.seconds // 3600
    minutes = (diff.seconds % 3600) // 60
    
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"

def get_hold_time_color(first: datetime, last: datetime) -> str:
    """Determine color for hold time based on duration"""
    diff = last - first
    total_minutes = diff.days * 1440 + diff.seconds // 60  # Convert to total minutes
    
    if total_minutes < 2:
        return "red"
    elif total_minutes < 10:
        return "yellow"
    return "green"

def display_dex_trading_summary(trades: List[Dict[str, Any]], console: Console, wallet_address: str, filter_str: Optional[str] = None):
    """
    Display DEX trading summary grouped by token and save to CSV
    
    Args:
        trades: List of trades to analyze
        console: Rich console for output
        wallet_address: Address of the wallet being analyzed
        filter_str: Optional filter string to filter token statistics
    """
    # Dictionary to track token stats
    token_stats = {}
    period_stats = {
        '24h': {'invested': 0, 'received': 0, 'start_time': datetime.now().timestamp() - 86400},
        '7d': {'invested': 0, 'received': 0, 'start_time': datetime.now().timestamp() - 7 * 86400},
        '30d': {'invested': 0, 'received': 0, 'start_time': datetime.now().timestamp() - 30 * 86400}
    }
    SOL_ADDRESSES = {
        "So11111111111111111111111111111111111111112",
        "So11111111111111111111111111111111111111111"
    }

    def is_sol_token(token: str) -> bool:
        """Check if a token is SOL"""
        return token in SOL_ADDRESSES
    
    # First pass: collect all trades and update period stats
    for trade in trades:
        amount_info = trade.get('amount_info', {})
        if not amount_info:
            continue
            
        # Extract token information from amount_info
        token1 = amount_info.get('token1')
        token2 = amount_info.get('token2')
        token1_decimals = amount_info.get('token1_decimals', 0)
        token2_decimals = amount_info.get('token2_decimals', 0)
        
        # Ignore vault dex activity
        if not token1 or not token2:
            continue
        
        # Safely convert amounts to float with null checks
        try:
            amount1_raw = amount_info.get('amount1')
            amount2_raw = amount_info.get('amount2')
            amount1 = float(amount1_raw if amount1_raw is not None else 0) / (10 ** token1_decimals)
            amount2 = float(amount2_raw if amount2_raw is not None else 0) / (10 ** token2_decimals)
        except (ValueError, TypeError):
            # Skip this trade if amounts are invalid
            continue
        
        trade_time = datetime.fromtimestamp(trade['block_time'])
        trade_timestamp = trade['block_time']
        
        # Update period stats
        for period, stats in period_stats.items():
            if trade_timestamp >= stats['start_time']:
                if is_sol_token(token1):
                    stats['invested'] += amount1
                elif is_sol_token(token2):
                    stats['received'] += amount2
        
        # Initialize token stats if needed (excluding SOL tokens)
        for token in [token1, token2]:
            if token and not is_sol_token(token) and token not in token_stats:
                token_stats[token] = {
                    'sol_invested': 0,  # SOL spent to buy this token
                    'sol_received': 0,  # SOL received from selling this token
                    'tokens_bought': 0,  # Amount of tokens bought
                    'tokens_sold': 0,    # Amount of tokens sold
                    'last_trade': None,
                    'first_trade': None,  # Track first trade date
                    'last_sol_rate': 0,  # Last known SOL/token rate
                    'token_price_usdt': 0,  # Current token price in USDT
                    'decimals': 0,  # Token decimals
                    'name': '',  # Token name
                    'symbol': '',  # Token symbol
                    'hold_time': None,  # Added for the new hold time calculation
                    'trade_count': 0  # Added for trade count
                }
        
        # Update stats based on trade direction
        if is_sol_token(token1) and not is_sol_token(token2):
            # Sold SOL for tokens
            token_stats[token2]['sol_invested'] += amount1
            token_stats[token2]['tokens_bought'] += amount2
            token_stats[token2]['last_sol_rate'] = amount1 / (amount2 or 0.0000000001)  # SOL per token
            token_stats[token2]['last_trade'] = max(trade_time, token_stats[token2]['last_trade']) if token_stats[token2]['last_trade'] else trade_time
            token_stats[token2]['first_trade'] = min(trade_time, token_stats[token2]['first_trade']) if token_stats[token2]['first_trade'] else trade_time
        elif is_sol_token(token2) and not is_sol_token(token1):
            # Sold tokens for SOL
            token_stats[token1]['sol_received'] += amount2
            token_stats[token1]['tokens_sold'] += amount1
            token_stats[token1]['last_sol_rate'] = amount2 / (amount1 or 0.0000000001)  # SOL per token
            token_stats[token1]['last_trade'] = max(trade_time, token_stats[token1]['last_trade']) if token_stats[token1]['last_trade'] else trade_time
            token_stats[token1]['first_trade'] = min(trade_time, token_stats[token1]['first_trade']) if token_stats[token1]['first_trade'] else trade_time
        
        # Update trade count
        if token1 and not is_sol_token(token1):
            token_stats[token1]['trade_count'] += 1
        if token2 and not is_sol_token(token2):
            token_stats[token2]['trade_count'] += 1
    
    # Fetch current token prices for tokens with remaining balance
    api = SolscanAPI()
    sol_price = api.get_token_price("So11111111111111111111111111111111111111112")
    sol_price_usdt = sol_price.get('price_usdt', 0) if sol_price else 0
    
    console.print("\n[yellow]Fetching current token prices...[/yellow]")
    for token, stats in token_stats.items():
        remaining_tokens = stats['tokens_bought'] - stats['tokens_sold']
        if remaining_tokens >= 100:  # Only fetch price if significant remaining balance
            token_data = api.get_token_price(token)
            if token_data:
                stats['token_price_usdt'] = token_data.get('price_usdt', 0)
                stats['decimals'] = token_data.get('decimals', 0)
                stats['name'] = token_data.get('name', '')
                stats['symbol'] = token_data.get('symbol', '')
    
    # Calculate hold time for each token
    current_time = datetime.now()
    for token, stats in token_stats.items():
        remaining_tokens = stats['tokens_bought'] - stats['tokens_sold']
        if stats['first_trade']:
            # If tokens are still held, use current time as the end time
            if remaining_tokens > 0:
                stats['last_trade'] = current_time
            # Calculate hold time
            if stats['last_trade']:
                duration = stats['last_trade'] - stats['first_trade']
                stats['hold_time'] = duration

    # Apply filtering before displaying results
    if filter_str:
        # Show the filter being applied
        console.print(f"\n[yellow]Applying filter: [cyan]{filter_str}[/cyan][/yellow]")
        token_stats = filter_token_stats(token_stats, filter_str)
        if not token_stats:
            console.print("[red]No tokens match the specified filter criteria[/red]")
            return
        console.print(f"[green]{len(token_stats)} tokens match the filter criteria[/green]\n")
    elif filter_str == "":
        # Show filter usage information
        filter_token_stats({}, None)
        return

    # Sort by first trade date
    sorted_tokens = sorted(
        [(k, v) for k, v in token_stats.items() if not is_sol_token(k)],
        key=lambda x: x[1]['first_trade'] if x[1]['first_trade'] else datetime.max
    )
    
    # Create the table
    table = Table(title="DEX Trading Summary")
    table.add_column("Token", style="dim")
    table.add_column("Hold Time", justify="right", style="blue")
    table.add_column("Last Trade", justify="right", style="cyan")
    table.add_column("First MC", justify="right", style="yellow")
    table.add_column("SOL Invested", justify="right", style="green")
    table.add_column("SOL Received", justify="right", style="green")
    table.add_column("SOL Profit", justify="right", style="green")
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
    
    # Prepare CSV data
    os.makedirs('reports', exist_ok=True)
    csv_file = f'reports/{wallet_address}.csv'
    with open(csv_file, 'w') as f:
        f.write("Token,First Trade,Hold Time,Last Trade,First MC,SOL Invested,SOL Received,SOL Profit,Remaining Value,Total Profit,Token Price (USDT),Trades\n")
        
        for token, stats in sorted_tokens:
            remaining_tokens = stats['tokens_bought'] - stats['tokens_sold']
            sol_profit = stats['sol_received'] - stats['sol_invested']
            
            # Calculate remaining value using current token price if available
            token_price = stats.get('token_price_usdt')
            if token_price is not None and token_price > 0 and sol_price_usdt > 0:
                remaining_value = (remaining_tokens * token_price) / sol_price_usdt
            else:
                remaining_value = remaining_tokens * stats.get('last_sol_rate', 0)
            
            total_token_profit = sol_profit + remaining_value
            
            # Calculate number of trades for this token
            token_trades = sum(1 for trade in trades if 
                trade.get('amount_info', {}).get('token1') == token or 
                trade.get('amount_info', {}).get('token2') == token)
            total_trades += token_trades
            
            total_invested += stats['sol_invested']
            total_received += stats['sol_received']
            total_profit += sol_profit
            total_remaining += remaining_value
            
            profit_color = "green" if sol_profit >= 0 else "red"
            total_profit_color = "green" if total_token_profit >= 0 else "red"
            
            # Format token price display
            token_price_display = f"${token_price:.6f}" if token_price is not None and token_price > 0 else "N/A"
            
            # Format hold time with color
            first_trade = stats.get('first_trade')
            last_trade = stats.get('last_trade')
            hold_time = format_time_difference(first_trade, last_trade) if first_trade and last_trade else 'N/A'
            if hold_time != 'N/A':
                hold_time_color = get_hold_time_color(first_trade, last_trade)
                hold_time = f"[{hold_time_color}]{hold_time}[/{hold_time_color}]"
                if remaining_tokens > 0:
                    hold_time += " [dim]*[dim]"
            
            # Calculate first trade market cap (assuming 1B supply)
            tokens_bought = stats.get('tokens_bought', 0)
            first_trade_rate = stats['sol_invested'] / tokens_bought if tokens_bought > 0 else 0
            first_trade_mc = first_trade_rate * sol_price_usdt * 1_000_000_000  # 1B tokens
            
            # Format market cap display with appropriate suffix and color
            if first_trade_mc > 0:
                # Determine color based on market cap thresholds
                if first_trade_mc >= 1_000_000_000:  # Over 1B
                    mc_color = "red"
                    mc_value = f"{first_trade_mc/1_000_000_000:.1f}B"
                elif first_trade_mc >= 200_000_000:  # Over 200M
                    mc_color = "yellow"
                    mc_value = f"{first_trade_mc/1_000_000:.1f}M"
                elif first_trade_mc >= 1_000_000:  # Over 1M
                    mc_color = "green"
                    mc_value = f"{first_trade_mc/1_000_000:.1f}M"
                elif first_trade_mc >= 250_000:  # Over 250K
                    mc_color = "green"
                    mc_value = f"{first_trade_mc/1_000:.1f}K"
                elif first_trade_mc >= 25_000:  # Over 50K
                    mc_color = "yellow"
                    mc_value = f"{first_trade_mc/1_000:.1f}K"
                else:  # Under 25K
                    mc_color = "red"
                    mc_value = f"{first_trade_mc/1_000:.1f}K"
                
                mc_display = f"[{mc_color}]{mc_value}[/{mc_color}]"
            else:
                mc_display = "N/A"
            
            # Add to table
            table.add_row(
                format_token_address(token),
                hold_time,
                stats.get('last_trade').strftime('%Y-%m-%d %H:%M') if stats.get('last_trade') else 'N/A',
                mc_display,
                f"{stats.get('sol_invested', 0):.3f} ◎",
                f"{stats.get('sol_received', 0):.3f} ◎",
                f"[{profit_color}]{sol_profit:+.3f} ◎[/{profit_color}]",
                f"{remaining_value:.3f} ◎",
                f"[{total_profit_color}]{total_token_profit:+.3f} ◎[/{total_profit_color}]",
                token_price_display,
                str(token_trades)
            )
            
            # Write to CSV (keep both absolute and relative times)
            # Handle missing token information
            try:
                token_price_csv = stats.get('token_price_usdt')
                if token_price_csv is None:
                    token_price_csv = 0
                
                first_trade_str = stats.get('first_trade').strftime('%Y-%m-%d %H:%M') if stats.get('first_trade') else 'N/A'
                last_trade_str = stats.get('last_trade').strftime('%Y-%m-%d %H:%M') if stats.get('last_trade') else 'N/A'
                hold_time_str = format_time_difference(stats.get('first_trade'), stats.get('last_trade')) if stats.get('first_trade') and stats.get('last_trade') else 'N/A'
                
                f.write(f"{token}," + 
                       f"{first_trade_str}," +
                       f"{hold_time_str}," +
                       f"{last_trade_str}," +
                       f"{first_trade_mc:.2f}," +
                       f"{stats.get('sol_invested', 0):.3f}," +
                       f"{stats.get('sol_received', 0):.3f}," +
                       f"{sol_profit:.3f}," +
                       f"{'ERROR' if token_price_csv is None else remaining_value:.3f}," +
                       f"{total_token_profit:.3f}," +
                       f"{token_price_csv:.6f}," +
                       f"{token_trades}\n")
            except Exception as e:
                # If any error occurs while writing token data, write a safe fallback row
                f.write(f"{token},N/A,N/A,N/A,0.00,{stats.get('sol_invested', 0):.3f},{stats.get('sol_received', 0):.3f}," +
                       f"{sol_profit:.3f},ERROR,{total_token_profit:.3f},0.000000,{token_trades}\n")
    
        # Add totals to CSV
        total_overall_profit = total_profit + total_remaining
        f.write(f"TOTAL,{total_invested:.3f},{total_received:.3f},{total_profit:.3f},{total_remaining:.3f},{total_overall_profit:.3f},,,{total_trades},\n")
    
    # Add totals row to table
    profit_style = "green" if total_profit >= 0 else "red"
    total_profit_style = "green" if total_overall_profit >= 0 else "red"
    table.add_row(
        "[bold]TOTAL[/bold]",
        "",
        "",
        "",
        f"[bold]{total_invested:.3f} ◎[/bold]",
        f"[bold]{total_received:.3f} ◎[/bold]",
        f"[bold][{profit_style}]{total_profit:+.3f} ◎[/{profit_style}][/bold]",
        f"[bold]{total_remaining:.3f} ◎[/bold]",
        f"[bold][{total_profit_style}]{total_overall_profit:+.3f} ◎[/{total_profit_style}][/bold]",
        "",
        f"[bold]{total_trades}[/bold]",
        end_section=True
    )
    
    console.print(table)
    console.print(f"\n[yellow]Report saved to {csv_file}[/yellow]")
    
    # Calculate and display ROI for different periods
    console.print("\n[bold]Return on Investment (ROI)[/bold]")
    roi_table = Table(show_header=True, header_style="bold")
    roi_table.add_column("Period", style="cyan")
    roi_table.add_column("SOL Invested", justify="right", style="green")
    roi_table.add_column("SOL Received", justify="right", style="red")
    roi_table.add_column("Profit/Loss", justify="right", style="yellow")
    roi_table.add_column("ROI %", justify="right", style="magenta")
    
    # Track remaining value per period
    period_remaining_value = {
        '24h': 0,
        '7d': 0,
        '30d': 0
    }
    
    # Calculate remaining value for each period using current token prices
    current_time = datetime.now().timestamp()
    for token, stats in token_stats.items():
        remaining_tokens = stats['tokens_bought'] - stats['tokens_sold']
        
        # Calculate remaining value using current token price if available
        token_price = stats.get('token_price_usdt')
        if token_price is not None and token_price > 0 and sol_price_usdt > 0:
            remaining_value = (remaining_tokens * token_price) / sol_price_usdt
        else:
            remaining_value = remaining_tokens * stats.get('last_sol_rate', 0)
        
        if stats.get('last_trade'):
            last_trade_time = stats['last_trade'].timestamp()
            # Add remaining value to each period where the last trade falls within the period
            if last_trade_time >= current_time - 86400:  # 24h
                period_remaining_value['24h'] += remaining_value
            if last_trade_time >= current_time - 7 * 86400:  # 7d
                period_remaining_value['7d'] += remaining_value
            if last_trade_time >= current_time - 30 * 86400:  # 30d
                period_remaining_value['30d'] += remaining_value
    
    for period, stats in period_stats.items():
        invested = stats.get('invested', 0)
        if invested > 0:
            # Include remaining value in profit calculation
            total_received = stats.get('received', 0) + period_remaining_value.get(period, 0)
            profit = total_received - invested
            roi_percent = ((total_received / invested) - 1) * 100
            profit_color = "green" if profit >= 0 else "red"
            roi_color = "green" if roi_percent >= 0 else "red"
            
            roi_table.add_row(
                period.upper(),
                f"{invested:.3f} ◎",
                f"{total_received:.3f} ◎",  # Show total including remaining value
                f"[{profit_color}]{profit:+.3f} ◎[/{profit_color}]",
                f"[{roi_color}]{roi_percent:+.2f}%[/{roi_color}]"
            )
        else:
            roi_table.add_row(
                period.upper(),
                "0.000 ◎",
                "0.000 ◎",
                "0.000 ◎",
                "N/A"
            )
    
    console.print(roi_table)

    # Count transactions
    total_defi_txs = len(trades)
    non_sol_txs = 0

    for trade in trades:
        amount_info = trade.get('amount_info', {})
        if not amount_info:
            continue
            
        token1 = amount_info.get('token1')
        token2 = amount_info.get('token2')
        
        # Count if neither token is SOL
        if token1 and token2 and token1 not in SOL_ADDRESSES and token2 not in SOL_ADDRESSES:
            non_sol_txs += 1

    # Calculate median profit and loss and holding times
    profits = []
    losses = []
    investments = []  # Track all investments
    hold_times = []  # Track all hold times
    for token, stats in token_stats.items():
        sol_profit = stats['sol_received'] - stats['sol_invested']
        investments.append(stats['sol_invested'])  # Add investment to list
        if sol_profit > 0:
            profits.append(sol_profit)
        elif sol_profit < 0:
            losses.append(abs(sol_profit))  # Store absolute value of losses
        
        # Calculate and store hold time
        if stats['first_trade'] and stats['last_trade'] and stats['first_trade'] != stats['last_trade']:
            duration = stats['last_trade'] - stats['first_trade']
            hold_times.append(duration)
    
    # Calculate medians
    median_profit = sorted(profits)[len(profits)//2] if profits else 0
    median_loss = sorted(losses)[len(losses)//2] if losses else 0
    median_investment = sorted(investments)[len(investments)//2] if investments else 0
    median_hold_time = sorted(hold_times)[len(hold_times)//2] if hold_times else timedelta()

    # Calculate win rate
    total_tokens = len(profits) + len(losses)
    win_rate = (len(profits) / total_tokens * 100) if total_tokens > 0 else 0
    win_rate_color = "green" if win_rate >= 50 else "red"

    # Calculate ROI percentages relative to median investment
    median_profit_roi = (median_profit / median_investment * 100) if median_investment > 0 else 0
    median_loss_roi = (median_loss / median_investment * 100) if median_investment > 0 else 0

    # Display transaction summary
    summary_table = Table(show_header=True, header_style="bold")
    summary_table.add_column("Transaction Type", style="cyan")
    summary_table.add_column("Count", justify="right", style="yellow")
    summary_table.add_column("Percentage", justify="right", style="green")

    summary_table.add_row(
        "Total DeFi Transactions",
        str(total_defi_txs),
        "100%"
    )
    summary_table.add_row(
        "Non-SOL Token Swaps",
        str(non_sol_txs),
        f"{(non_sol_txs/total_defi_txs*100):.1f}%" if total_defi_txs > 0 else "0%"
    )
    summary_table.add_row(
        "SOL-Involved Swaps",
        str(total_defi_txs - non_sol_txs),
        f"{((total_defi_txs-non_sol_txs)/total_defi_txs*100):.1f}%" if total_defi_txs > 0 else "0%"
    )

    # Add section for profit/loss statistics
    summary_table.add_section()
    summary_table.add_row(
        "Win Rate",
        f"[{win_rate_color}]{win_rate:.1f}%[/{win_rate_color}]",
        f"({len(profits)}/{total_tokens} tokens)"
    )
    summary_table.add_row(
        "Median Investment per Token",
        f"{median_investment:.3f} ◎",
        ""
    )
    if profits:
        summary_table.add_row(
            "Median Profit per Token",
            f"[green]+{median_profit:.3f} ◎ (+{median_profit_roi:.1f}%)[/green]",
            f"({len(profits)} tokens)"
        )
    if losses:
        summary_table.add_row(
            "Median Loss per Token",
            f"[red]-{median_loss:.3f} ◎ (-{median_loss_roi:.1f}%)[/red]",
            f"({len(losses)} tokens)"
        )

    if hold_times:
        summary_table.add_row(
            "Median Hold Time",
            format_time_difference(datetime.now(), datetime.now() + median_hold_time),
            f"({len(hold_times)} tokens)"
        )

    console.print("\n[bold]Transaction Summary[/bold]")
    console.print(summary_table)

def filter_token_stats(token_stats: Dict[str, Dict[str, Any]], filter_str: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """
    Filter token statistics based on key-value pairs.
    
    Args:
        token_stats: Dictionary of token statistics
        filter_str: Filter string in format "key1:value1;key2:value2"
                   where key can be:
                   - 30droip (30D ROI %)
                   - wr (winrate)
                   - mi (median investment)
                   - ml (median loss)
                   - mw (median winnings)
                   - mlp (median loss percentage)
                   - mwp (median winnings percentage)
                   - mht (median hold time, in seconds)
                   - t (trades)
                   - tps (tokens per sol, at time invested)
                   
                   value format: operator number
                   operators: >, <, >=, <=, =
                   eg. -f "t:>500;tps:>1000000"
                   
    Returns:
        Filtered token statistics dictionary
    """
    if not filter_str:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from rich.text import Text

        console = Console()

        # Create table for filter keys
        keys_table = Table(title="[bold cyan]Available Filter Keys", show_header=True, header_style="bold magenta")
        keys_table.add_column("Key", style="yellow")
        keys_table.add_column("Description", style="green")
        
        # Add rows for each filter key
        keys_table.add_row("30droip", "30 Day ROI Percentage")
        keys_table.add_row("wr", "Win Rate")
        keys_table.add_row("mi", "Median Investment")
        keys_table.add_row("ml", "Median Loss")
        keys_table.add_row("mw", "Median Winnings")
        keys_table.add_row("mlp", "Median Loss Percentage")
        keys_table.add_row("mwp", "Median Winnings Percentage")
        keys_table.add_row("mht", "Median Hold Time (in seconds)")
        keys_table.add_row("t", "SOL Swaps Count")
        keys_table.add_row("fmc", "First Market Cap")
        keys_table.add_row("tps", "Tokens per SOL at investment")

        # Create table for operators
        operators_table = Table(title="[bold cyan]Available Operators", show_header=True, header_style="bold magenta")
        operators_table.add_column("Operator", style="yellow")
        operators_table.add_column("Description", style="green")
        
        operators_table.add_row(">", "Greater than")
        operators_table.add_row("<", "Less than")
        operators_table.add_row(">=", "Greater than or equal to")
        operators_table.add_row("<=", "Less than or equal to")
        operators_table.add_row("=", "Equal to")

        # Create table for examples
        examples_table = Table(title="[bold cyan]Filter Examples", show_header=True, header_style="bold magenta")
        examples_table.add_column("Example", style="yellow")
        examples_table.add_column("Description", style="green")
        
        examples_table.add_row("-f \"t:>500\"", "Filter tokens with more than 500 swaps")
        examples_table.add_row("-f \"fmc:>=25000\"", "Filter tokens with first market cap >= 25000")
        examples_table.add_row("-f \"wr:>50\"", "Filter tokens with win rate > 50%")
        examples_table.add_row("-f \"mht:>86400\"", "Filter tokens held more than 24 hours")
        examples_table.add_row("-f \"t:>500;fmc:>25000\"", "Multiple filters combined")
        examples_table.add_row("-f \"tps:>1000000\"", "Filter tokens with >1M tokens per SOL exchange rate at first investment")

        # Format text
        format_text = Text("\nFilter Format: ", style="bold white")
        format_text.append("key:operator value", style="cyan")
        format_text.append("\nMultiple filters: ", style="bold white")
        format_text.append("key1:operator value1;key2:operator value2", style="cyan")

        # Display everything
        console.print("\n[bold]Filter Usage Guide[/bold]")
        console.print(format_text)
        console.print()
        console.print(keys_table)
        console.print()
        console.print(operators_table)
        console.print()
        console.print(examples_table)
        return token_stats

    filtered_stats = {}
    filters = filter_str.split(';')
    
    for token, stats in token_stats.items():
        include_token = True
        
        for filter_item in filters:
            if ':' not in filter_item:
                continue
                
            key, value = filter_item.split(':', 1)
            # Extract operator and value
            import re
            match = re.match(r'([><]=?|=)(\d+\.?\d*)', value.strip())
            if not match:
                continue
                
            operator, threshold = match.groups()
            threshold = float(threshold)
            
            # Get the actual value based on the key
            actual_value = None
            
            if key == '30droip':
                # Calculate 30-day ROI percentage
                invested = stats.get('30d', {}).get('invested', 0)
                received = stats.get('30d', {}).get('received', 0)
                actual_value = ((received / invested) - 1) * 100 if invested > 0 else 0
            elif key == 'wr':
                # Calculate win rate
                wins = len([p for p in stats.get('profits', []) if p > 0])
                total = len(stats.get('profits', [])) + len(stats.get('losses', []))
                actual_value = (wins / total * 100) if total > 0 else 0
            elif key == 'mi':
                actual_value = stats.get('median_investment', 0)
            elif key == 'ml':
                actual_value = stats.get('median_loss', 0)
            elif key == 'mw':
                actual_value = stats.get('median_profit', 0)
            elif key == 'mlp':
                actual_value = stats.get('median_loss_roi', 0)
            elif key == 'mwp':
                actual_value = stats.get('median_profit_roi', 0)
            elif key == 'mht':
                hold_time = stats.get('hold_time')
                actual_value = hold_time.total_seconds() if hold_time else 0
            elif key == 't':
                actual_value = stats.get('trade_count', 0)
            elif key == 'tps':
                # Tokens per sol
                tokens_bought = stats.get('tokens_bought', 0)
                first_trade_rate = stats['sol_invested'] / tokens_bought if tokens_bought > 0 else 0
                actual_value = 1/first_trade_rate if first_trade_rate > 0 else 0
            
            if actual_value is None:
                include_token = False
                break
                
            # Compare using the operator
            if operator == '>':
                include_token = actual_value > threshold
            elif operator == '<':
                include_token = actual_value < threshold
            elif operator == '>=':
                include_token = actual_value >= threshold
            elif operator == '<=':
                include_token = actual_value <= threshold
            elif operator == '=':
                include_token = abs(actual_value - threshold) < 1e-6  # Float comparison
                
            if not include_token:
                break
                
        if include_token:
            filtered_stats[token] = stats
            
    return filtered_stats