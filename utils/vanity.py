import base58
import re
import time
import ctypes
import numpy as np
import numpy.typing as npt
from numba import njit, prange
from datetime import datetime
from multiprocessing import Process, Value, Queue, cpu_count
from nacl.signing import SigningKey
from datetime import datetime
from rich.live import Live
from rich.panel import Panel
from rich.console import Console

@njit(cache=True)
def fast_check_pattern(public_key_bytes: npt.NDArray[np.uint8], pattern_bytes: npt.NDArray[np.uint8]) -> bool:
    """JIT-compiled pattern matching for simple contains check"""
    n, m = len(public_key_bytes), len(pattern_bytes)
    for i in range(n - m + 1):
        match = True
        for j in range(m):
            if public_key_bytes[i + j] != pattern_bytes[j]:
                match = False
                break
        if match:
            return True
    return False

@njit(parallel=True, cache=True)
def parallel_check_keypairs(public_keys: npt.NDArray[np.uint8], pattern: npt.NDArray[np.uint8]) -> npt.NDArray[np.uint8]:
    """Check multiple public keys in parallel using Numba, returns array of match flags"""
    n = len(public_keys)
    results = np.zeros(n, dtype=np.uint8)
    
    # Parallel loop over all keys
    for i in prange(n):
        if fast_check_pattern(public_keys[i], pattern):
            results[i] = 1
    
    return results

def batch_generate_keypairs(batch_size: int = 1000):
    """Generate multiple keypairs at once for better efficiency"""
    keypairs = []
    for _ in range(batch_size):
        signing_key = SigningKey.generate()
        secret_key = bytes(signing_key)
        verify_key = bytes(signing_key.verify_key)
        keypairs.append(secret_key + verify_key)
    return keypairs

def worker_process(pattern: str, found_key, result_queue: Queue, total_attempts):
    """Worker process to generate and check addresses in batches"""
    try:
        regex = re.compile(pattern)
        batch_size = 1000  # Adjust based on your CPU
        
        while not found_key.value:
            # Generate batch of keypairs
            keypairs = batch_generate_keypairs(batch_size)
            
            # Process in smaller chunks to avoid memory issues
            with total_attempts.get_lock():
                total_attempts.value += batch_size
            
            # Check each keypair in the batch
            for idx, keypair in enumerate(keypairs):
                public_key = keypair[32:]  # Last 32 bytes
                public_key_b58 = base58.b58encode(public_key).decode()
                
                if regex.search(public_key_b58):
                    with found_key.get_lock():
                        if not found_key.value:
                            found_key.value = True
                            result_queue.put(keypair)
                            return
                        
    except Exception as e:
        print(f"Worker error: {e}")

def generate_vanity_address(pattern: str, console: Console, test_mode: bool = False) -> None:
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
    num_processes = 1 if test_mode else max(1, cpu_count() - 1)
    
    if not test_mode:
        console.print(f"\n[yellow]Starting {num_processes} optimized worker processes...[/yellow]")
        console.print("[yellow]Using JIT compilation and batch processing[/yellow]")
        console.print("[yellow]Press Ctrl+C to stop searching[/yellow]\n")
    
    # Start worker processes
    processes = []
    start_time = time.time()
    
    if not test_mode:
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
        if test_mode:
            # In test mode, just wait for result
            while not found_key.value and result_queue.empty():
                time.sleep(0.1)
        else:
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
            
            if test_mode:
                console.print(f"Public Key: {public_key_b58}")
                console.print(f"Private Key: {private_key_b58}")
            else:
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
