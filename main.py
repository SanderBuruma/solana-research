from rich.console import Console

from utils.solscan import SolscanAPI, display_dex_trading_summary, display_transactions_table
from utils.vanity import generate_vanity_address

def print_usage():
    """
    Print usage information
    """
    print("\nSolana Research Tool Usage:")
    print("==========================")
    print("-1 <address>     Get Account Balance")
    print("-2 <address>     View Transaction History")
    print("-3 <address>     View Balance History")
    print("-4 <pattern>     Generate Vanity Address")
    print("\nExamples:")
    print("python main.py -1 AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY")
    print("python main.py -3 AqEvrwvsNad9ftZaPneUrjTcuY2o7RGkeuqknbT91VnY")
    print("python main.py -4 \"abc$\"")
    print("==========================")

def main():
    import sys
    
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)
        
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
        if len(sys.argv) != 3:
            print("Error: Address required for balance history")
            print_usage()
            sys.exit(1)
        address = sys.argv[2]
        api.console.print("\nFetching DEX trading history...", style="yellow")
        trades = api.get_dex_trading_history(address)
        
        if trades:
            api.console.print(f"\nFound [green]{len(trades)}[/green] DEX trades\n")
            display_dex_trading_summary(trades, api.console, address)
        else:
            api.console.print("[red]No DEX trading history found[/red]")
            
    elif option == "-4":
        if len(sys.argv) != 3:
            print("Error: Pattern required for vanity address")
            print_usage()
            sys.exit(1)
        pattern = sys.argv[2]
        if not pattern:
            console.print("[red]Pattern cannot be empty[/red]")
            sys.exit(1)
        generate_vanity_address(pattern, console)
        
    else:
        print(f"Error: Unknown option {option}")
        print_usage()
        sys.exit(1)

if __name__ == "__main__":
    main()
