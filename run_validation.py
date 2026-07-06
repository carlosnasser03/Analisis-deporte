#!/usr/bin/env python
"""
Wrapper script to install dependencies and run validation
"""
import subprocess
import sys

# List of packages to install
packages = [
    'numpy',
    'opencv-python',
    'pyyaml',
    'supervision',
    'ultralytics'
]

print("=" * 70)
print("Installing required packages...")
print("=" * 70)

for package in packages:
    print(f"\n>> Installing {package}...")
    result = subprocess.run(
        [sys.executable, '-m', 'pip', 'install', package, '--no-cache-dir', '-q'],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print(f"OK {package} installed")
    else:
        print(f"WARNING {package} installation warning:")
        print(result.stderr[:200])

print("\n" + "=" * 70)
print("Running validation script...")
print("=" * 70 + "\n")

# Run the validation script
result = subprocess.run(
    [sys.executable, 'scripts/0_validate_single.py', '--skip', '1', '--max-frames', '500'],
    text=True
)

sys.exit(result.returncode)
