#!/usr/bin/env python3
"""
Run tests for the Solscan API with command line options
"""
import unittest
import os
import sys
import argparse

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    parser = argparse.ArgumentParser(description='Run Solscan API tests')
    parser.add_argument('--integration', action='store_true', 
                      help='Run integration tests that call the real API')
    parser.add_argument('--wallet', type=str, default="3jU3igB7fqix2GZuS6wGfdenLwanTJM5LMA7eEzCfkbm",
                      help='Solana wallet address to use for testing')
    args = parser.parse_args()
    
    # Set environment variables based on arguments
    if args.integration:
        os.environ['RUN_INTEGRATION_TESTS'] = 'true'
    
    if args.wallet:
        os.environ['TEST_WALLET'] = args.wallet
    
    # Import tests here so they can access updated environment variables
    from test_solscan_history import TestSolscanGetDexTradingHistory
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSolscanGetDexTradingHistory)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return non-zero exit code if tests failed
    sys.exit(not result.wasSuccessful())

if __name__ == '__main__':
    main() 