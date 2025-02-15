from rich.console import Console
from datetime import datetime

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
    print("-5 <address>     View DeFi Summary for Wallets")
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

    elif option == "-5":
        if len(sys.argv) < 3:
            print("Error: At least one wallet address is required for option -5")
            print_usage()
            sys.exit(1)
        addresses = sys.argv[2:]
        from rich.table import Table
        summary_table = Table(title="DeFi Summary for Wallets")
        summary_table.add_column("Address", style="cyan")
        summary_table.add_column("24H ROI %", justify="right", style="magenta")
        summary_table.add_column("7D ROI %", justify="right", style="magenta")
        summary_table.add_column("30D ROI %", justify="right", style="magenta")
        summary_table.add_column("30D ROI", justify="right", style="yellow")
        summary_table.add_column("nSol Swaps", justify="right", style="green")
        summary_table.add_column("Total Swaps", justify="right", style="green")

        SOL_ADDRESSES = {"So11111111111111111111111111111111111111112", "So11111111111111111111111111111111111111111"}
        now = datetime.now().timestamp()

        for addr in addresses:
            trades = api.get_dex_trading_history(addr)
            # Initialize period stats
            period_stats = {
                "24h": {"invested": 0.0, "received": 0.0, "start": now - 86400},
                "7d": {"invested": 0.0, "received": 0.0, "start": now - 7 * 86400},
                "30d": {"invested": 0.0, "received": 0.0, "start": now - 30 * 86400}
            }
            total_swaps = len(trades)
            non_sol_swaps = 0
            for trade in trades:
                amount_info = trade.get("amount_info", {})
                if not amount_info:
                    continue
                token1 = amount_info.get("token1")
                token2 = amount_info.get("token2")
                token1_dec = amount_info.get("token1_decimals", 0)
                token2_dec = amount_info.get("token2_decimals", 0)
                try:
                    amt1 = float(amount_info.get("amount1", 0)) / (10 ** token1_dec)
                    amt2 = float(amount_info.get("amount2", 0)) / (10 ** token2_dec)
                except (ValueError, TypeError):
                    amt1 = 0
                    amt2 = 0
                trade_time = trade.get("block_time", 0)
                for period, stats in period_stats.items():
                    if trade_time >= stats["start"]:
                        if token1 in SOL_ADDRESSES:
                            stats["invested"] += amt1
                        elif token2 in SOL_ADDRESSES:
                            stats["received"] += amt2
                if token1 and token2 and (token1 not in SOL_ADDRESSES and token2 not in SOL_ADDRESSES):
                    non_sol_swaps += 1
            
            def compute_roi(stats):
                if stats["invested"] > 0:
                    profit = stats["received"] - stats["invested"]
                    return (profit / stats["invested"]) * 100
                return 0.0
            
            roi_24h = compute_roi(period_stats["24h"])
            roi_7d = compute_roi(period_stats["7d"])
            roi_30d = compute_roi(period_stats["30d"])
            roi_30d_abs = period_stats["30d"]["received"] - period_stats["30d"]["invested"]
            
            summary_table.add_row(
                addr,
                f"{roi_24h:.2f}%",
                f"{roi_7d:.2f}%",
                f"{roi_30d:.2f}%",
                f"{roi_30d_abs:.3f} SOL",
                str(non_sol_swaps),
                str(total_swaps)
            )
        console.print(summary_table)

    else:
        print(f"Error: Unknown option {option}")
        print_usage()
        sys.exit(1)

if __name__ == "__main__":
    main()
