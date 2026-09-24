#!/usr/bin/env python3
"""
Generate StatsBomb benchmarks from downloaded data.

This script:
1. Loads all downloaded StatsBomb data
2. Calculates comprehensive player statistics
3. Generates position-based benchmarks
4. Saves benchmarks to JSON for use in other modules
"""

import sys
import logging
from pathlib import Path

# Add core module to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.statsbomb_data_loader import StatsBombDataLoader, create_default_benchmarks

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Generate benchmarks from StatsBomb data."""
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "core" / "data" / "statsbomb_raw"
    output_file = project_root / "core" / "data" / "statsbomb_benchmarks.json"

    logger.info("Starting benchmark generation")

    # Check if data directory exists
    if not data_dir.exists():
        logger.warning(f"Data directory not found: {data_dir}")
        logger.info("Using default benchmarks instead")
        benchmarks = create_default_benchmarks()
    else:
        # Load and process data
        try:
            logger.info(f"Loading data from {data_dir}")
            loader = StatsBombDataLoader(str(data_dir))

            logger.info("Loading events and matches...")
            if not loader.load_data():
                logger.warning("No data loaded, using default benchmarks")
                benchmarks = create_default_benchmarks()
            else:
                logger.info(f"Calculating statistics for players...")
                loader.calculate_player_stats()

                logger.info("Generating benchmarks...")
                benchmarks = loader.calculate_benchmarks()

                if not benchmarks:
                    logger.warning("No benchmarks generated, using defaults")
                    benchmarks = create_default_benchmarks()

        except Exception as e:
            logger.error(f"Error processing data: {e}")
            logger.info("Using default benchmarks instead")
            benchmarks = create_default_benchmarks()

    # Save benchmarks
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)

        import json
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(benchmarks, f, indent=2)

        logger.info(f"Successfully saved benchmarks to {output_file}")

        # Print summary
        print("\n" + "=" * 70)
        print("BENCHMARK SUMMARY")
        print("=" * 70)

        for position, metrics in benchmarks.items():
            print(f"\n{position.upper()}:")
            for metric, stats in metrics.items():
                print(f"  {metric:20} mean={stats['mean']:>10.2f}, "
                      f"std={stats['std']:>8.2f}, n={stats['sample_size']:>5}")

        print("\n" + "=" * 70)
        return 0

    except Exception as e:
        logger.error(f"Error saving benchmarks: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
