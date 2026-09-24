#!/usr/bin/env python3
"""
Quick benchmark generation using default values and any available data.
This is faster than full data processing and useful for immediate use.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.statsbomb_data_loader import create_default_benchmarks

def main():
    project_root = Path(__file__).parent.parent
    output_file = project_root / "core" / "data" / "statsbomb_benchmarks.json"

    print("Generating benchmarks...")

    # Create benchmarks
    benchmarks = create_default_benchmarks()

    # Save to file
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(benchmarks, f, indent=2)

    print(f"Benchmarks saved to {output_file}")

    # Print summary
    print("\n" + "=" * 70)
    print("BENCHMARK SUMMARY (Default Values)")
    print("=" * 70)

    for position, metrics in benchmarks.items():
        print(f"\n{position.upper()}:")
        for metric, stats in metrics.items():
            print(f"  {metric:20} mean={stats['mean']:>10.2f}, "
                  f"std={stats['std']:>8.2f}")

    print("\n" + "=" * 70)
    return 0

if __name__ == "__main__":
    exit(main())
