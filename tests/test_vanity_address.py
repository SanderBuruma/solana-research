import unittest
import re
import base58
from nacl.signing import SigningKey
import sys
import os
from rich.live import Live
from rich.panel import Panel

# Add the parent directory to the path so we can import main
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import generate_vanity_address, batch_generate_keypairs, Console

class TestVanityAddress(unittest.TestCase):
    def setUp(self):
        self.console = Console()

    def test_keypair_generation(self):
        """Test that batch_generate_keypairs generates valid keypairs"""
        batch_size = 5
        keypairs = batch_generate_keypairs(batch_size)
        
        self.assertEqual(len(keypairs), batch_size)
        for keypair in keypairs:
            # Check keypair length (32 bytes private + 32 bytes public)
            self.assertEqual(len(keypair), 64)
            
            # Verify we can extract public key
            public_key = keypair[32:]
            public_key_b58 = base58.b58encode(public_key).decode()
            
            # Check that the public key is valid base58
            self.assertTrue(all(c in '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz' for c in public_key_b58))
            
            # Check public key length (should be around 32-44 chars in base58)
            self.assertTrue(32 <= len(public_key_b58) <= 44)

    def test_pattern_matching(self):
        """Test that generated addresses match the given pattern"""
        # Test with a simple pattern that should be relatively quick to find
        pattern = "a"  # Looking for any address containing 'a'
        
        # Create a mock console that captures output
        class MockConsole:
            def __init__(self):
                self.output = []
            def print(self, *args, **kwargs):
                self.output.append(str(args[0]))
            def set_live(self, *args, **kwargs):
                pass
            def clear_live(self, *args, **kwargs):
                pass
            def get_width(self):
                return 80
            def line(self):
                pass
            def is_terminal(self):
                return True
            def size(self):
                return (80, 24)
            def show_cursor(self, show):
                pass
        
        mock_console = MockConsole()
        
        # Run the generator in test mode
        generate_vanity_address(pattern, mock_console, test_mode=True)
        
        # Check if we found a matching address
        found_address = False
        for line in mock_console.output:
            if "Public Key:" in line:
                # Extract the public key and verify it matches the pattern
                public_key = line.split("Public Key:")[1].strip()
                self.assertRegex(public_key, pattern)
                found_address = True
                break
        
        self.assertTrue(found_address, "Failed to find a matching address")

    def test_invalid_pattern(self):
        """Test that invalid regex patterns are handled properly"""
        # Test with an invalid regex pattern
        pattern = "["  # Invalid regex pattern
        
        # Create a mock console that captures output
        class MockConsole:
            def __init__(self):
                self.output = []
            def print(self, *args, **kwargs):
                self.output.append(str(args[0]))
            def set_live(self, *args, **kwargs):
                pass
            def clear_live(self, *args, **kwargs):
                pass
            def get_width(self):
                return 80
            def line(self):
                pass
            def is_terminal(self):
                return True
            def size(self):
                return (80, 24)
            def show_cursor(self, show):
                pass
        
        mock_console = MockConsole()
        
        # Run the generator in test mode
        generate_vanity_address(pattern, mock_console, test_mode=True)
        
        # Check if we got an error message
        error_found = False
        for line in mock_console.output:
            if "Invalid regex pattern" in line:
                error_found = True
                break
        
        self.assertTrue(error_found, "Failed to handle invalid regex pattern")

if __name__ == '__main__':
    unittest.main() 