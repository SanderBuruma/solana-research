import os
import time
import csv
import random
import string
import re
import json
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime, timedelta
import sys

# Third-party imports
import cloudscraper
import requests
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from dotenv import load_dotenv

def is_sol_token(token: str) -> bool:
    """Check if a token is SOL"""
    SOL_ADDRESSES = {
        "So11111111111111111111111111111111111111112",
        "So11111111111111111111111111111111111111111"
    }
    return token in SOL_ADDRESSES

def is_usd(token: str) -> bool:
    """Check if a token is a USD token"""
    USD_ADDRESSES = {
        "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    }
    return token in USD_ADDRESSES
    
def generate_random_token() -> str:
    """
    Generate a random Solscan authentication token following the same pattern as the JavaScript code.
    Returns a string that includes 'B9dls0fK' at a random position.
    """
    # Character set for random generation (excluding '=' and '-' which will be added later)
    chars = string.ascii_letters + string.digits
    
    # Generate two 16-character strings
    t = ''.join(random.choice(chars) for _ in range(16))
    r = ''.join(random.choice(chars) for _ in range(16))
    
    # Random position for inserting the fixed string (0-30)
    n = random.randint(0, 30)
    
    # Concatenate strings and insert fixed string
    combined = t + r
    result = combined[:n] + "B9dls0fK" + combined[n:]
    
    # Add some '=' and '-' characters randomly
    result = result.replace(random.choice(result), '=', 2)  # Replace 2 random chars with '='
    result = result.replace(random.choice(result), '-', 2)  # Replace 2 random chars with '-'
    
    return result

class SolscanDefiActivity:
    """
    Structured representation of a DEX trading activity from Solscan.
    
    This class encapsulates all the relevant information about a DEX trade,
    providing a cleaner and more type-safe access to trade data compared to
    using raw dictionaries.
    
    Attributes:
        transaction_id (str): Unique identifier of the transaction
        block_time (float): UNIX timestamp of the block when the transaction occurred
        block_id (int): Block ID/slot number for the transaction
        token1 (str): Address of the first token in the swap
        token2 (str): Address of the second token in the swap
        token1_decimals (int): Number of decimals for the first token
        token2_decimals (int): Number of decimals for the second token
        amount1 (float): Raw amount of the first token (multiply by 10^-decimals to get human-readable amount)
        amount2 (float): Raw amount of the second token (multiply by 10^-decimals to get human-readable amount)
        price_usdt (float): Price in USDT at the time of the transaction
        decimals (int): Decimals of the token (if applicable)
        name (str): Name of the token (if applicable)
        symbol (str): Symbol of the token (if applicable)
        flow (str): Direction of the transaction (in/out)
        value (float): Value of the transaction (in USD)
    """
    def __init__(self, trade: Dict[str, Any]):
        """
        Initialize a new SolscanDefiActivity instance from a trade dictionary.
        
        Args:
            trade: Dictionary containing trade data from Solscan API
        """
        self.transaction_id = trade.get('trans_id', '')
        self.block_time = trade.get('block_time', 0)
        self.block_id = trade.get('slot', 0)  # Store block ID/slot
        
        # Extract amount_info data
        amount_info = trade.get('amount_info', {})
        self.token1 = amount_info.get('token1', '')
        self.token2 = amount_info.get('token2', '')
        self.token1_decimals = amount_info.get('token1_decimals', 0)
        self.token2_decimals = amount_info.get('token2_decimals', 0)
        self.amount1 = amount_info.get('amount1', 0)
        self.amount2 = amount_info.get('amount2', 0)
        self.from_address = trade.get('from_address', '')
        
        # Add additional fields
        self.price_usdt = trade.get('price_usdt', 0)
        self.decimals = trade.get('decimals', 0)
        self.name = trade.get('name', '')
        self.symbol = trade.get('symbol', '')
        self.flow = trade.get('flow', '')
        self.value = trade.get('value', 0)
        
    def get_amount1_human_readable(self) -> float:
        """Return the human-readable amount of token1"""
        return float(self.amount1) / (10 ** self.token1_decimals)
        
    def get_amount2_human_readable(self) -> float:
        """Return the human-readable amount of token2"""
        return float(self.amount2) / (10 ** self.token2_decimals)
        
    def is_sol_purchase(self) -> bool:
        """Check if this trade is buying a token with SOL"""
        return is_sol_token(self.token1) and not is_sol_token(self.token2)
        
    def is_sol_sale(self) -> bool:
        """Check if this trade is selling a token for SOL"""
        return is_sol_token(self.token2) and not is_sol_token(self.token1)
        
    def get_trade_datetime(self) -> datetime:
        """Return the datetime of the trade"""
        return datetime.fromtimestamp(self.block_time)
        
    def __str__(self) -> str:
        """String representation of the trade"""
        if self.is_sol_purchase():
            return f"Bought {self.get_amount2_human_readable():.4f} {self.token2} for {self.get_amount1_human_readable():.4f} SOL at {self.get_trade_datetime()}"
        elif self.is_sol_sale():
            return f"Sold {self.get_amount1_human_readable():.4f} {self.token1} for {self.get_amount2_human_readable():.4f} SOL at {self.get_trade_datetime()}"
        else:
            return f"Swapped {self.get_amount1_human_readable():.4f} {self.token1} for {self.get_amount2_human_readable():.4f} {self.token2} at {self.get_trade_datetime()}"

class SolscanAPI:
    def __init__(self):
        self.base_url = 'https://api-v2.solscan.io/v2'
        
        # Check for cache-only mode
        self.cache_only = '--cache-only' in sys.argv
        
        # Preset headers as fallback
        self.preset_headers = {
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
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36'
        }
        
        # Try to get headers from request.ps1
        request_headers = self._parse_request_ps1()
        if request_headers:
            self.headers = request_headers
            self.console = Console()
            self.console.print("[green]Using headers from request.ps1[/green]")
        else:
            self.headers = self.preset_headers
            self.console = Console()
            self.console.print("[yellow]Using preset headers (request.ps1 not found or invalid)[/yellow]")

        self.scraper = cloudscraper.create_scraper()
        proxy_url = os.getenv('PROXY_URL')
        if os.getenv('PROXY_ENABLED') == 'True' and proxy_url:
            self.proxies = {
                'http': f'{proxy_url}',
                'https':f'{proxy_url}'
            }
        else:
            self.proxies = None
            
        if self.cache_only:
            self.console.print("[yellow]Cache-only mode enabled - no API requests will be made[/yellow]")

    def _parse_request_ps1(self) -> Optional[Dict[str, str]]:
        """
        Parse request.ps1 file to extract headers and cookies.
        Returns a dictionary of headers if found, None otherwise.
        """
        try:
            # in the dev console network requests, copy as curl ( windows ) a solscan.io dextrading request to request.ps1
            if not os.path.exists('request.ps1'):
                return None
                
            with open('request.ps1', 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Extract headers from curl command
            headers = {}
            
            # Extract User-Agent
            user_agent_match = re.search(r'User-Agent: ([^"]+)', content)
            if user_agent_match:
                headers['user-agent'] = user_agent_match.group(1)
                
            # Extract Accept
            accept_match = re.search(r'Accept: ([^"]+)', content)
            if accept_match:
                headers['accept'] = accept_match.group(1)
                
            # Extract Accept-Language
            accept_lang_match = re.search(r'Accept-Language: ([^"]+)', content)
            if accept_lang_match:
                headers['accept-language'] = accept_lang_match.group(1)
                
            # Extract Accept-Encoding
            accept_enc_match = re.search(r'Accept-Encoding: ([^"]+)', content)
            if accept_enc_match:
                headers['accept-encoding'] = accept_enc_match.group(1)
                
            # Extract Referer
            referer_match = re.search(r'Referer: ([^"]+)', content)
            if referer_match:
                headers['referer'] = referer_match.group(1)
                
            # Extract sol-aut
            sol_aut_match = re.search(r'sol-aut: ([^"]+)', content)
            if sol_aut_match:
                headers['sol-aut'] = sol_aut_match.group(1)
                
            # Extract Origin
            origin_match = re.search(r'Origin: ([^"]+)', content)
            if origin_match:
                headers['origin'] = origin_match.group(1)
                
            # Extract Sec-GPC
            sec_gpc_match = re.search(r'Sec-GPC: ([^"]+)', content)
            if sec_gpc_match:
                headers['sec-gpc'] = sec_gpc_match.group(1)
                
            # Extract Connection
            connection_match = re.search(r'Connection: ([^"]+)', content)
            if connection_match:
                headers['connection'] = connection_match.group(1)
                
            # Extract Cookie
            cookie_match = re.search(r'Cookie: ([^"]+)', content)
            if cookie_match:
                headers['cookie'] = cookie_match.group(1)
                
            # Extract Sec-Fetch headers
            sec_fetch_dest_match = re.search(r'Sec-Fetch-Dest: ([^"]+)', content)
            if sec_fetch_dest_match:
                headers['sec-fetch-dest'] = sec_fetch_dest_match.group(1)
                
            sec_fetch_mode_match = re.search(r'Sec-Fetch-Mode: ([^"]+)', content)
            if sec_fetch_mode_match:
                headers['sec-fetch-mode'] = sec_fetch_mode_match.group(1)
                
            sec_fetch_site_match = re.search(r'Sec-Fetch-Site: ([^"]+)', content)
            if sec_fetch_site_match:
                headers['sec-fetch-site'] = sec_fetch_site_match.group(1)
                
            # Extract TE
            te_match = re.search(r'TE: ([^"]+)', content)
            if te_match:
                headers['te'] = te_match.group(1)
                
            # Only return headers if we found at least the essential ones
            if 'user-agent' in headers and 'accept' in headers and 'cookie' in headers:
                return headers
                
            return None
            
        except Exception as e:
            self.console.print(f"[yellow]Error parsing request.ps1: {str(e)}[/yellow]")
            return None

    def _make_request(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """
        Make a request to the Solscan API with improved error handling and retry logic.
        
        Args:
            endpoint (str): API endpoint to request
            
        Returns:
            Optional[Dict[str, Any]]: JSON response or None if request failed
            
        Raises:
            requests.exceptions.HTTPError: If a 403 Forbidden response is received
        """
        # Return empty results in cache-only mode
        if self.cache_only:
            return {
                'success': True,
                'data': []
            }
            
        url = f'{self.base_url}/{endpoint}'
        max_retries = 3
        base_wait_time = 5
        wait_time = base_wait_time
        
        for attempt in range(max_retries):
            try:
                if self.proxies:
                    response = self.scraper.get(url, headers=self.headers, proxies=self.proxies)
                else:
                    response = self.scraper.get(url, headers=self.headers)
                
                # Check response status
                response.raise_for_status()
                
                # Check if response is empty
                if not response.text:
                    return None
                
                # Try to parse JSON
                try:
                    return response.json()
                except json.JSONDecodeError:
                    if attempt < max_retries - 1:
                        wait_time = int(wait_time * 1.2)
                        time.sleep(wait_time)
                        continue
                    return None
                    
            except requests.exceptions.HTTPError as e:
                # Raise exception for 403 Forbidden responses
                if e.response.status_code == 403:
                    raise
                # For other HTTP errors, retry if possible
                if attempt < max_retries - 1:
                    wait_time = int(wait_time * 1.2)
                    time.sleep(wait_time)
                else:
                    return None
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = int(wait_time * 1.2)
                    time.sleep(wait_time)
                else:
                    return None
            except Exception:
                return None
        
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

    def get_dex_trading_history(self, address: str, time_filter: dict = None, quiet: bool = False, days: int = None, defi_days: int = None, from_time: int = None, to_time: int = None) -> List[SolscanDefiActivity]:
        """
        Get complete DEX trading history for an account, up to 60 days old.
        Uses cached transactions from CSV if available and only fetches new transactions.
        
        Args:
            address: The address to get trading history for
            time_filter: Optional time filtering parameters:
                - 'reference_time': base timestamp to compare against
                - 'direction': 'before' or 'after' to fetch trades before or after the reference time
                - 'window': maximum time difference in seconds (default 30)
            quiet: If True, suppresses progress bar display (useful when called from other functions with their own status displays)
            days: If provided, only includes tokens that were first bought within this many days
            defi_days: If provided, only includes transactions from the last X days
            from_time: If provided, only includes transactions after this Unix timestamp
            to_time: If provided, only includes transactions before this Unix timestamp
        
        Returns:
            List[SolscanDefiActivity]: List of trading activities sorted by timestamp (newest first)
        """
        # Skip CSV interaction when direct timestamp filtering is used
        skip_csv = from_time is not None or to_time is not None
        
        if not skip_csv:
            # Only create directory and handle CSV if we're not skipping it
            wallet_dir = f'./dex_activity/{address}'
            os.makedirs(wallet_dir, exist_ok=True)
            csv_filename = f'{wallet_dir}/transactions.csv'
        
        # Show timestamp filtering info if applicable
        if not quiet and skip_csv:
            time_window_seconds = None
            if from_time is not None and to_time is not None:
                time_window_seconds = to_time - from_time
                
            # Determine if this is a narrow time window (useful for copy trading detection)
            is_narrow_window = time_window_seconds is not None and time_window_seconds <= 60
            
            time_filter_msg = "[yellow]Using timestamp filtering"
            if is_narrow_window:
                time_filter_msg += f" (narrow {time_window_seconds}s window)"
            time_filter_msg += "[/yellow]"
            self.console.print(time_filter_msg)

        cached_trades = {}
        all_trades = []
        
        # Calculate cutoff timestamp for defi_days if specified
        defi_cutoff_timestamp = None
        current_time = datetime.now().timestamp()
        
        if defi_days is not None and not skip_csv:
            defi_cutoff_timestamp = current_time - (defi_days * 86400)  # Convert days to seconds
            if not quiet:
                cutoff_date = datetime.fromtimestamp(defi_cutoff_timestamp).strftime('%Y-%m-%d %H:%M')
                current_date = datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M')
                self.console.print(f"[yellow]Filtering transactions to last {defi_days} days (since {cutoff_date}, current time: {current_date})[/yellow]")
        
        # Keep track of filtered transactions for logging
        filtered_cached_count = 0
        filtered_api_count = 0
        
        # Load existing transactions from CSV if available and not skipping CSV
        latest_cached_timestamp = 0
        if not skip_csv and os.path.exists(csv_filename):
            try:
                with open(csv_filename, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    # Convert CSV data back to SolscanDefiActivity objects
                    for row in reader:
                        # Skip rows without required fields
                        if not all(key in row for key in ['trans_id', 'block_time', 'token1', 'token2']):
                            continue
                        
                        # Apply defi_days filter before loading into memory
                        if defi_cutoff_timestamp is not None and float(row['block_time']) < defi_cutoff_timestamp:
                            filtered_cached_count += 1
                            continue
                            
                        # Convert the CSV data back to a dict format for SolscanDefiActivity
                        trade = {
                            'trans_id': row['trans_id'],
                            'block_time': float(row['block_time']),
                            'amount_info': {
                                'token1': row['token1'],
                                'token2': row['token2'],
                                'token1_decimals': int(row['token1_decimals']),
                                'token2_decimals': int(row['token2_decimals']),
                                'amount1': float(row['amount1']),
                                'amount2': float(row['amount2'])
                            },
                            'price_usdt': float(row.get('price_usdt', 0)),
                            'decimals': int(row.get('decimals', 0)),
                            'name': row.get('name', ''),
                            'symbol': row.get('symbol', ''),
                            'flow': row.get('flow', ''),
                            'value': float(row.get('value', 0)),
                            'from_address': row.get('from_address', '')
                        }
                        
                        # Add block_id/slot if available
                        if 'block_id' in row:
                            trade['slot'] = int(row['block_id'])
                        
                        # Add to cached trades
                        cached_trades[row['trans_id']] = trade
                        all_trades.append(SolscanDefiActivity(trade))
                        
                        # Track latest timestamp from cached data
                        latest_cached_timestamp = max(latest_cached_timestamp, float(row['block_time']))
                
                if not quiet and not skip_csv:
                    loaded_msg = f"[green]Loaded {len(cached_trades)} cached transactions[/green]"
                    if filtered_cached_count > 0:
                        loaded_msg += f" [yellow](filtered out {filtered_cached_count} older than {defi_days} days)[/yellow]"
                    self.console.print(loaded_msg)
            except Exception as e:
                if not quiet:
                    self.console.print(f"[yellow]Error loading cached transactions: {str(e)}[/yellow]")

        # Get total number of transactions
        endpoint = f'account/activity/dextrading/total?address={address}'
        total_data = self._make_request(endpoint)
        total_trades = 0
        if total_data and total_data.get('success'):
            total_trades = total_data.get('data', 0)
            if isinstance(total_trades, list):
                total_trades = len(total_trades)
            if total_trades > 10100:
                total_trades = 10100
        
        if total_trades == 0:
            # Sort all trades by block_time, newest first
            sorted_trades = sorted(all_trades, key=lambda x: x.block_time, reverse=True)
            # Apply days filter if specified (token first purchase)
            if days is not None:
                sorted_trades = self._filter_by_first_purchase_date(sorted_trades, days)
            return sorted_trades

        page = 1
        page_size = 100
        sixty_days_ago = datetime.now().timestamp() - (60 * 86400)  # 60 days in seconds
        found_cached = False  # Always start with False regardless of skip_csv
        new_trades_count = 0
        
        # Unpack time filter parameters if provided
        reference_time = None
        time_direction = None
        time_window = 30  # Default 30 seconds
        
        if time_filter:
            reference_time = time_filter.get('reference_time')
            time_direction = time_filter.get('direction')
            time_window = time_filter.get('window', 30)
        
        # Function to process data from a page of trades
        def process_page_data(trades_data):
            nonlocal found_cached, all_trades, cached_trades, new_trades_count, filtered_api_count
            
            # Track if we've exceeded the time window for time-filtered queries
            exceeded_time_window = False
            
            # Check each trade
            for trade in trades_data:
                # Filter by from_time if specified
                if from_time is not None and trade['block_time'] < from_time:
                    continue
                
                # Filter by to_time if specified
                if to_time is not None and trade['block_time'] > to_time:
                    continue
                
                # Apply defi_days filter here to API results
                if defi_cutoff_timestamp is not None and trade['block_time'] < defi_cutoff_timestamp:
                    filtered_api_count += 1
                    # If this trade is too old, and it's older than what we have, we can stop
                    if not skip_csv and trade['block_time'] < latest_cached_timestamp and not time_filter:
                        found_cached = True
                        break
                    continue
                
                # Check if this trade is outside our time window (for -4 and -7 optimization)
                if reference_time is not None and time_direction is not None:
                    time_diff = trade['block_time'] - reference_time
                    
                    if time_direction == 'before' and time_diff > 0:
                        # For option -7, we're looking for trades before the reference time
                        # If we find a trade after the reference time, we've gone too far
                        exceeded_time_window = True
                        break
                    elif time_direction == 'after' and time_diff < -time_window:
                        # For option -4, we're looking for trades after the reference time
                        # If we find a trade more than window seconds before, we've gone too far
                        # (continue looking as newer transactions might be within window)
                        continue
                
                trans_id = trade.get('trans_id')
                
                # Skip if we've already seen this transaction (when not skipping CSV)
                if not skip_csv and trans_id in cached_trades:
                    found_cached = True
                    continue
                
                # Skip transactions older than what we already have (unless we're filtering or skipping CSV)
                if not skip_csv and trade['block_time'] <= latest_cached_timestamp and not time_filter:
                    found_cached = True
                    continue
                        
                if trade['block_time'] < sixty_days_ago:
                    found_cached = True
                    break

                if not is_sol_token(trade.get('amount_info', {}).get('token1')) and not is_sol_token(trade.get('amount_info', {}).get('token2')):
                    continue

                if is_usd(trade.get('amount_info', {}).get('token1')) or is_usd(trade.get('amount_info', {}).get('token2')):
                    continue

                if 'price_usdt' not in trade:
                    trade['price_usdt'] = 0
                if 'decimals' not in trade:
                    trade['decimals'] = 0
                if 'name' not in trade:
                    trade['name'] = ''
                if 'symbol' not in trade:
                    trade['symbol'] = ''
                if 'flow' not in trade:
                    trade['flow'] = ''
                if 'value' not in trade:
                    trade['value'] = 0
                        
                all_trades.append(SolscanDefiActivity(trade))
                if not skip_csv:
                    cached_trades[trans_id] = trade
                new_trades_count += 1
                
            return exceeded_time_window
        
        # Use different approaches based on quiet mode
        if quiet:
            # Process without progress bar
            while page < 101 and not found_cached:
                # Add timestamp filters to the endpoint if provided
                timestamp_params = ""
                if from_time is not None:
                    timestamp_params += f"&from_time={from_time}"
                if to_time is not None:
                    timestamp_params += f"&to_time={to_time}"
                
                endpoint = f'account/activity/dextrading?address={address}&page={page}&page_size={page_size}&activity_type[]=ACTIVITY_TOKEN_SWAP&activity_type[]=ACTIVITY_AGG_TOKEN_SWAP{timestamp_params}'
                try:
                    data = self._make_request(endpoint)
                except Exception as e:
                    print(f"Error: {e}")
                    print(f"Endpoint: {endpoint}")
                    print(f"Address: {address}")
                    print(f"Page: {page}")
                    print(f"Page Size: {page_size}")
                    print(f"Timestamp Params: {timestamp_params}")
                    # Skip this page
                    break
                
                if not data or not data.get('success') or not data.get('data'):
                    break
                    
                trades = data['data']
                if not trades:
                    break
                
                exceeded_time_window = process_page_data(trades)
                
                # Break early if we've exceeded the time window
                if exceeded_time_window:
                    break
                
                if len(trades) < page_size:
                    break
                    
                page += 1
        else:
            # Use progress bar
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=self.console,
                transient=True
            ) as progress:
                task = progress.add_task(f"[yellow]Fetching DEX trades...", total=total_trades)
                
                while page < 101 and not found_cached:
                    # Add timestamp filters to the endpoint if provided
                    timestamp_params = ""
                    if from_time is not None:
                        timestamp_params += f"&from_time={from_time}"
                    if to_time is not None:
                        timestamp_params += f"&to_time={to_time}"
                    
                    endpoint = f'account/activity/dextrading?address={address}&page={page}&page_size={page_size}&activity_type[]=ACTIVITY_TOKEN_SWAP&activity_type[]=ACTIVITY_AGG_TOKEN_SWAP{timestamp_params}'
                    data = self._make_request(endpoint)
                    
                    if not data or not data.get('success') or not data.get('data'):
                        break
                        
                    trades = data['data']
                    if not trades:
                        break
                    
                    exceeded_time_window = process_page_data(trades)
                    
                    # Update progress
                    progress.update(task, advance=len(trades))
                    
                    # Break early if we've exceeded the time window
                    if exceeded_time_window:
                        break
                    
                    if len(trades) < page_size:
                        break
                        
                    page += 1
                
                progress.update(task, completed=new_trades_count)

        # Save new trades to CSV if we found any and aren't skipping CSV
        if new_trades_count > 0 and not skip_csv:
            try:
                # First, load all existing data to prevent overwriting
                existing_data = []
                if os.path.exists(csv_filename):
                    with open(csv_filename, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        existing_data = list(reader)
                
                # Create a dictionary of existing transactions by ID
                existing_trades = {row['trans_id']: row for row in existing_data if 'trans_id' in row}
                
                # Update with new trades
                for trade_id, trade in cached_trades.items():
                    if trade_id not in existing_trades:  # Only add new trades
                        row = {
                            'trans_id': trade.get('trans_id', ''),
                            'block_time': trade.get('block_time', 0),
                            'block_id': trade.get('slot', 0),
                            'token1': trade.get('amount_info', {}).get('token1', ''),
                            'token2': trade.get('amount_info', {}).get('token2', ''),
                            'token1_decimals': trade.get('amount_info', {}).get('token1_decimals', 0),
                            'token2_decimals': trade.get('amount_info', {}).get('token2_decimals', 0),
                            'amount1': trade.get('amount_info', {}).get('amount1', 0),
                            'amount2': trade.get('amount_info', {}).get('amount2', 0),
                            'price_usdt': trade.get('price_usdt', 0),
                            'decimals': trade.get('decimals', 0),
                            'name': trade.get('name', ''),
                            'symbol': trade.get('symbol', ''),
                            'flow': trade.get('flow', ''),
                            'value': trade.get('value', 0),
                            'from_address': trade.get('from_address', '')
                        }
                        existing_trades[trade_id] = row
                
                # Write all trades back to the CSV
                with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
                    fieldnames = ['trans_id', 'block_time', 'block_id', 'token1', 'token2', 'token1_decimals', 
                                'token2_decimals', 'amount1', 'amount2', 'price_usdt', 'decimals', 
                                'name', 'symbol', 'flow', 'value', 'from_address']
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(existing_trades.values())
                
                if not quiet:
                    saved_msg = f"[green]Saved {new_trades_count} new transactions to {csv_filename}[/green]"
                    if filtered_api_count > 0:
                        saved_msg += f" [yellow](filtered out {filtered_api_count} older than {defi_days} days)[/yellow]"
                    self.console.print(saved_msg)
            except Exception as e:
                if not quiet:
                    self.console.print(f"[red]Error saving transactions to CSV: {str(e)}[/red]")

        # Sort all trades by block_time (newest first)
        sorted_trades = sorted(all_trades, key=lambda x: x.block_time, reverse=True)
        
        # Apply days filter if specified (token first purchase)
        if days is not None:
            sorted_trades = self._filter_by_first_purchase_date(sorted_trades, days)

        # Apply final defi_days filter to ensure consistency
        if defi_cutoff_timestamp is not None:
            # This should be redundant as we already filtered during loading,
            # but keeping it for safety to ensure no older transactions slip through
            sorted_trades = [trade for trade in sorted_trades if trade.block_time >= defi_cutoff_timestamp]
        
        # Apply from_time filtering again on the final results
        if from_time is not None:
            sorted_trades = [trade for trade in sorted_trades if trade.block_time >= from_time]
            
        # Apply to_time filtering again on the final results
        if to_time is not None:
            sorted_trades = [trade for trade in sorted_trades if trade.block_time <= to_time]
        
        if not quiet and not skip_csv and (filtered_cached_count > 0 or filtered_api_count > 0):
            self.console.print(f"[yellow]Total filtered: {filtered_cached_count + filtered_api_count} transactions older than {defi_days} days[/yellow]")
            
        if not quiet and (from_time is not None or to_time is not None):
            time_filter_msg = "[yellow]Time filtered transactions: "
            if from_time is not None:
                from_date = datetime.fromtimestamp(from_time).strftime('%Y-%m-%d %H:%M')
                time_filter_msg += f"from {from_date} "
            if to_time is not None:
                to_date = datetime.fromtimestamp(to_time).strftime('%Y-%m-%d %H:%M')
                time_filter_msg += f"to {to_date}"
            time_filter_msg += f" ({len(sorted_trades)} transactions)[/yellow]"
            self.console.print(time_filter_msg)
            
        return sorted_trades

    def get_token_price(self, token_address: str) -> Optional[Dict[str, Any]]:
        """
        Get token price and metadata from Solscan API
        Returns a dictionary containing price in USDT and other token information
        """
        # Return 0 price in cache-only mode or --no-token-value mode
        if self.cache_only or '--no-token-value' in sys.argv or '--cache-only' in sys.argv:
            return {
                'price_usdt': 0,
                'decimals': 0,
                'name': '',
                'symbol': ''
            }
            
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
        """
        Get token accounts for a given Solana address.
        
        Args:
            address (str): Solana wallet address
            
        Returns:
            Optional[Dict[str, Any]]: Token account data or empty response if no tokens found
        """
        endpoint = f'account/tokenaccounts?address={address}&page=1&page_size=480&type=token&hide_zero=true'
        response = self._make_request(endpoint)
        
        # If request failed, return empty response structure
        if response is None:
            self.console.print("[yellow]No token data available, returning empty response[/yellow]")
            return {
                "success": True,
                "data": {
                    "tokenAccounts": []
                }
            }
            
        return response

def display_transactions_table(transactions: List[Dict[str, Any]], console: Console, input_address: str):
    """
    Display transactions in a rich table format
    """
    table = Table(title="Transaction History")
    
    # Add columns
    table.add_column("Time", style="bold")
    table.add_column("Type", style="magenta")
    table.add_column("Amount (SOL)", style="cyan")
    table.add_column("From", style="bold")
    table.add_column("To", style="bold")
    table.add_column("Value (USD)", justify="right", style="yellow")
    
    # Add rows
    for tx in transactions:
        timestamp = datetime.fromtimestamp(tx['block_time']).strftime('%Y-%m-%d %H:%M')
        amount = float(tx['amount']) / (10 ** tx['token_decimals'])
        direction = "→" if tx['flow'] == 'out' else "←"
        
        # Extract last 5 characters safely
        from_last5 = f"...{tx['from_address'][-5:]}" if tx.get('from_address') else "[N/A]"
        to_last5 = f"...{tx['to_address'][-5:]}" if tx.get('to_address') else "[N/A]"

        # Apply color formatting based on whether the address matches input_address
        from_addr = f"[dim]{from_last5}" if tx.get("from_address") == input_address else f"[blue]{from_last5}"
        to_addr = f"[dim]{to_last5}" if tx.get("to_address") == input_address else f"[blue]{to_last5}"

        # Format the value with color based on whether it's positive or negative
        value_color = "green" if not tx.get("from_address") == input_address else "red"
        
        table.add_row(
            timestamp,
            tx['activity_type'].replace('ACTIVITY_', ''),
            f"{amount:.4f} {direction}",
            from_addr,
            to_addr,
            f"[{value_color}]${tx.get('value', 0):.2f}[/{value_color}]"
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
    """Format token address to show the full address, except for SOL tokens"""
    if address == "So11111111111111111111111111111111111111112" or address == "So11111111111111111111111111111111111111111":
        return "SOL"
    return address

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

def format_number_for_csv(number: float) -> str:
    """Format a number with comma as decimal separator for CSV files."""
    if isinstance(number, (int, float)):
        # Always use 2 decimal places for non-integer numbers
        return f"{number:.2f}".replace('.', ',')
    return str(number)

def display_dex_trading_summary(trades: List[SolscanDefiActivity], console: Console, wallet_address: str, filter_str: Optional[str] = None):
    """
    Display DEX trading summary grouped by token and save to CSV
    
    Args:
        trades: List of SolscanDefiActivity objects to analyze
        console: Rich console for output
        wallet_address: Address of the wallet being analyzed
        filter_str: Optional filter string to filter token statistics
    """
    # Dictionary to track token stats
    token_stats = {}
    period_stats = {
        '24h': {'invested': 0, 'received': 0, 'start_time': datetime.now().timestamp() - 86400},
        '7d': {'invested': 0, 'received': 0, 'start_time': datetime.now().timestamp() - 7 * 86400},
        '30d': {'invested': 0, 'received': 0, 'start_time': datetime.now().timestamp() - 30 * 86400},
        '60d': {'invested': 0, 'received': 0, 'start_time': datetime.now().timestamp() - 60 * 86400}
    }

    # First pass: collect all trades and update period stats
    for trade in trades:
        # Extract token information
        token1 = trade.token1
        token2 = trade.token2
        token1_decimals = trade.token1_decimals
        token2_decimals = trade.token2_decimals
        
        # Ignore vault dex activity
        if not token1 or not token2:
            continue
        
        # Safely convert amounts to float with null checks
        try:
            amount1_raw = trade.amount1
            amount2_raw = trade.amount2
            amount1 = float(amount1_raw if amount1_raw is not None else 0) / (10 ** token1_decimals)
            amount2 = float(amount2_raw if amount2_raw is not None else 0) / (10 ** token2_decimals)
        except (ValueError, TypeError):
            # Skip this trade if amounts are invalid
            continue
        
        trade_time = datetime.fromtimestamp(trade.block_time)
        trade_timestamp = trade.block_time
        
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
                    'trade_count': 0,  # Added for trade count
                    'buy_fees': 0,  # Track buy fees
                    'sell_fees': 0,  # Track sell fees
                    'total_fees': 0  # Track total fees
                }
        
        # Update stats based on trade direction
        if is_sol_token(token1) and not is_sol_token(token2):
            # Sold SOL for tokens
            token_stats[token2]['sol_invested'] += amount1
            token_stats[token2]['tokens_bought'] += amount2
            token_stats[token2]['last_sol_rate'] = amount1 / (amount2 or 0.0000000001)  # SOL per token
            token_stats[token2]['last_trade'] = max(trade_time, token_stats[token2]['last_trade']) if token_stats[token2]['last_trade'] else trade_time
            token_stats[token2]['first_trade'] = min(trade_time, token_stats[token2]['first_trade']) if token_stats[token2]['first_trade'] else trade_time
            
            # Calculate and add buy fees
            BUY_FIXED_FEE = float(os.getenv('BUY_FIXED_FEE', 0.002))
            BUY_PERCENT_FEE = float(os.getenv('BUY_PERCENT_FEE', 0.022912))
            fixed_fee = BUY_FIXED_FEE
            percent_fee = amount1 * BUY_PERCENT_FEE
            total_fee = fixed_fee + percent_fee
            token_stats[token2]['buy_fees'] += total_fee
            token_stats[token2]['total_fees'] += total_fee
            
        elif is_sol_token(token2) and not is_sol_token(token1):
            # Sold tokens for SOL - include even if token appears in sell transactions first
            if token1 not in token_stats:
                token_stats[token1] = {
                    'sol_invested': 0,
                    'sol_received': 0,
                    'tokens_bought': 0,
                    'tokens_sold': 0,
                    'last_trade': None,
                    'first_trade': trade_time,
                    'last_sol_rate': 0,
                    'token_price_usdt': 0,
                    'decimals': 0,
                    'name': '',
                    'symbol': '',
                    'hold_time': None,
                    'trade_count': 0,
                    'buy_fees': 0,
                    'sell_fees': 0,
                    'total_fees': 0
                }
            
            token_stats[token1]['sol_received'] += amount2
            token_stats[token1]['tokens_sold'] += amount1
            token_stats[token1]['last_sol_rate'] = amount2 / (amount1 or 0.0000000001)  # SOL per token
            token_stats[token1]['last_trade'] = max(trade_time, token_stats[token1]['last_trade']) if token_stats[token1]['last_trade'] else trade_time
            token_stats[token1]['first_trade'] = min(trade_time, token_stats[token1]['first_trade']) if token_stats[token1]['first_trade'] else trade_time
            
            # Calculate and add sell fees
            SELL_FIXED_FEE = float(os.getenv('SELL_FIXED_FEE', 0.002))
            SELL_PERCENT_FEE = float(os.getenv('SELL_PERCENT_FEE', 0.063))
            fixed_fee = SELL_FIXED_FEE
            percent_fee = amount2 * SELL_PERCENT_FEE
            total_fee = fixed_fee + percent_fee
            token_stats[token1]['sell_fees'] += total_fee
            token_stats[token1]['total_fees'] += total_fee
        
        # Update trade count
        if token1 and not is_sol_token(token1):
            token_stats[token1]['trade_count'] += 1
        if token2 and not is_sol_token(token2):
            token_stats[token2]['trade_count'] += 1

    # Fetch current token prices for tokens with remaining balance
    api = SolscanAPI()
    sol_price = api.get_token_price("So11111111111111111111111111111111111111112")
    sol_price_usdt = sol_price.get('price_usdt', 0) if sol_price else 0

    # Count tokens that need price fetching
    tokens_to_fetch = sum(1 for token, stats in token_stats.items() if stats['tokens_bought'] - stats['tokens_sold'] >= 100)

    if tokens_to_fetch > 0:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task(f"[yellow]Fetching token prices...", total=tokens_to_fetch)
            
            for token, stats in token_stats.items():
                remaining_tokens = stats['tokens_bought'] - stats['tokens_sold']
                if remaining_tokens >= 100:  # Only fetch price if significant remaining balance
                    token_data = api.get_token_price(token)
                    if token_data:
                        stats['token_price_usdt'] = token_data.get('price_usdt', 0)
                        stats['decimals'] = token_data.get('decimals', 0)
                        stats['name'] = token_data.get('name', '')
                        stats['symbol'] = token_data.get('symbol', '')
                    progress.update(task, advance=1)
    else:
        console.print("[yellow]No tokens with significant remaining balance to fetch prices for.[/yellow]")

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
    with open(csv_file, 'w', encoding='utf-8') as f:
        f.write("Token;First Trade;Hold Time;Last Trade;First MC;SOL Invested;SOL Received;SOL Profit (after fees);Buy Fees;Sell Fees;Total Fees;Remaining Value;Total Profit (after fees);Token Price (USDT);Trades\n")
        
        for token, stats in sorted_tokens:
            remaining_tokens = stats['tokens_bought'] - stats['tokens_sold']
            sol_profit = stats['sol_received'] - stats['sol_invested'] - stats['total_fees']
            
            # Calculate remaining value using current token price if available
            token_price = stats.get('token_price_usdt')
            if token_price is not None and token_price > 0 and sol_price_usdt > 0:
                remaining_value = (remaining_tokens * token_price) / sol_price_usdt
            else:
                remaining_value = remaining_tokens * stats.get('last_sol_rate', 0)
            
            total_token_profit = sol_profit + remaining_value
            
            # Calculate number of trades for this token
            token_trades = sum(1 for trade in trades if 
                trade.token1 == token or 
                trade.token2 == token)
            total_trades += token_trades
            
            total_invested += stats['sol_invested']
            total_received += stats['sol_received']
            total_profit += sol_profit
            total_remaining += remaining_value
            
            profit_color = "green" if sol_profit >= 0 else "red"
            total_profit_color = "green" if total_token_profit >= 0 else "red"
            
            # Write to CSV (keep both absolute and relative times)
            # Handle missing token information
            try:
                token_price_csv = stats.get('token_price_usdt')
                if token_price_csv is None:
                    token_price_csv = 0
                
                first_trade_str = stats.get('first_trade').strftime('%Y-%m-%d %H:%M') if stats.get('first_trade') else 'N/A'
                last_trade_str = stats.get('last_trade').strftime('%Y-%m-%d %H:%M') if stats.get('last_trade') else 'N/A'
                hold_time_str = format_time_difference(stats.get('first_trade'), stats.get('last_trade')) if stats.get('first_trade') and stats.get('last_trade') else 'N/A'
                
                f.write(f"{token};" + 
                       f"{first_trade_str};" +
                       f"{hold_time_str};" +
                       f"{last_trade_str};" +
                       f"{first_trade_mc:.2f};" +
                       f"{stats.get('sol_invested', 0):.3f};" +
                       f"{stats.get('sol_received', 0):.3f};" +
                       f"{format_number_for_csv(sol_profit)};" +  # Already includes fees
                       f"{format_number_for_csv(stats.get('buy_fees', 0))};" +
                       f"{format_number_for_csv(stats.get('sell_fees', 0))};" +
                       f"{format_number_for_csv(stats.get('total_fees', 0))};" +
                       f"{format_number_for_csv(remaining_value)};" +
                       f"{format_number_for_csv(total_token_profit)};" +  # Already includes fees
                       f"{format_number_for_csv(token_price_csv)};" +
                       f"{token_trades}\n")
            except Exception as e:
                # If any error occurs while writing token data, write a safe fallback row
                f.write(f"{token};N/A;N/A;N/A;0.00;{stats.get('sol_invested', 0):.3f};{stats.get('sol_received', 0):.3f};" +
                       f"{format_number_for_csv(sol_profit)};" +  # Already includes fees
                       f"{format_number_for_csv(stats.get('buy_fees', 0))};{format_number_for_csv(stats.get('sell_fees', 0))};" +
                       f"{format_number_for_csv(stats.get('total_fees', 0))};ERROR;{format_number_for_csv(total_token_profit)};" +  # Already includes fees
                       f"0.000000;{token_trades}\n")
    
        # Add totals to CSV
        total_overall_profit = total_profit + total_remaining  # Already includes fees
        f.write(f"TOTAL;;;;" +
                f";{format_number_for_csv(total_invested)};" +
                f"{format_number_for_csv(total_received)};" +
                f"{format_number_for_csv(total_profit)};" +  # Already includes fees
                f"{format_number_for_csv(total_buy_fees)};" +
                f"{format_number_for_csv(total_sell_fees)};" +
                f"{format_number_for_csv(total_fees)};" +
                f"{format_number_for_csv(total_remaining)};" +
                f"{format_number_for_csv(total_overall_profit)};;" +  # Already includes fees
                f"{total_trades}\n")
    
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
    
    # Calculate ROI for different time periods
    current_time = int(time.time())
    periods = {
        '24h': {'seconds': 24 * 60 * 60, 'invested': 0, 'received': 0, 'profit': 0, 'roi_percent': None, 'fees': 0},
        '7d': {'seconds': 7 * 24 * 60 * 60, 'invested': 0, 'received': 0, 'profit': 0, 'roi_percent': None, 'fees': 0},
        '30d': {'seconds': 30 * 24 * 60 * 60, 'invested': 0, 'received': 0, 'profit': 0, 'roi_percent': None, 'fees': 0},
        '60d': {'seconds': 60 * 24 * 60 * 60, 'invested': 0, 'received': 0, 'profit': 0, 'roi_percent': None, 'fees': 0}
    }

    # Calculate period metrics
    for token, stats in token_stats.items():
        for period_name, period_data in periods.items():
            period_start = current_time - period_data['seconds']
            if stats['last_trade'] and stats['last_trade'].timestamp() >= period_start:
                period_data['invested'] += stats['sol_invested']
                period_data['received'] += stats['sol_received']
                period_data['fees'] += stats['total_fees']
                # Calculate profit after fees
                period_profit = stats['sol_received'] - stats['sol_invested'] - stats['total_fees']
                if stats.get('remaining_value', 0) > 0:
                    period_profit += stats['remaining_value']
                period_data['profit'] += period_profit

    # Calculate ROI percentages
    for period_data in periods.values():
        if period_data['invested'] > 0:
            period_data['roi_percent'] = (period_data['profit'] / period_data['invested']) * 100

    # Display ROI table
    console.print("\n[bold]Return on Investment (ROI)[/bold]")
    roi_table = Table(show_header=True, header_style="bold")
    roi_table.add_column("Period", justify="left", style="cyan")
    roi_table.add_column("Invested", justify="right", style="yellow")
    roi_table.add_column("Received", justify="right", style="yellow")
    roi_table.add_column("Profit", justify="right", style="green")
    roi_table.add_column("ROI %", justify="right", style="magenta")

    # Define order of periods to display
    period_order = ['60d', '30d', '7d', '24h']

    for period in period_order:
        data = periods[period]
        if data['invested'] > 0:
            profit_color = "green" if data['profit'] >= 0 else "red"
            roi_color = "green" if data['roi_percent'] >= 0 else "red"
            roi_table.add_row(
                period.upper(),
                f"{data['invested']:.3f} ◎",
                f"{data['received']:.3f} ◎",
                f"[{profit_color}]{data['profit']:+.3f} ◎[/{profit_color}]",
                f"[{roi_color}]{data['roi_percent']:+.2f}%[/{roi_color}]"
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
        amount_info = trade.amount_info
        if not amount_info:
            continue
            
        token1 = amount_info.get('token1')
        token2 = amount_info.get('token2')
        
        # Count if neither token is SOL
        if token1 and token2 and not is_sol_token(token1) and not is_sol_token(token2):
            non_sol_txs += 1

    # Calculate median profit and loss and holding times
    profits = []
    losses = []
    investments = []  # Track all investments
    hold_times = []  # Track all hold times
    for token, stats in token_stats.items():
        sol_profit = stats['sol_received'] - stats['sol_invested'] - stats['total_fees']
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
    summary_table.add_column("Transaction Type")
    summary_table.add_column("Count", justify="right", style="yellow")
    summary_table.add_column("Percentage", justify="right", style="green")

    summary_table.add_row(
        "[gold]Total DeFi Transactions[/gold]",
        str(total_defi_txs),
        "100%"
    )
    summary_table.add_row(
        "[gold]Non-SOL Token Swaps[/gold]",
        str(non_sol_txs),
        f"{(non_sol_txs/total_defi_txs*100):.1f}%" if total_defi_txs > 0 else "0%"
    )
    summary_table.add_row(
        "[gold]SOL-Involved Swaps[/gold]",
        str(total_defi_txs - non_sol_txs),
        f"{((total_defi_txs-non_sol_txs)/total_defi_txs*100):.1f}%" if total_defi_txs > 0 else "0%"
    )

    # Add section for profit/loss statistics
    summary_table.add_section()
    summary_table.add_row(
        "[gold]Win Rate[/gold]",
        f"[{win_rate_color}]{win_rate:.1f}%[/{win_rate_color}]",
        f"({len(profits)}/{total_tokens} tokens)"
    )
    summary_table.add_row(
        "[gold]Median Investment per Token[/gold]",
        f"{median_investment:.3f} ◎",
        ""
    )
    if profits:
        summary_table.add_row(
            "[gold]Median Profit per Token[/gold]",
            f"[green]+{median_profit:.3f} ◎ (+{median_profit_roi:.1f}%)[/green]",
            f"({len(profits)} tokens)"
        )
    if losses:
        summary_table.add_row(
            "[gold]Median Loss per Token[/gold]",
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
        keys_table.add_row("tps", "Tokens per SOL at investment")
        keys_table.add_row("fmc", "First Market Cap")
        keys_table.add_row("MC", "Market Cap")
        keys_table.add_row("mme", "Median Market Entry")
        keys_table.add_row("mmcp", "Median % of Market Cap at Entry")

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
        examples_table.add_row("-f \"MC:>50000\"", "Filter tokens with market cap > 50000")
        examples_table.add_row("-f \"wr:>50\"", "Filter tokens with win rate > 50%")
        examples_table.add_row("-f \"mht:>86400\"", "Filter tokens held more than 24 hours")
        examples_table.add_row("-f \"t:>500;fmc:>25000\"", "Multiple filters combined")
        examples_table.add_row("-f \"tps:>1000000\"", "Filter tokens with >1M tokens per SOL exchange rate at first investment")
        examples_table.add_row("-f \"mwp:>100\"", "Filter tokens with median winnings percentage > 100%")
        examples_table.add_row("-f \"mme:>1000000\"", "Filter tokens with median market entry > 1M")
        examples_table.add_row("-f \"mmcp:<1\"", "Filter tokens with median % of market cap at entry < 1%")
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
            elif key == 'fmc':
                actual_value = stats.get('first_market_cap', 0)
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
            elif key == 'MC':
                actual_value = stats.get('market_cap', 0)
            elif key == 'mme':
                actual_value = stats.get('median_market_entry', 0)
            elif key == 'mmcp':
                actual_value = stats.get('median_market_cap_percentage', 0)
            
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

def analyze_trades(trades: List[SolscanDefiActivity], console: Console) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    """
    Analyze trades and return structured data instead of displaying it.
    
    Args:
        trades: List of SolscanDefiActivity objects
        console: Rich console for output
        
    Returns a tuple of:
    - List of token dictionaries sorted by last trade time
    - ROI statistics dictionary
    - Transaction summary dictionary
    """
    # Load fee values from environment
    load_dotenv()
    BUY_FIXED_FEE = float(os.getenv('BUY_FIXED_FEE', '0.002'))
    SELL_FIXED_FEE = float(os.getenv('SELL_FIXED_FEE', '0.002'))
    BUY_PERCENT_FEE = float(os.getenv('BUY_PERCENT_FEE', '0.022912'))
    SELL_PERCENT_FEE = float(os.getenv('SELL_PERCENT_FEE', '0.063'))
    
    # Dictionary to track token stats
    token_stats = {}
    period_stats = {
        '24h': {'invested': 0, 'received': 0, 'start_time': datetime.now().timestamp() - 86400},
        '7d': {'invested': 0, 'received': 0, 'start_time': datetime.now().timestamp() - 7 * 86400},
        '30d': {'invested': 0, 'received': 0, 'start_time': datetime.now().timestamp() - 30 * 86400},
        '60d': {'invested': 0, 'received': 0, 'start_time': datetime.now().timestamp() - 60 * 86400}
    }

    # First pass: collect all trades and update period stats
    for trade in trades:
        token1 = trade.token1
        token2 = trade.token2
        token1_decimals = trade.token1_decimals
        token2_decimals = trade.token2_decimals

        # If no tokens are involved, skip
        if not token1 or not token2:
            continue
        
        # If USDT or USDC are involved, skip
        if is_usd(token1) or is_usd(token2):
            continue

        # if no SOL is involved, skip
        if not is_sol_token(token1) and not is_sol_token(token2):
            continue

        # Initialize stats for tokens found in sells or buys
        if (is_sol_token(token2) and token1 not in token_stats) or (is_sol_token(token1) and token2 not in token_stats):
            # For token1 (sell case)
            if is_sol_token(token2) and token1 not in token_stats:
                token_stats[token1] = {
                    'sol_invested': 0,
                    'sol_received': 0,
                    'tokens_tally': 0, # This might go negative, which is now allowed
                    'tokens_bought': 0,
                    'tokens_sold': 0,
                    'last_trade': None,
                    'first_trade': None,  # Will be set properly below
                    'last_sol_rate': 0,
                    'token_price_usdt': 0,
                    'decimals': 0,
                    'name': '',
                    'symbol': '',
                    'hold_time': None,
                    'trade_count': 0,
                    'buy_fees': 0,
                    'sell_fees': 0,
                    'total_fees': 0
                }
            
            # For token2 (buy case)
            if is_sol_token(token1) and token2 not in token_stats:
                token_stats[token2] = {
                    'sol_invested': 0,
                    'sol_received': 0,
                    'tokens_tally': 0,
                    'tokens_bought': 0,
                    'tokens_sold': 0,
                    'last_trade': None,
                    'first_trade': None,  # Will be set properly below
                    'last_sol_rate': 0,
                    'token_price_usdt': 0,
                    'decimals': 0,
                    'name': '',
                    'symbol': '',
                    'hold_time': None,
                    'trade_count': 0,
                    'buy_fees': 0,
                    'sell_fees': 0,
                    'total_fees': 0
                }
        
        try:
            amount1_raw = trade.amount1
            amount2_raw = trade.amount2
            amount1 = float(amount1_raw if amount1_raw is not None else 0) / (10 ** token1_decimals)
            amount2 = float(amount2_raw if amount2_raw is not None else 0) / (10 ** token2_decimals)
        except (ValueError, TypeError):
            continue

        if amount2 == 0 or amount1 == 0:
            continue
        
        trade_time = datetime.fromtimestamp(trade.block_time)
        trade_timestamp = trade.block_time
        
        # Update token stats timestamps
        if is_sol_token(token1):
            # Buying token2 with SOL
            # Update last_trade
            if token_stats[token2]['last_trade'] is None or trade_time > token_stats[token2]['last_trade']:
                token_stats[token2]['last_trade'] = trade_time
            
            # Update first_trade
            if token_stats[token2]['first_trade'] is None or trade_time < token_stats[token2]['first_trade']:
                token_stats[token2]['first_trade'] = trade_time
        else:
            # Selling token1 for SOL
            # Update last_trade
            if token_stats[token1]['last_trade'] is None or trade_time > token_stats[token1]['last_trade']:
                token_stats[token1]['last_trade'] = trade_time
            
            # Update first_trade
            if token_stats[token1]['first_trade'] is None or trade_time < token_stats[token1]['first_trade']:
                token_stats[token1]['first_trade'] = trade_time

        if is_sol_token(token1) and not is_sol_token(token2):
            # Buying tokens with SOL
            token_stats[token2]['sol_invested'] += amount1
            token_stats[token2]['tokens_bought'] += amount2
            token_stats[token2]['tokens_tally'] += amount2_raw
            token_stats[token2]['last_sol_rate'] = amount1 / (amount2 or 0.0000000001)

            # Calculate and add buy fees
            fixed_fee = BUY_FIXED_FEE
            percent_fee = amount1 * BUY_PERCENT_FEE
            total_fee = fixed_fee + percent_fee
            token_stats[token2]['buy_fees'] += total_fee
            token_stats[token2]['total_fees'] += total_fee

            # Period stats
            for period, stats in period_stats.items():
                if trade_timestamp >= stats['start_time']:
                    stats['invested'] += amount1
            
        elif is_sol_token(token2) and not is_sol_token(token1):
            # Selling tokens for SOL - now we process all sell transactions
            token_stats[token1]['sol_received'] += amount2
            token_stats[token1]['tokens_sold'] += amount1
            token_stats[token1]['tokens_tally'] -= amount1_raw
            token_stats[token1]['last_sol_rate'] = amount2 / (amount1 or 0.0000000001)
            
            # Calculate and add sell fees
            fixed_fee = SELL_FIXED_FEE
            percent_fee = amount2 * SELL_PERCENT_FEE
            total_fee = fixed_fee + percent_fee
            token_stats[token1]['sell_fees'] += total_fee
            token_stats[token1]['total_fees'] += total_fee

            # Period stats
            for period, stats in period_stats.items():
                if trade_timestamp >= stats['start_time']:
                    stats['received'] += amount2
        
        if not is_sol_token(token1):
            token_stats[token1]['trade_count'] += 1
        else:
            token_stats[token2]['trade_count'] += 1

    # Fetch token prices
    api = SolscanAPI()
    sol_price = api.get_token_price("So11111111111111111111111111111111111111112")
    sol_price_usdt = sol_price.get('price_usdt', 0) if sol_price else 0

    tokens_to_fetch = sum(1 for token, stats in token_stats.items() if stats['tokens_bought'] - stats['tokens_sold'] >= 100)

    if tokens_to_fetch > 0:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task(f"[yellow]Fetching token prices...", total=tokens_to_fetch)
            
            for token, stats in token_stats.items():
                remaining_tokens = stats['tokens_bought'] - stats['tokens_sold']
                if remaining_tokens >= 100:
                    token_data = api.get_token_price(token)
                    if token_data:
                        stats['token_price_usdt'] = token_data.get('price_usdt', 0)
                        stats['decimals'] = token_data.get('decimals', 0)
                        stats['name'] = token_data.get('name', '')
                        stats['symbol'] = token_data.get('symbol', '')
                    progress.update(task, advance=1)

    # Calculate hold times and prepare token data
    current_time = datetime.now()
    token_data_list = []
    # Track investments, profits, losses, and hold times for median calculations
    investments = []
    profits = []
    losses = []
    hold_times = []
    roi_percentages = []  # Add list to track individual token ROI percentages
    market_entries = []   # Track market cap at entry for median calculation
    mc_investment_percentages = []  # Track % of market cap invested at entry
    token_profits = []  # Track individual token profits
    token_losses = []   # Track individual token losses

    for token, stats in token_stats.items():
        if is_sol_token(token):
            continue
            
        remaining_tokens = stats['tokens_bought'] - stats['tokens_sold']
        if remaining_tokens < 1e-6:
            remaining_tokens = 0
        sol_profit = stats['sol_received'] - stats['sol_invested'] - stats['total_fees']
        
        # Calculate remaining value
        token_price = stats.get('token_price_usdt')
        if token_price is not None and token_price > 0 and sol_price_usdt > 0:
            remaining_value = (remaining_tokens * token_price) / sol_price_usdt
        else:
            remaining_value = remaining_tokens * stats.get('last_sol_rate', 0)
        
        # Calculate profits including fees
        total_token_profit = sol_profit + remaining_value
        
        # Track individual token profits/losses
        if total_token_profit > 0:
            token_profits.append(total_token_profit)
        elif total_token_profit < 0:
            token_losses.append(abs(total_token_profit))

        # Calculate ROI percentage for this token and add to list
        if stats['sol_invested'] > 0:
            roi_percent = (total_token_profit / stats['sol_invested']) * 100
            roi_percentages.append(roi_percent)
        
        # Calculate first trade market cap
        tokens_bought = stats.get('tokens_bought', 0)
        first_trade_rate = stats['sol_invested'] / tokens_bought if tokens_bought > 0 else 0
        first_trade_mc = first_trade_rate * sol_price_usdt * 1_000_000_000
        
        # Track market cap at entry
        mc_investment_percentage = 0
        if first_trade_mc > 0:
            market_entries.append(first_trade_mc)
            
            # Calculate % of market cap invested
            if sol_price_usdt > 0:
                sol_value_usd = stats['sol_invested'] * sol_price_usdt
                mc_investment_percentage = (sol_value_usd / first_trade_mc) * 100
                mc_investment_percentages.append(mc_investment_percentage)

        # Calculate hold time
        if stats['first_trade']:
            if remaining_tokens > 0:
                stats['last_trade'] = current_time
            if stats['last_trade']:
                # Ensure first_trade is earlier than last_trade
                first = stats['first_trade']
                last = stats['last_trade']
                if first > last:
                    first, last = last, first
                duration = last - first
                stats['hold_time'] = duration
                hold_times.append(duration)
        
        # Track profits/losses (after fees)
        investments.append(stats['sol_invested'])
        if sol_profit > 0:
            profits.append(sol_profit)
        elif sol_profit < 0:
            losses.append(abs(sol_profit))

        # Create token data dictionary
        token_data = {
            'address': token,
            'hold_time': stats['hold_time'].total_seconds() if stats['hold_time'] else 0,
            'last_trade': stats['last_trade'].timestamp() if stats['last_trade'] else 0,
            'first_trade': stats['first_trade'].timestamp() if stats['first_trade'] else 0,
            'first_mc': first_trade_mc,
            'sol_invested': stats['sol_invested'],
            'sol_received': stats['sol_received'],
            'sol_profit': sol_profit,  # Now includes fees
            'buy_fees': stats['buy_fees'],
            'sell_fees': stats['sell_fees'],
            'total_fees': stats['total_fees'],
            'remaining_value': remaining_value,
            'total_profit': total_token_profit,  # Now includes fees
            'token_price': stats['token_price_usdt'],
            'trades': stats['trade_count'],
            'mc_investment_percentage': mc_investment_percentage  # Add investment % of MC at entry
        }
        token_data_list.append(token_data)

    # Sort by last trade time
    token_data_list.sort(key=lambda x: x['last_trade'])  # Removed reverse=True to show oldest first

    # Prepare ROI data
    roi_data = {}
    period_remaining_value = {'24h': 0, '7d': 0, '30d': 0, '60d': 0}
    period_fees = {'24h': 0, '7d': 0, '30d': 0, '60d': 0}  # Track fees for each period
    
    # Calculate remaining value and fees for each period
    for token, stats in token_stats.items():
        remaining_tokens = stats['tokens_bought'] - stats['tokens_sold']
        token_price = stats.get('token_price_usdt')
        if token_price is not None and token_price > 0 and sol_price_usdt > 0:
            remaining_value = (remaining_tokens * token_price) / sol_price_usdt
        else:
            remaining_value = remaining_tokens * stats.get('last_sol_rate', 0)
        
        if stats.get('last_trade'):
            last_trade_time = stats['last_trade'].timestamp()
            current_time_ts = current_time.timestamp()
            
            # Add remaining value and fees to appropriate periods
            if last_trade_time >= current_time_ts - 86400:  # 24h
                period_remaining_value['24h'] += remaining_value
                period_fees['24h'] += stats['total_fees']
            if last_trade_time >= current_time_ts - 7 * 86400:  # 7d
                period_remaining_value['7d'] += remaining_value
                period_fees['7d'] += stats['total_fees']
            if last_trade_time >= current_time_ts - 30 * 86400:  # 30d
                period_remaining_value['30d'] += remaining_value
                period_fees['30d'] += stats['total_fees']
            if last_trade_time >= current_time_ts - 60 * 86400:  # 60d
                period_remaining_value['60d'] += remaining_value
                period_fees['60d'] += stats['total_fees']

    for period, stats in period_stats.items():
        invested = stats.get('invested', 0)
        total_received = stats.get('received', 0) + period_remaining_value.get(period, 0)
        period_total_fees = period_fees.get(period, 0)
        
        # Calculate profit after fees
        profit = total_received - invested - period_total_fees
        
        # Calculate ROI percentage after fees
        if invested > 0:
            roi_percent = ((total_received - period_total_fees) / invested - 1) * 100
        else:
            roi_percent = None
        
        roi_data[period] = {
            'invested': invested,
            'received': total_received,
            'profit': profit,  # Now includes fees
            'roi_percent': roi_percent,  # Now includes fees
            'fees': period_total_fees
        }

    # Calculate median ROI % from individual token ROI percentages
    median_roi_percent = sorted(roi_percentages)[len(roi_percentages)//2] if roi_percentages else 0
    
    # Calculate ROI standard deviation
    roi_std_dev = 0
    if roi_percentages:
        mean_roi = sum(roi_percentages) / len(roi_percentages)
        squared_diff_sum = sum((x - mean_roi) ** 2 for x in roi_percentages)
        roi_std_dev = (squared_diff_sum / len(roi_percentages)) ** 0.5
    
    # Calculate median profit and loss
    median_profit = sorted(token_profits)[len(token_profits)//2] if token_profits else 0
    median_loss = sorted(token_losses)[len(token_losses)//2] if token_losses else 0

    # Prepare transaction summary
    total_defi_txs = len(trades)
    non_sol_txs = sum(1 for trade in trades if 
        not is_sol_token(trade.token1) and not is_sol_token(trade.token2))
    
    median_investment = sorted(investments)[len(investments)//2] if investments else 0
    median_hold_time = sorted(hold_times)[len(hold_times)//2] if hold_times else timedelta()
    
    # Calculate median market entry and median % of market cap at entry
    median_market_entry = sorted(market_entries)[len(market_entries)//2] if market_entries else 0
    median_mc_percentage = sorted(mc_investment_percentages)[len(mc_investment_percentages)//2] if mc_investment_percentages else 0
    
    total_tokens = len(profits) + len(losses)
    win_rate = (len(profits) / total_tokens * 100) if total_tokens > 0 else 0
    
    tx_summary = {
        'total_transactions': total_defi_txs,
        'non_sol_swaps': non_sol_txs,
        'sol_swaps': total_defi_txs - non_sol_txs,
        'win_rate': win_rate,
        'win_rate_ratio': f"{len(profits)}/{total_tokens}",
        'median_investment': median_investment,
        'median_roi_percent': median_roi_percent,
        'roi_std_dev': roi_std_dev,
        'median_hold_time': median_hold_time.total_seconds(),
        'median_market_entry': median_market_entry,
        'median_mc_percentage': median_mc_percentage,
        'median_profit': median_profit,  # Add median profit
        'median_loss': median_loss      # Add median loss
    }

    return token_data_list, roi_data, tx_summary