#!/usr/bin/env python3
"""
Example usage of the StatsBomb Data Loader.

This script demonstrates how to:
1. Load StatsBomb data from the local directory
2. Calculate player statistics
3. Generate performance benchmarks for positions
4. Use benchmarks for player analysis
"""

import json
from pathlib import Path
import sys

# Add core module to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.statsbomb_data_loader import StatsBombDataLoader, create_default_benchmarks


def example_basic_loading():
    """Example 1: Basic loading and statistics calculation."""
    print("=" * 70)
    print("EXAMPLE 1: Basic Loading and Statistics")
    print("=" * 70)

    # Initialize loader with downloaded data
    data_dir = Path(__file__).parent.parent / "core" / "data" / "statsbomb_raw"

    if not data_dir.exists():
        print(f"Data directory not found: {data_dir}")
        print("Please run scripts/download_statsbomb_data.py first")
        return

    loader = StatsBombDataLoader(str(data_dir))

    # Load all data
    print("\nLoading data...")
    if not loader.load_data():
        print("Failed to load data")
        return

    print(f"Loaded {len(loader.events_data)} events from {len(loader.matches_data)} matches")

    # Calculate player statistics
    print("\nCalculating player statistics...")
    player_stats = loader.calculate_player_stats()
    print(f"Calculated stats for {len(player_stats)} players")

    # Show sample player statistics
    print("\nSample player statistics (first 5 players):")
    for i, (player_id, stats) in enumerate(list(player_stats.items())[:5]):
        print(f"\n{i+1}. {stats.player_name} ({stats.position})")
        print(f"   Team: {stats.team}")
        print(f"   Matches: {stats.match_count}")
        print(f"   Distance: {stats.distance:.0f}m")
        print(f"   Max Velocity: {stats.max_velocity:.2f} m/s")
        print(f"   Sprint Count: {stats.sprint_count}")
        print(f"   Intensity Score: {stats.intensity_score:.1f}/100")


def example_benchmark_calculation():
    """Example 2: Calculate and display benchmarks."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Benchmark Calculation by Position")
    print("=" * 70)

    data_dir = Path(__file__).parent.parent / "core" / "data" / "statsbomb_raw"

    if not data_dir.exists():
        print(f"Data directory not found: {data_dir}")
        return

    loader = StatsBombDataLoader(str(data_dir))

    # Load and calculate benchmarks
    print("\nCalculating benchmarks...")
    benchmarks = loader.load_and_calculate_benchmarks()

    if not benchmarks:
        print("No benchmarks were calculated. Using default benchmarks...")
        benchmarks = create_default_benchmarks()

    # Display benchmarks by position
    for position in loader.STANDARD_POSITIONS:
        if position not in benchmarks:
            continue

        print(f"\n{position.upper()} BENCHMARKS:")
        print("-" * 70)

        metrics = benchmarks[position]
        for metric, stats in metrics.items():
            print(f"\n  {metric}:")
            print(f"    Mean:     {stats['mean']:>8.2f}")
            print(f"    Std Dev:  {stats['std']:>8.2f}")
            print(f"    Min:      {stats['min']:>8.2f}")
            print(f"    Max:      {stats['max']:>8.2f}")
            print(f"    Median:   {stats['median']:>8.2f}")
            print(f"    N:        {stats['sample_size']:>8}")


def example_player_analysis():
    """Example 3: Analyze a specific player against benchmarks."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Individual Player Analysis")
    print("=" * 70)

    data_dir = Path(__file__).parent.parent / "core" / "data" / "statsbomb_raw"

    if not data_dir.exists():
        print(f"Data directory not found: {data_dir}")
        return

    loader = StatsBombDataLoader(str(data_dir))
    loader.load_data()
    player_stats_dict = loader.calculate_player_stats()
    benchmarks = loader.calculate_benchmarks()

    if not player_stats_dict:
        print("No player statistics available")
        return

    if not benchmarks:
        benchmarks = create_default_benchmarks()

    # Analyze first midfielder
    midfielders = [p for p in player_stats_dict.values() if p.position == 'midfielder']
    if not midfielders:
        print("No midfielders found in data")
        return

    player = midfielders[0]
    print(f"\nAnalyzing: {player.player_name}")
    print(f"Position: {player.position}")
    print(f"Team: {player.team}")
    print(f"Matches played: {player.match_count}")

    print(f"\nCOMPARISON TO {player.position.upper()} BENCHMARKS:")
    print("-" * 70)

    position_benchmarks = benchmarks.get(player.position, {})

    # Distance comparison
    if 'distance' in position_benchmarks:
        dist_bench = position_benchmarks['distance']
        percentile = (player.distance - dist_bench['min']) / (dist_bench['max'] - dist_bench['min']) * 100
        print(f"\nDistance Covered: {player.distance:.0f}m")
        print(f"  Benchmark mean: {dist_bench['mean']:.0f}m")
        print(f"  Percentile: {percentile:.1f}%")
        if player.distance > dist_bench['mean']:
            print(f"  Status: ABOVE AVERAGE (+{player.distance - dist_bench['mean']:.0f}m)")
        else:
            print(f"  Status: BELOW AVERAGE ({player.distance - dist_bench['mean']:.0f}m)")

    # Velocity comparison
    if 'max_velocity' in position_benchmarks:
        vel_bench = position_benchmarks['max_velocity']
        print(f"\nMax Velocity: {player.max_velocity:.2f} m/s")
        print(f"  Benchmark mean: {vel_bench['mean']:.2f} m/s")
        if player.max_velocity > vel_bench['mean']:
            print(f"  Status: ABOVE AVERAGE (+{player.max_velocity - vel_bench['mean']:.2f} m/s)")
        else:
            print(f"  Status: BELOW AVERAGE ({player.max_velocity - vel_bench['mean']:.2f} m/s)")

    # Sprint count comparison
    if 'sprint_count' in position_benchmarks:
        sprint_bench = position_benchmarks['sprint_count']
        print(f"\nSprint Count: {player.sprint_count}")
        print(f"  Benchmark mean: {sprint_bench['mean']:.1f}")
        if player.sprint_count > sprint_bench['mean']:
            print(f"  Status: ABOVE AVERAGE")
        else:
            print(f"  Status: BELOW AVERAGE")

    # Intensity comparison
    if 'intensity_score' in position_benchmarks:
        intensity_bench = position_benchmarks['intensity_score']
        print(f"\nIntensity Score: {player.intensity_score:.1f}/100")
        print(f"  Benchmark mean: {intensity_bench['mean']:.1f}/100")
        if player.intensity_score > intensity_bench['mean']:
            print(f"  Status: ABOVE AVERAGE")
        else:
            print(f"  Status: BELOW AVERAGE")


def example_save_benchmarks():
    """Example 4: Save benchmarks to file for use in other modules."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Saving Benchmarks")
    print("=" * 70)

    data_dir = Path(__file__).parent.parent / "core" / "data" / "statsbomb_raw"
    output_dir = Path(__file__).parent.parent / "core" / "data"

    if not data_dir.exists():
        print(f"Data directory not found: {data_dir}")
        print("Using default benchmarks instead...")
        benchmarks = create_default_benchmarks()
    else:
        loader = StatsBombDataLoader(str(data_dir))
        benchmarks = loader.load_and_calculate_benchmarks()

    # Save benchmarks
    output_file = output_dir / "statsbomb_benchmarks.json"
    print(f"\nSaving benchmarks to {output_file}")

    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(benchmarks, f, indent=2)

    print(f"Successfully saved benchmarks")

    # Load and verify
    with open(output_file, 'r') as f:
        loaded = json.load(f)

    print(f"Verified: {len(loaded)} positions in saved file")
    for pos in loaded.keys():
        print(f"  - {pos}")


def example_batch_player_analysis():
    """Example 5: Batch analysis of all players by position."""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Batch Player Analysis")
    print("=" * 70)

    data_dir = Path(__file__).parent.parent / "core" / "data" / "statsbomb_raw"

    if not data_dir.exists():
        print(f"Data directory not found: {data_dir}")
        return

    loader = StatsBombDataLoader(str(data_dir))
    loader.load_data()
    player_stats_dict = loader.calculate_player_stats()

    # Group by position and team
    from collections import defaultdict
    position_teams = defaultdict(lambda: defaultdict(list))

    for player in player_stats_dict.values():
        position_teams[player.position][player.team].append(player)

    # Show summary by position and team
    for position in loader.STANDARD_POSITIONS:
        if position not in position_teams:
            continue

        print(f"\n{position.upper()}:")
        for team, players in sorted(position_teams[position].items()):
            if players:
                avg_distance = sum(p.distance for p in players) / len(players)
                avg_velocity = sum(p.max_velocity for p in players) / len(players)
                print(f"  {team}: {len(players)} players")
                print(f"    Avg Distance: {avg_distance:.0f}m")
                print(f"    Avg Velocity: {avg_velocity:.2f} m/s")


def main():
    """Run all examples."""
    try:
        example_basic_loading()
        example_benchmark_calculation()
        example_player_analysis()
        example_save_benchmarks()
        example_batch_player_analysis()

        print("\n" + "=" * 70)
        print("All examples completed successfully!")
        print("=" * 70)

    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
