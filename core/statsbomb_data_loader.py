"""
StatsBomb Data Loader and Benchmark Calculator.

This module loads StatsBomb open data and calculates performance benchmarks
for players by position. It provides reference statistics for distance covered,
velocity, sprint counts, and intensity metrics.

Usage:
    loader = StatsBombDataLoader('path/to/data')
    benchmarks = loader.load_and_calculate_benchmarks()
    loader.save_benchmarks('path/to/output.json')
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from collections import defaultdict
import statistics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class PlayerStats:
    """Container for individual player statistics."""
    player_id: int
    player_name: str
    position: str
    distance: float  # in meters
    max_velocity: float  # in m/s (estimated)
    sprint_count: int  # passes/actions at high intensity
    intensity_score: float  # 0-100, based on action frequency
    match_count: int
    team: str


@dataclass
class PositionBenchmark:
    """Statistical benchmark for a position."""
    position: str
    stat_name: str
    mean: float
    std: float
    min: float
    max: float
    median: float
    sample_size: int


class StatsBombDataLoader:
    """Load and process StatsBomb open data."""

    # Position mapping from StatsBomb to standard positions
    POSITION_MAPPING = {
        # Goalkeeper
        'Goalkeeper': 'goalkeeper',

        # Defenders
        'Right Back': 'defender',
        'Left Back': 'defender',
        'Center Back': 'defender',
        'Right Fullback': 'defender',
        'Left Fullback': 'defender',
        'Right Wing Back': 'defender',
        'Left Wing Back': 'defender',

        # Midfielders
        'Right Midfield': 'midfielder',
        'Left Midfield': 'midfielder',
        'Right Wing': 'midfielder',
        'Left Wing': 'midfielder',
        'Center Midfield': 'midfielder',
        'Defensive Midfield': 'midfielder',
        'Attacking Midfield': 'midfielder',
        'Right Wing Midfield': 'midfielder',
        'Left Wing Midfield': 'midfielder',

        # Forwards
        'Striker': 'forward',
        'Right Center Forward': 'forward',
        'Left Center Forward': 'forward',
        'Right Winger': 'forward',
        'Left Winger': 'forward',
        'Center Forward': 'forward',
        'Attacking Midfielder': 'midfielder',  # Can be midfield
    }

    # Standard position names
    STANDARD_POSITIONS = ['goalkeeper', 'defender', 'midfielder', 'forward']

    def __init__(self, data_dir: str):
        """
        Initialize the loader.

        Args:
            data_dir: Path to directory containing StatsBomb JSON files
        """
        self.data_dir = Path(data_dir)
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {data_dir}")

        self.players_stats: Dict[int, PlayerStats] = {}
        self.events_data: List[Dict[str, Any]] = []
        self.matches_data: List[Dict[str, Any]] = []

    def load_data(self) -> bool:
        """
        Load all StatsBomb data files.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Load competitions list
            comp_file = self.data_dir / "competitions.json"
            if comp_file.exists():
                with open(comp_file, 'r', encoding='utf-8') as f:
                    competitions = json.load(f)
                logger.info(f"Loaded {len(competitions)} competitions")

            # Load matches files
            for matches_file in self.data_dir.glob("matches_*.json"):
                try:
                    with open(matches_file, 'r', encoding='utf-8') as f:
                        matches = json.load(f)
                        self.matches_data.extend(matches)
                        logger.info(f"Loaded {len(matches)} matches from {matches_file.name}")
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"Error loading {matches_file.name}: {e}")

            # Load events files
            for events_file in self.data_dir.glob("events_*.json"):
                try:
                    with open(events_file, 'r', encoding='utf-8') as f:
                        events = json.load(f)
                        self.events_data.extend(events)
                        logger.info(f"Loaded {len(events)} events from {events_file.name}")
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"Error loading {events_file.name}: {e}")

            # Load individual match events from subdirectories
            for match_subdir in self.data_dir.glob("*/"):
                if match_subdir.is_dir() and match_subdir.name != "__pycache__":
                    for match_file in match_subdir.glob("match_*.json"):
                        try:
                            with open(match_file, 'r', encoding='utf-8') as f:
                                events = json.load(f)
                                # Only add if not already loaded
                                if not any(e.get('match_id') == int(match_file.stem.split('_')[1])
                                          for e in self.events_data):
                                    self.events_data.extend(events)
                        except (json.JSONDecodeError, IOError, ValueError):
                            pass

            logger.info(f"Total loaded: {len(self.matches_data)} matches, "
                       f"{len(self.events_data)} events")
            return len(self.events_data) > 0

        except Exception as e:
            logger.error(f"Error loading data: {e}")
            return False

    def calculate_player_stats(self) -> Dict[int, PlayerStats]:
        """
        Calculate statistics for each player from events data.

        Returns:
            Dictionary mapping player IDs to PlayerStats objects
        """
        if not self.events_data:
            logger.error("No events data loaded. Call load_data() first.")
            return {}

        player_data: Dict[int, Dict[str, Any]] = defaultdict(lambda: {
            'name': 'Unknown',
            'position': 'unknown',
            'team': 'Unknown',
            'distance': 0.0,
            'max_velocity': 0.0,
            'sprint_count': 0,
            'action_count': 0,
            'high_intensity_actions': 0,
            'matches': set(),
        })

        logger.info("Calculating player statistics...")

        for event in self.events_data:
            # Extract player info
            player = event.get('player', {})
            if not player:
                continue

            player_id = player.get('id')
            if not player_id:
                continue

            player_name = player.get('name', 'Unknown')
            player_data[player_id]['name'] = player_name

            # Get position
            position_data = event.get('position', {})
            if position_data:
                position_name = position_data.get('name', 'Unknown')
                mapped_position = self.POSITION_MAPPING.get(position_name, 'unknown')
                if mapped_position != 'unknown':
                    player_data[player_id]['position'] = mapped_position

            # Get team
            team = event.get('team', {})
            if team:
                player_data[player_id]['team'] = team.get('name', 'Unknown')

            # Track matches
            match_id = event.get('match_id')
            if match_id:
                player_data[player_id]['matches'].add(match_id)

            # Extract event-specific metrics
            event_type = event.get('type', {}).get('name', '')

            # Count high-intensity actions
            if event_type in ['Pass', 'Shot', 'Duel', 'Foul Committed', 'Tackle']:
                player_data[player_id]['action_count'] += 1
                player_data[player_id]['high_intensity_actions'] += 1

            # Extract distance and velocity
            location = event.get('location', [])
            end_location = event.get('end_location', [])

            if location and end_location:
                try:
                    distance = self._calculate_distance(location, end_location)
                    player_data[player_id]['distance'] += distance
                    # Estimate velocity (distance in m, assume ~0.5s per action)
                    velocity = distance / 0.5
                    player_data[player_id]['max_velocity'] = max(
                        player_data[player_id]['max_velocity'],
                        velocity
                    )
                except (ValueError, IndexError):
                    pass

            # Count sprints (high-distance actions)
            if event_type in ['Pass', 'Duel', 'Shot'] and end_location:
                try:
                    distance = self._calculate_distance(location, end_location)
                    if distance > 5:  # 5+ meters is a "sprint"
                        player_data[player_id]['sprint_count'] += 1
                except (ValueError, IndexError):
                    pass

        # Convert to PlayerStats objects
        for player_id, stats in player_data.items():
            if stats['position'] != 'unknown' and stats['action_count'] > 10:
                # Normalize velocity (divide by estimated number of actions)
                if stats['action_count'] > 0:
                    normalized_velocity = stats['max_velocity'] / (stats['action_count'] ** 0.5)
                    stats['max_velocity'] = min(normalized_velocity, 12.0)  # Cap at 12 m/s

                # Calculate intensity score (0-100)
                intensity_score = min(100, (stats['high_intensity_actions'] / max(1, stats['action_count'])) * 100)

                self.players_stats[player_id] = PlayerStats(
                    player_id=player_id,
                    player_name=stats['name'],
                    position=stats['position'],
                    distance=stats['distance'],
                    max_velocity=stats['max_velocity'],
                    sprint_count=stats['sprint_count'],
                    intensity_score=intensity_score,
                    match_count=len(stats['matches']),
                    team=stats['team'],
                )

        logger.info(f"Calculated stats for {len(self.players_stats)} players")
        return self.players_stats

    def calculate_benchmarks(self) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        Calculate statistical benchmarks for each position.

        Returns:
            Dictionary of benchmarks by position and metric
        """
        if not self.players_stats:
            logger.error("No player stats available. Call calculate_player_stats() first.")
            return {}

        benchmarks: Dict[str, Dict[str, Dict[str, float]]] = {}
        position_data: Dict[str, Dict[str, List[float]]] = defaultdict(
            lambda: defaultdict(list)
        )

        # Group players by position and metric
        for player in self.players_stats.values():
            if player.match_count < 3:  # Only include players with 3+ matches
                continue

            pos = player.position
            position_data[pos]['distance'].append(player.distance)
            position_data[pos]['max_velocity'].append(player.max_velocity)
            position_data[pos]['sprint_count'].append(player.sprint_count)
            position_data[pos]['intensity_score'].append(player.intensity_score)

        # Calculate statistics
        for position in self.STANDARD_POSITIONS:
            if position not in position_data:
                logger.warning(f"No data for position: {position}")
                continue

            benchmarks[position] = {}
            pos_data = position_data[position]

            for metric, values in pos_data.items():
                if not values:
                    continue

                values_sorted = sorted(values)
                mean_val = statistics.mean(values)
                stdev = statistics.stdev(values) if len(values) > 1 else 0
                median_val = statistics.median(values)

                benchmarks[position][metric] = {
                    'mean': round(mean_val, 2),
                    'std': round(stdev, 2),
                    'min': round(min(values), 2),
                    'max': round(max(values), 2),
                    'median': round(median_val, 2),
                    'sample_size': len(values),
                }

                logger.info(
                    f"{position:12} {metric:20} - "
                    f"mean: {mean_val:8.2f}, std: {stdev:6.2f}, "
                    f"n: {len(values)}"
                )

        return benchmarks

    def load_and_calculate_benchmarks(self) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        Load data and calculate benchmarks in one step.

        Returns:
            Dictionary of benchmarks
        """
        if not self.load_data():
            logger.error("Failed to load data")
            return {}

        self.calculate_player_stats()
        benchmarks = self.calculate_benchmarks()

        if benchmarks:
            logger.info("Successfully calculated benchmarks")
        else:
            logger.warning("No benchmarks were calculated")

        return benchmarks

    def save_benchmarks(self, output_file: str) -> bool:
        """
        Save benchmarks to JSON file.

        Args:
            output_file: Path to output JSON file

        Returns:
            True if successful, False otherwise
        """
        try:
            benchmarks = self.calculate_benchmarks()
            if not benchmarks:
                logger.error("No benchmarks to save")
                return False

            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(benchmarks, f, indent=2)

            logger.info(f"Saved benchmarks to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Error saving benchmarks: {e}")
            return False

    def get_player_benchmarks(self, position: str, metric: str) -> Optional[Dict[str, float]]:
        """
        Get benchmark for a specific position and metric.

        Args:
            position: Player position (goalkeeper, defender, midfielder, forward)
            metric: Metric name (distance, max_velocity, sprint_count, intensity_score)

        Returns:
            Dictionary with benchmark statistics or None if not found
        """
        benchmarks = self.calculate_benchmarks()

        if position in benchmarks and metric in benchmarks[position]:
            return benchmarks[position][metric]

        return None

    def export_player_stats(self, output_file: str) -> bool:
        """
        Export all player statistics to JSON file.

        Args:
            output_file: Path to output JSON file

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.players_stats:
                logger.error("No player stats available")
                return False

            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            stats_dict = {
                str(player_id): asdict(stats)
                for player_id, stats in self.players_stats.items()
            }

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(stats_dict, f, indent=2)

            logger.info(f"Exported {len(stats_dict)} player stats to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Error exporting stats: {e}")
            return False

    @staticmethod
    def _calculate_distance(loc1: List[float], loc2: List[float]) -> float:
        """Calculate Euclidean distance between two points (in meters)."""
        if len(loc1) < 2 or len(loc2) < 2:
            return 0.0

        dx = loc2[0] - loc1[0]
        dy = loc2[1] - loc1[1]
        return (dx**2 + dy**2) ** 0.5


def create_default_benchmarks() -> Dict[str, Dict[str, Dict[str, float]]]:
    """
    Create default/fallback benchmarks if no data is available.

    These are realistic estimates based on football analytics literature.

    Returns:
        Dictionary of default benchmarks
    """
    return {
        'goalkeeper': {
            'distance': {
                'mean': 4200.0,
                'std': 600.0,
                'min': 2800.0,
                'max': 6500.0,
                'median': 4150.0,
                'sample_size': 0,
            },
            'max_velocity': {
                'mean': 6.5,
                'std': 1.2,
                'min': 4.0,
                'max': 9.5,
                'median': 6.3,
                'sample_size': 0,
            },
            'sprint_count': {
                'mean': 2.0,
                'std': 1.5,
                'min': 0.0,
                'max': 8.0,
                'median': 1.5,
                'sample_size': 0,
            },
            'intensity_score': {
                'mean': 35.0,
                'std': 12.0,
                'min': 15.0,
                'max': 70.0,
                'median': 34.0,
                'sample_size': 0,
            },
        },
        'defender': {
            'distance': {
                'mean': 9800.0,
                'std': 1200.0,
                'min': 7000.0,
                'max': 13500.0,
                'median': 9750.0,
                'sample_size': 0,
            },
            'max_velocity': {
                'mean': 8.2,
                'std': 0.9,
                'min': 6.0,
                'max': 10.5,
                'median': 8.1,
                'sample_size': 0,
            },
            'sprint_count': {
                'mean': 8.5,
                'std': 2.8,
                'min': 2.0,
                'max': 18.0,
                'median': 8.0,
                'sample_size': 0,
            },
            'intensity_score': {
                'mean': 62.0,
                'std': 10.0,
                'min': 35.0,
                'max': 85.0,
                'median': 62.0,
                'sample_size': 0,
            },
        },
        'midfielder': {
            'distance': {
                'mean': 10800.0,
                'std': 1400.0,
                'min': 7500.0,
                'max': 14500.0,
                'median': 10850.0,
                'sample_size': 0,
            },
            'max_velocity': {
                'mean': 8.8,
                'std': 1.0,
                'min': 6.5,
                'max': 11.5,
                'median': 8.8,
                'sample_size': 0,
            },
            'sprint_count': {
                'mean': 10.2,
                'std': 3.2,
                'min': 3.0,
                'max': 22.0,
                'median': 10.0,
                'sample_size': 0,
            },
            'intensity_score': {
                'mean': 68.0,
                'std': 9.5,
                'min': 40.0,
                'max': 90.0,
                'median': 68.0,
                'sample_size': 0,
            },
        },
        'forward': {
            'distance': {
                'mean': 9500.0,
                'std': 1600.0,
                'min': 5500.0,
                'max': 13500.0,
                'median': 9600.0,
                'sample_size': 0,
            },
            'max_velocity': {
                'mean': 9.2,
                'std': 1.1,
                'min': 7.0,
                'max': 12.0,
                'median': 9.2,
                'sample_size': 0,
            },
            'sprint_count': {
                'mean': 9.8,
                'std': 3.5,
                'min': 2.0,
                'max': 20.0,
                'median': 9.5,
                'sample_size': 0,
            },
            'intensity_score': {
                'mean': 71.0,
                'std': 11.0,
                'min': 38.0,
                'max': 92.0,
                'median': 71.0,
                'sample_size': 0,
            },
        },
    }
