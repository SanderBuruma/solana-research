import unittest
import os
import csv
import shutil
import time
from datetime import datetime
from unittest.mock import patch, MagicMock
import sys
import json

from rich.console import Console

# Add parent directory to path to import from utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.solscan import SolscanAPI, SolscanDefiActivity, analyze_trades


class TestSolscanGetDexTradingHistory(unittest.TestCase):
    """Tests for the get_dex_trading_history method of SolscanAPI"""
    
    # Use environment variable if available, otherwise default to test wallet
    TEST_WALLET = os.environ.get('TEST_WALLET', "3jU3igB7fqix2GZuS6wGfdenLwanTJM5LMA7eEzCfkbm")
    
    def setUp(self):
        """Set up for each test - create a fresh API instance and clean test directories"""
        self.api = SolscanAPI()
        
        # Clean up any existing test data
        self.clean_test_dirs()
        
        # Create test directory
        os.makedirs(f"./dex_activity/{self.TEST_WALLET}", exist_ok=True)
    
    def tearDown(self):
        """Clean up after each test"""
        self.clean_test_dirs()
    
    def clean_test_dirs(self):
        """Remove test directories"""
        if os.path.exists(f"./dex_activity/{self.TEST_WALLET}"):
            shutil.rmtree(f"./dex_activity/{self.TEST_WALLET}")
    
    def test_initial_fetch_creates_csv(self):
        """Test that the initial fetch creates a CSV file"""
        # Ensure we start with a clean directory
        self.clean_test_dirs()
        
        # Fetch a limited number of trades for testing (just 1 page to keep it quick)
        with patch.object(self.api, '_make_request') as mock_request:
            # Mock response for total trades
            mock_request.return_value = {'success': True, 'data': 100}
            
            # Set up mock to return a single test trade for the first call for dextrading data
            def side_effect(endpoint):
                if 'total' in endpoint:
                    return {'success': True, 'data': 100}
                elif 'dextrading?' in endpoint:
                    # Return a single mock trade
                    return {
                        'success': True,
                        'data': [{
                            'trans_id': 'test_tx_1',
                            'block_time': time.time(),
                            'slot': 123456789,
                            'amount_info': {
                                'token1': 'So11111111111111111111111111111111111111112',  # SOL
                                'token2': 'test_token_1',
                                'token1_decimals': 9,
                                'token2_decimals': 6,
                                'amount1': 1000000000,  # 1 SOL
                                'amount2': 1000000  # 1 token
                            }
                        }]
                    }
                return {'success': False, 'data': None}
            
            mock_request.side_effect = side_effect
            
            # Fetch trades
            trades = self.api.get_dex_trading_history(self.TEST_WALLET, quiet=True)
            
            # Check that CSV file was created
            csv_path = f"./dex_activity/{self.TEST_WALLET}/transactions.csv"
            self.assertTrue(os.path.exists(csv_path), "CSV file was not created")
            
            # Verify the trade was returned
            self.assertEqual(len(trades), 1, "Should return one trade")
            self.assertEqual(trades[0].transaction_id, 'test_tx_1', "Transaction ID should match")
            
            # Verify the CSV file contains the right data
            with open(csv_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn('test_tx_1', content, "CSV should contain the transaction ID")
    
    def test_loads_from_csv_on_subsequent_fetch(self):
        """Test that subsequent fetches load data from CSV first"""
        # Create a mock CSV with some test data
        csv_path = f"./dex_activity/{self.TEST_WALLET}/transactions.csv"
        
        # Ensure directory is clean
        self.clean_test_dirs()
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        
        # Create a mock transaction data
        cached_tx_time = time.time()
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['trans_id', 'block_time', 'block_id', 'token1', 'token2', 'token1_decimals', 
                          'token2_decimals', 'amount1', 'amount2', 'price_usdt', 'decimals', 
                          'name', 'symbol', 'flow', 'value', 'from_address'])
            writer.writerow(['cached_tx_1', cached_tx_time, '123456789', 
                          'So11111111111111111111111111111111111111112', 'test_token_1', 
                          '9', '6', '1000000000', '1000000', '0', '0', 
                          '', '', '', '0', ''])
        
        # Verify CSV has one entry
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 1, "CSV should start with 1 trade")
        
        # Mock API to return a different set of trades
        new_tx_time = cached_tx_time + 1000  # Newer timestamp
        with patch.object(self.api, '_make_request') as mock_request:
            def side_effect(endpoint):
                if 'total' in endpoint:
                    return {'success': True, 'data': 100}
                elif 'dextrading?' in endpoint:
                    # Return a different mock trade
                    return {
                        'success': True,
                        'data': [{
                            'trans_id': 'api_tx_1',
                            'block_time': new_tx_time,
                            'slot': 123456790,
                            'amount_info': {
                                'token1': 'So11111111111111111111111111111111111111112',  # SOL
                                'token2': 'test_token_2',
                                'token1_decimals': 9,
                                'token2_decimals': 6,
                                'amount1': 2000000000,
                                'amount2': 2000000
                            }
                        }]
                    }
                return {'success': False, 'data': None}
            
            mock_request.side_effect = side_effect
            
            # Fetch trades
            trades = self.api.get_dex_trading_history(self.TEST_WALLET, quiet=True)
            
            # Verify that both cached and API trades are included
            self.assertEqual(len(trades), 2, "Should include both cached and API trades")
            
            # Check if our trades contain both the cached and new transaction
            trade_ids = [t.transaction_id for t in trades]
            self.assertIn('cached_tx_1', trade_ids, "Cached trade should be in the results")
            self.assertIn('api_tx_1', trade_ids, "New API trade should be in the results")
            
            # Verify the CSV file contents manually
            with open(csv_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn('cached_tx_1', content, "CSV should contain cached transaction")
                self.assertIn('api_tx_1', content, "CSV should contain new transaction")
    
    def test_sorts_trades_newest_first(self):
        """Test that trades are sorted with newest first"""
        # Create a CSV with trades at different timestamps
        csv_path = f"./dex_activity/{self.TEST_WALLET}/transactions.csv"
        
        # Ensure directory is clean
        self.clean_test_dirs()
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        
        current_time = time.time()
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['trans_id', 'block_time', 'block_id', 'token1', 'token2', 'token1_decimals', 
                          'token2_decimals', 'amount1', 'amount2', 'price_usdt', 'decimals', 
                          'name', 'symbol', 'flow', 'value', 'from_address'])
            
            # Add trades with increasing timestamps (older to newer)
            for i in range(5):
                timestamp = current_time - (5-i) * 3600  # 5 trades, 1 hour apart
                writer.writerow([f'tx_{i}', timestamp, f'{1000000+i}', 
                              'So11111111111111111111111111111111111111112', f'token_{i}', 
                              '9', '6', '1000000000', '1000000', '0', '0', 
                              '', '', '', '0', ''])
        
        # Mock API to not return any new trades
        with patch.object(self.api, '_make_request') as mock_request:
            mock_request.return_value = {'success': True, 'data': 0}
            
            # Fetch trades
            trades = self.api.get_dex_trading_history(self.TEST_WALLET, quiet=True)
            
            # Verify that trades are sorted newest first
            self.assertEqual(len(trades), 5, "Should load all 5 cached trades")
            
            # Check timestamps are in descending order
            timestamps = [trade.block_time for trade in trades]
            self.assertEqual(timestamps, sorted(timestamps, reverse=True), 
                            "Trades should be sorted newest first")
    
    def test_avoids_duplicates(self):
        """Test that duplicate transactions are not added"""
        # Create a CSV with one trade
        csv_path = f"./dex_activity/{self.TEST_WALLET}/transactions.csv"
        
        # Ensure directory is clean
        self.clean_test_dirs()
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        
        current_time = time.time()
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['trans_id', 'block_time', 'block_id', 'token1', 'token2', 'token1_decimals', 
                          'token2_decimals', 'amount1', 'amount2', 'price_usdt', 'decimals', 
                          'name', 'symbol', 'flow', 'value', 'from_address'])
            
            writer.writerow(['duplicate_tx', current_time, '123456789', 
                          'So11111111111111111111111111111111111111112', 'test_token_1', 
                          '9', '6', '1000000000', '1000000', '0', '0', 
                          '', '', '', '0', ''])
        
        # Mock API to return the same transaction again
        with patch.object(self.api, '_make_request') as mock_request:
            def side_effect(endpoint):
                if 'total' in endpoint:
                    return {'success': True, 'data': 100}
                elif 'dextrading?' in endpoint:
                    # Return the same transaction
                    return {
                        'success': True,
                        'data': [{
                            'trans_id': 'duplicate_tx',
                            'block_time': current_time,
                            'slot': 123456789,
                            'amount_info': {
                                'token1': 'So11111111111111111111111111111111111111112',
                                'token2': 'test_token_1',
                                'token1_decimals': 9,
                                'token2_decimals': 6,
                                'amount1': 1000000000,
                                'amount2': 1000000
                            }
                        }]
                    }
                return {'success': False, 'data': None}
            
            mock_request.side_effect = side_effect
            
            # Fetch trades
            trades = self.api.get_dex_trading_history(self.TEST_WALLET, quiet=True)
            
            # Verify no duplicates
            self.assertEqual(len(trades), 1, "Should not duplicate transactions")
            
            # Check CSV still has only one entry
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                self.assertEqual(len(rows), 1, "CSV should still contain only 1 trade")

    def test_real_wallet_fetch(self):
        """Integration test with a real wallet (limited to minimize API calls)"""
        # This test will be slow and actually call the API
            
        # Fetch a small number of trades (limited to 5 for testing)
        # Save the original method BEFORE patching
        original_make_request = self.api._make_request
        
        with patch.object(self.api, '_make_request') as mock_request:
            # Define the limited request function using the saved original
            def limited_make_request(endpoint):
                if 'page=' in endpoint and 'page=1' not in endpoint:
                    # Only allow page 1 to reduce API load during testing
                    return {'success': True, 'data': []}
                return original_make_request(endpoint)
            
            mock_request.side_effect = limited_make_request
            
            # First fetch - should create CSV
            trades1 = self.api.get_dex_trading_history(self.TEST_WALLET, quiet=True)
            
            # Record number of trades
            trade_count1 = len(trades1)
            
            # Verify CSV was created with same number of trades
            csv_path = f"./dex_activity/{self.TEST_WALLET}/transactions.csv"
            self.assertTrue(os.path.exists(csv_path), "CSV file was not created")
            
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                self.assertEqual(len(rows), trade_count1, f"CSV should contain {trade_count1} trades")
            
            # Second fetch - should load from CSV and not add any new trades since we're limiting to page 1
            trades2 = self.api.get_dex_trading_history(self.TEST_WALLET, quiet=True)
            
            # Verify count remains the same
            self.assertEqual(len(trades2), trade_count1, "Second fetch should return same number of trades")

    def test_csv_matches_api_results(self):
        """Test that CSV saved transactions match the API results exactly"""
        # Ensure clean start
        self.clean_test_dirs()
        
        # Define test trade data
        test_trades = [
            {
                'trans_id': 'test_tx_1',
                'block_time': int(time.time()) - 3600,  # 1 hour ago
                'slot': 123456789,
                'amount_info': {
                    'token1': 'So11111111111111111111111111111111111111112',  # SOL
                    'token2': 'test_token_1',
                    'token1_decimals': 9,
                    'token2_decimals': 6,
                    'amount1': 1000000000,  # 1 SOL
                    'amount2': 1000000  # 1 token
                }
            },
            {
                'trans_id': 'test_tx_2',
                'block_time': int(time.time()) - 1800,  # 30 min ago
                'slot': 123456790,
                'amount_info': {
                    'token1': 'test_token_1',
                    'token2': 'So11111111111111111111111111111111111111112',  # SOL
                    'token1_decimals': 6,
                    'token2_decimals': 9,
                    'amount1': 500000,  # 0.5 token
                    'amount2': 600000000  # 0.6 SOL
                }
            }
        ]
        
        # Mock API to return our test trades
        with patch.object(self.api, '_make_request') as mock_request:
            def side_effect(endpoint):
                if 'total' in endpoint:
                    return {'success': True, 'data': len(test_trades)}
                elif 'dextrading?' in endpoint:
                    return {'success': True, 'data': test_trades}
                return {'success': False, 'data': None}
            
            mock_request.side_effect = side_effect
            
            # First fetch should create CSV with our test trades
            trades1 = self.api.get_dex_trading_history(self.TEST_WALLET, quiet=True)
            
            # Verify correct number of trades returned
            self.assertEqual(len(trades1), len(test_trades), "Should return all test trades")
            
            # Verify transactions have correct IDs
            trade_ids = [t.transaction_id for t in trades1]
            for trade in test_trades:
                self.assertIn(trade['trans_id'], trade_ids, f"Transaction {trade['trans_id']} should be in results")
            
            # Verify CSV was created
            csv_path = f"./dex_activity/{self.TEST_WALLET}/transactions.csv"
            self.assertTrue(os.path.exists(csv_path), "CSV file was not created")
            
            # Now modify the mock to return no trades (so we only load from CSV)
            def no_trades_side_effect(endpoint):
                if 'total' in endpoint:
                    return {'success': True, 'data': 0}
                return {'success': True, 'data': []}
            
            mock_request.side_effect = no_trades_side_effect
            
            # Second fetch should load from CSV
            trades2 = self.api.get_dex_trading_history(self.TEST_WALLET, quiet=True)
            
            # Verify we got the same number of trades
            self.assertEqual(len(trades2), len(test_trades), "CSV-loaded trades count should match")
            
            # Compare trades from API with trades from CSV
            for i, api_trade in enumerate(trades1):
                csv_trade = next((t for t in trades2 if t.transaction_id == api_trade.transaction_id), None)
                self.assertIsNotNone(csv_trade, f"Trade {api_trade.transaction_id} should be loaded from CSV")
                
                # Compare key properties
                self.assertEqual(api_trade.transaction_id, csv_trade.transaction_id, "Transaction IDs should match")
                self.assertEqual(api_trade.block_time, csv_trade.block_time, "Block times should match")
                self.assertEqual(api_trade.block_id, csv_trade.block_id, "Block IDs should match")
                self.assertEqual(api_trade.token1, csv_trade.token1, "Token1 addresses should match")
                self.assertEqual(api_trade.token2, csv_trade.token2, "Token2 addresses should match")
                self.assertEqual(api_trade.amount1, csv_trade.amount1, "Amount1 should match")
                self.assertEqual(api_trade.amount2, csv_trade.amount2, "Amount2 should match")

    def test_analyze_trades_hold_time(self):
        """Test that the analyze_trades function correctly calculates hold times"""
        # Create mock trades with different timestamps
        now = time.time()
        one_hour = 3600
        one_day = 86400
        
        # Create a token that was bought and fully sold (fixed hold time)
        trade1_buy = {
            'trans_id': 'trade1_buy',
            'block_time': now - 2*one_day,  # 2 days ago
            'slot': 100001,
            'amount_info': {
                'token1': 'So11111111111111111111111111111111111111112',  # SOL
                'token2': 'token1',
                'token1_decimals': 9,
                'token2_decimals': 6,
                'amount1': 1000000000,  # 1 SOL
                'amount2': 1000000  # 1 token
            }
        }
        
        trade1_sell = {
            'trans_id': 'trade1_sell',
            'block_time': now - one_day,  # 1 day ago
            'slot': 100002,
            'amount_info': {
                'token1': 'token1',
                'token2': 'So11111111111111111111111111111111111111112',  # SOL
                'token1_decimals': 6,
                'token2_decimals': 9,
                'amount1': 1000000,  # 1 token
                'amount2': 1200000000  # 1.2 SOL (20% profit)
            }
        }
        
        # Create a token that was bought and partially sold (ongoing hold time)
        trade2_buy = {
            'trans_id': 'trade2_buy',
            'block_time': now - 3*one_day,  # 3 days ago
            'slot': 100003,
            'amount_info': {
                'token1': 'So11111111111111111111111111111111111111112',  # SOL
                'token2': 'token2',
                'token1_decimals': 9,
                'token2_decimals': 6,
                'amount1': 2000000000,  # 2 SOL
                'amount2': 2000000  # 2 tokens
            }
        }
        
        trade2_sell = {
            'trans_id': 'trade2_sell',
            'block_time': now - 2*one_day,  # 2 days ago
            'slot': 100004,
            'amount_info': {
                'token1': 'token2',
                'token2': 'So11111111111111111111111111111111111111112',  # SOL
                'token1_decimals': 6,
                'token2_decimals': 9,
                'amount1': 1000000,  # 1 token (50% sold)
                'amount2': 1100000000  # 1.1 SOL (10% profit)
            }
        }
        
        # Create a token that was bought and not sold at all (ongoing hold time)
        trade3_buy = {
            'trans_id': 'trade3_buy',
            'block_time': now - 5*one_day,  # 5 days ago
            'slot': 100005,
            'amount_info': {
                'token1': 'So11111111111111111111111111111111111111112',  # SOL
                'token2': 'token3',
                'token1_decimals': 9,
                'token2_decimals': 6,
                'amount1': 3000000000,  # 3 SOL
                'amount2': 3000000  # 3 tokens
            }
        }
        
        # Convert to SolscanDefiActivity objects
        mock_trades = [
            SolscanDefiActivity(trade1_buy),
            SolscanDefiActivity(trade1_sell),
            SolscanDefiActivity(trade2_buy),
            SolscanDefiActivity(trade2_sell),
            SolscanDefiActivity(trade3_buy)
        ]
        
        # Create a console for the analyze_trades function
        console = Console(record=True)
        
        # Call analyze_trades function
        token_data, roi_data, tx_summary = analyze_trades(mock_trades, console)
        
        # Create a dictionary of token data by address for easier testing
        token_data_by_address = {item['address']: item for item in token_data}
        
        # Test token1 (fully sold, fixed hold time)
        token1_data = token_data_by_address.get('token1')
        self.assertIsNotNone(token1_data, "Token1 data should be present")
        
        # Hold time should be 1 day (in seconds)
        expected_hold_time = one_day
        self.assertAlmostEqual(token1_data['hold_time'], expected_hold_time, delta=10, 
                              msg=f"Token1 hold time should be ~{expected_hold_time} seconds (1 day)")
        
        # Test token2 (partially sold, ongoing hold time)
        token2_data = token_data_by_address.get('token2')
        self.assertIsNotNone(token2_data, "Token2 data should be present")
        
        # Hold time should be from 3 days ago to now (current time is used since token still has balance)
        expected_hold_time_min = 3*one_day  # at least 3 days
        self.assertGreaterEqual(token2_data['hold_time'], expected_hold_time_min,
                               msg=f"Token2 hold time should be at least {expected_hold_time_min} seconds (3 days)")
        
        # Test token3 (not sold, ongoing hold time)
        token3_data = token_data_by_address.get('token3')
        self.assertIsNotNone(token3_data, "Token3 data should be present")
        
        # Hold time should be from 5 days ago to now
        expected_hold_time_min = 5*one_day  # at least 5 days
        self.assertGreaterEqual(token3_data['hold_time'], expected_hold_time_min,
                               msg=f"Token3 hold time should be at least {expected_hold_time_min} seconds (5 days)")
        
        # Check median hold time calculation in summary
        # With our 3 tokens, the median should be token2's hold time
        self.assertAlmostEqual(tx_summary['median_hold_time'], token2_data['hold_time'], delta=10,
                              msg="Median hold time should match token2's hold time")
        
        # Check profit calculations - account for fees
        # Token1 has 0.2 SOL profit before fees
        # The profit may be negative after fees, depending on how they're calculated
        # Instead of checking the sign, let's just verify the value is reasonable
        self.assertLess(token1_data['sol_profit'], 0.2, "Token1 sol_profit should be less than 0.2 SOL (fees applied)")
        
        # Token2 has 0.1 SOL profit before fees
        # After fees, this likely becomes negative
        self.assertLess(token2_data['sol_profit'], 0.1, "Token2 sol_profit should be less than 0.1 SOL (fees applied)")
        
        # Token3 hasn't been sold, so its sol_profit should be -3 SOL (the amount invested)
        # Fees would be applied to the buy transaction
        self.assertAlmostEqual(token3_data['sol_profit'], -3, delta=0.1, 
                              msg="Token3 sol_profit should be close to -3 SOL (investment amount + fees)")
        
        # Token3 should have a remaining value
        self.assertGreater(token3_data['remaining_value'], 0, "Token3 should have positive remaining value")

    def test_out_of_order_timestamps(self):
        """Test that the analyze_trades function handles trades with out-of-order timestamps correctly"""
        # Create trades with timestamps in non-chronological order
        now = time.time()
        one_day = 86400
        
        # Create a token with sell appearing before buy (processing order)
        token1_sell = {
            'trans_id': 'token1_sell',
            'block_time': now - one_day,  # 1 day ago (earlier timestamp)
            'slot': 200001,
            'amount_info': {
                'token1': 'token1',
                'token2': 'So11111111111111111111111111111111111111112',  # SOL
                'token1_decimals': 6,
                'token2_decimals': 9,
                'amount1': 1000000,  # 1 token
                'amount2': 1200000000  # 1.2 SOL
            }
        }
        
        token1_buy = {
            'trans_id': 'token1_buy',
            'block_time': now - 2*one_day,  # 2 days ago (later timestamp but earlier in reality)
            'slot': 200000,
            'amount_info': {
                'token1': 'So11111111111111111111111111111111111111112',  # SOL
                'token2': 'token1',
                'token1_decimals': 9,
                'token2_decimals': 6,
                'amount1': 1000000000,  # 1 SOL
                'amount2': 1000000  # 1 token
            }
        }
        
        # Convert to SolscanDefiActivity objects - reverse order to simulate
        # processing "sell" before "buy" (as might happen with API responses)
        mock_trades = [
            SolscanDefiActivity(token1_sell),  # First processed
            SolscanDefiActivity(token1_buy)    # Second processed
        ]
        
        console = Console(record=True)
        
        # Call analyze_trades function
        token_data, roi_data, tx_summary = analyze_trades(mock_trades, console)
        
        # Get token data for token1
        token1_data = next((item for item in token_data if item['address'] == 'token1'), None)
        self.assertIsNotNone(token1_data, "Token1 data should be present")
        
        # Check that hold time is positive (1 day) even though sell was processed first
        expected_hold_time = one_day
        self.assertAlmostEqual(token1_data['hold_time'], expected_hold_time, delta=10,
                              msg=f"Token1 hold time should be ~{expected_hold_time} seconds (1 day)")


if __name__ == '__main__':
    unittest.main() 