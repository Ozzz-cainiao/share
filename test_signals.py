#!/usr/bin/env python3
"""Test signal calculation module."""

import sys

sys.path.append(".")

from investlab.allocation import signals
import pandas as pd

print("Testing signal calculation...")

# Test Chinese signal
print("\n1. Testing Chinese signal...")
try:
    cn_signal = signals.build_cn_signal_series(window=12)  # Small window for testing
    print(f"Chinese signal shape: {cn_signal.shape}")
    print(f"Sample:\n{cn_signal.head()}")
except Exception as e:
    print(f"Error with Chinese signal: {e}")

# Test US signal
print("\n2. Testing US signal...")
try:
    us_signal = signals.build_us_signal_series(window=12)
    print(f"US signal shape: {us_signal.shape}")
    print(f"Sample:\n{us_signal.head()}")
except Exception as e:
    print(f"Error with US signal: {e}")

print("\nSignal test completed.")
