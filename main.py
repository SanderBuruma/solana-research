import requests
import json
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from rich.console import Console
from rich.table import Table
import base58
import time
from rich.live import Live
from rich.panel import Panel
import secrets
import re
from nacl.signing import SigningKey
from nacl.public import PrivateKey
import multiprocessing
import os
from multiprocessing import Process, Queue, Value, cpu_count
import ctypes
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from numba import jit, njit, prange
import numpy.typing as npt

def generate_keypair():
    """Generate a new Ed25519 keypair for Solana in Phantom wallet format."""
    signing_key = SigningKey.generate()
    secret_key = bytes(signing_key)  # 32 bytes private key
    verify_key = bytes(signing_key.verify_key)  # 32 bytes public key
    
    # Combine into a 64-byte array (Phantom wallet format)
    full_keypair = secret_key + verify_key
    return full_keypair

def get_public_key(private_key: bytes) -> str:
    """Get public key from private key"""
    return base58.b58encode(private_key).decode('ascii')[:44]  # First 44 chars is roughly the public key length

class SolscanAPI:
    def __init__(self):
        self.base_url = 'https://api-v2.solscan.io/v2'
        self.headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en-GB,en;q=0.5',
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
            'sol-aut': '9XmgllMkPSIeiF9CU8XihsvB9dls0fKQwzALi2z9',
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

def print_menu():
    """
    Print the main menu options
    """
    print("\nSolana Research Tool")
    print("===================")
    print("1. Get Account Balance")
    print("2. View Transaction History")
    print("3. View DEX Trading History")
    print("4. Generate Vanity Address")
    print("0. Exit")
    print("===================")

def get_account_balance_menu(api: SolscanAPI):
    """
    Handle the account balance menu option
    """
    address = input("Enter Solana account address: ")
    balance = api.get_account_balance(address)
    
    if balance is not None:
        api.console.print(f"\nAccount Balance: [green]{balance:.9f}[/green] SOL")
    else:
        api.console.print("[red]Failed to fetch account balance[/red]")

def view_transactions_menu(api: SolscanAPI):
    """
    Handle the transaction history menu option
    """
    address = input("Enter Solana account address: ")
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
        if len(transactions) < page_size:  # If we got fewer transactions than requested, we've hit the end
            break
            
        page += 1
    
    if all_transactions:
        api.console.print(f"\nFound [green]{len(all_transactions)}[/green] transactions\n")
        display_transactions_table(all_transactions, api.console, address)
    else:
        api.console.print("[red]Failed to fetch transactions or no transactions found[/red]")

def view_balance_history_menu(api: SolscanAPI):
    """
    Handle the DEX trading history analysis menu option
    """
    address = input("Enter Solana account address: ")
    console = Console()
    
    headers = {
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
        'sol-aut': '4iOtUjKOhwGFLxtTMWPOVZB9dls0fKyJ0pVfH-hN',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36'
    }

    # Dictionary to store token trading data
    token_data = {}
    page = 1
    total_trades = 0
    
    console.print("\n[yellow]Fetching DEX trading history...[/yellow]")
    
    while True:
        url = f'https://api-v2.solscan.io/v2/account/activity/dextrading'
        params = {
            'address': address,
            'page': page,
            'page_size': 100
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            if not data.get('data') or not data['data'].get('items'):
                break
                
            trades = data['data']['items']
            if not trades:
                break
                
            total_trades += len(trades)
            console.print(f"[yellow]Processing page {page} ({len(trades)} trades)...[/yellow]")
            
            for trade in trades:
                token_mint = trade.get('tokenMint')
                token_symbol = trade.get('tokenSymbol', 'UNKNOWN')
                token_name = trade.get('tokenName', 'Unknown Token')
                timestamp = datetime.fromtimestamp(trade.get('blockTime', 0))
                
                if token_mint not in token_data:
                    token_data[token_mint] = {
                        'symbol': token_symbol,
                        'name': token_name,
                        'invested_sol': 0.0,
                        'sold_sol': 0.0,
                        'remaining_tokens': 0.0,
                        'last_trade': timestamp,
                        'trades': 0
                    }
                
                amount = float(trade.get('tokenAmount', 0))
                sol_value = float(trade.get('solValue', 0))
                
                if trade.get('actionType') == 'buy':
                    token_data[token_mint]['invested_sol'] += sol_value
                    token_data[token_mint]['remaining_tokens'] += amount
                else:  # sell
                    token_data[token_mint]['sold_sol'] += sol_value
                    token_data[token_mint]['remaining_tokens'] -= amount
                
                token_data[token_mint]['trades'] += 1
                token_data[token_mint]['last_trade'] = max(token_data[token_mint]['last_trade'], timestamp)
            
            page += 1
            
        except requests.exceptions.RequestException as e:
            console.print(f"[red]Error fetching data: {str(e)}[/red]")
            break
    
    if not token_data:
        console.print("[red]No DEX trading history found[/red]")
        return
    
    # Create and display the summary table
    table = Table(title=f"DEX Trading Summary - Total Trades: {total_trades}")
    
    table.add_column("Token", style="cyan")
    table.add_column("Invested (SOL)", justify="right", style="green")
    table.add_column("Sold (SOL)", justify="right", style="red")
    table.add_column("Profit/Loss", justify="right")
    table.add_column("Remaining", justify="right", style="yellow")
    table.add_column("# Trades", justify="right")
    table.add_column("Last Trade", justify="left")
    
    # Sort by last trade date, most recent first
    sorted_tokens = sorted(token_data.items(), key=lambda x: x[1]['last_trade'], reverse=True)
    
    for token_mint, data in sorted_tokens:
        profit_loss = data['sold_sol'] - data['invested_sol']
        profit_loss_color = "green" if profit_loss >= 0 else "red"
        
        table.add_row(
            f"{data['symbol']} ({data['name'][:15]}...)",
            f"{data['invested_sol']:.4f}",
            f"{data['sold_sol']:.4f}",
            f"[{profit_loss_color}]{profit_loss:.4f}[/{profit_loss_color}]",
            f"{data['remaining_tokens']:.4f}",
            str(data['trades']),
            data['last_trade'].strftime('%Y-%m-%d %H:%M'),
        )
    
    console.print("\n")
    console.print(table)
    
    # Calculate and display totals
    total_invested = sum(data['invested_sol'] for data in token_data.values())
    total_sold = sum(data['sold_sol'] for data in token_data.values())
    total_profit_loss = total_sold - total_invested
    
    console.print("\n[bold]Portfolio Summary:[/bold]")
    console.print(f"Total Invested: [green]{total_invested:.4f} SOL[/green]")
    console.print(f"Total Sold: [yellow]{total_sold:.4f} SOL[/yellow]")
    console.print(f"Overall Profit/Loss: [{('green' if total_profit_loss >= 0 else 'red')}]{total_profit_loss:.4f} SOL[/]")
    console.print(f"Total Number of Trades: [blue]{total_trades}[/blue]")

def generate_vanity_address(pattern: str, console: Console) -> None:
    """
    Generate a Solana address matching the specified regex pattern using multiple processes
    with JIT compilation and batch processing
    """
    try:
        re.compile(pattern)
    except re.error as e:
        console.print(f"[red]Invalid regex pattern: {str(e)}[/red]")
        return

    # Shared variables between processes
    found_key = Value(ctypes.c_bool, False)
    total_attempts = Value(ctypes.c_uint64, 0)
    result_queue = Queue()
    
    # Use all cores except one for system
    num_processes = max(1, cpu_count() - 1)
    
    console.print(f"\n[yellow]Starting {num_processes} optimized worker processes...[/yellow]")
    console.print("[yellow]Using JIT compilation and batch processing[/yellow]")
    console.print("[yellow]Press Ctrl+C to stop searching[/yellow]\n")
    
    # Start worker processes
    processes = []
    start_time = time.time()
    
    # Warm up the JIT compiler
    console.print("[yellow]Warming up JIT compiler...[/yellow]")
    dummy_data = np.zeros((1, 32), dtype=np.uint8)
    dummy_pattern = np.zeros(1, dtype=np.uint8)
    parallel_check_keypairs(dummy_data, dummy_pattern)
    
    for _ in range(num_processes):
        p = Process(target=worker_process, args=(pattern, found_key, result_queue, total_attempts))
        p.start()
        processes.append(p)
    
    # Monitor progress and update display
    try:
        with Live(console=console, refresh_per_second=4) as live:
            while not found_key.value:
                elapsed = time.time() - start_time
                attempts = total_attempts.value
                rate = attempts / elapsed if elapsed > 0 else 0
                
                status = Panel(f"""[yellow]Searching with {num_processes} optimized processes:
Pattern: [magenta]{pattern}[/magenta]
Attempts: [blue]{attempts:,}[/blue]
Time: [blue]{elapsed:.2f}[/blue] seconds
Combined Rate: [blue]{rate:.0f}[/blue] addresses/second
Rate per core: [blue]{rate/num_processes:.0f}[/blue] addresses/second
Using: JIT compilation + Batch processing[/yellow]""")
                
                live.update(status)
                time.sleep(0.25)
                
                if not result_queue.empty():
                    break
        
        # Get the result if found
        if not result_queue.empty():
            full_keypair = result_queue.get()
            # Split into private and public parts
            private_key = full_keypair[:32]  # First 32 bytes
            public_key = full_keypair[32:]   # Last 32 bytes
            
            # Convert to base58
            public_key_b58 = base58.b58encode(public_key).decode()
            # For Phantom wallet, we encode the full keypair
            private_key_b58 = base58.b58encode(full_keypair).decode()
            
            elapsed = time.time() - start_time
            attempts = total_attempts.value
            rate = attempts / elapsed if elapsed > 0 else 0
            
            match = re.search(pattern, public_key_b58)
            result = Panel(f"""[green]Found matching address![/green]
Public Key: [cyan]{public_key_b58}[/cyan]
Private Key (Phantom Compatible): [yellow]{private_key_b58}[/yellow]
Pattern: [magenta]{pattern}[/magenta]
Match Position: {match.start()}-{match.end()}
Attempts: [blue]{attempts:,}[/blue]
Time: [blue]{elapsed:.2f}[/blue] seconds
Combined Rate: [blue]{rate:.0f}[/blue] addresses/second
Rate per core: [blue]{rate/num_processes:.0f}[/blue] addresses/second

[green]✓ This private key can be imported directly into Phantom wallet[/green]""")
            
            # Also save to file
            with open("found_addresses.txt", "a") as f:
                f.write(f"\nFound at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}:\n")
                f.write(f"Public Key: {public_key_b58}\n")
                f.write(f"Private Key: {private_key_b58}\n")
                f.write("-" * 80 + "\n")
            
            console.print(result)
            console.print("\n[yellow]Address details have been saved to found_addresses.txt[/yellow]")
    
    except KeyboardInterrupt:
        console.print("\n[yellow]Search cancelled by user[/yellow]")
    
    finally:
        # Cleanup: Set found flag and terminate all processes
        found_key.value = True
        for p in processes:
            p.terminate()
            p.join()

def generate_vanity_address_menu(console: Console):
    """
    Handle the vanity address generation menu option
    """
    console.print("\nRegex Pattern Examples:")
    console.print("- End pattern: 'abc$'")
    console.print("- Start pattern: '^abc'")
    console.print("- Numbers: '\\d{3}'")
    console.print("- Letters: '[a-f]{4}'")
    console.print("- Complex: 'abc.*xyz'")
    
    pattern = input("\nEnter regex pattern for the address: ")
    if not pattern:
        console.print("[red]Pattern cannot be empty[/red]")
        return
    
    generate_vanity_address(pattern, console)

def main():
    api = SolscanAPI()
    console = Console()
    
    while True:
        print_menu()
        choice = input("\nEnter your choice (0-4): ")
        
        if choice == "1":
            get_account_balance_menu(api)
        elif choice == "2":
            view_transactions_menu(api)
        elif choice == "3":
            view_balance_history_menu(api)
        elif choice == "4":
            generate_vanity_address_menu(console)
        elif choice == "0":
            print("\nGoodbye!")
            break
        else:
            print("\nInvalid choice. Please try again.")

if __name__ == "__main__":
    main()
