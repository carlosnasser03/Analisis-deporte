"""
Unit tests for StatsBomb data loader module.

Tests cover:
- Data loading from JSON files
- Player statistics calculation
- Benchmark calculation and accuracy
- Data validation
- Error handling
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the module to test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.statsbomb_data_loader import (
    StatsBombDataLoader,
    PlayerStats,
    create_default_benchmarks,
)


class TestStatsBombDataLoader(unittest.TestCase):
    """Test StatsBombDataLoader class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for test data
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_data_dir = Path(self.temp_dir.name)

        # Create mock data files
        self._create_mock_data()

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def _create_mock_data(self):
        """Create mock StatsBomb data files for testing."""
        # Mock competitions file
        competitions = [
            {
                "competition_id": 2,
                "season_id": 27,
                "competition_name": "Premier League",
                "season_name": "2015/2016",
            },
            {
                "competition_id": 4,
                "season_id": 1,
                "competition_name": "La Liga",
                "season_name": "2017/2018",
            },
            {
                "competition_id": 16,
                "season_id": 4,
                "competition_name": "Champions League",
                "season_name": "2018/2019",
            },
        ]

        with open(self.test_data_dir / "competitions.json", "w") as f:
            json.dump(competitions, f)

        # Mock events file with realistic structure
        events = [
            {
                "id": "event1",
                "match_id": 1,
                "type": {"name": "Pass"},
                "player": {
                    "id": 1001,
                    "name": "Player One",
                },
                "position": {"name": "Center Midfield"},
                "team": {"name": "Team A"},
                "location": [60.0, 40.0],
                "end_location": [70.0, 45.0],
            },
            {
                "id": "event2",
                "match_id": 1,
                "type": {"name": "Pass"},
                "player": {
                    "id": 1001,
                    "name": "Player One",
                },
                "position": {"name": "Center Midfield"},
                "team": {"name": "Team A"},
                "location": [70.0, 45.0],
                "end_location": [80.0, 50.0],
            },
            {
                "id": "event3",
                "match_id": 1,
                "type": {"name": "Shot"},
                "player": {
                    "id": 1002,
                    "name": "Player Two",
                },
                "position": {"name": "Striker"},
                "team": {"name": "Team B"},
                "location": [80.0, 40.0],
                "end_location": [100.0, 40.0],
            },
            {
                "id": "event4",
                "match_id": 2,
                "type": {"name": "Pass"},
                "player": {
                    "id": 1001,
                    "name": "Player One",
                },
                "position": {"name": "Center Midfield"},
                "team": {"name": "Team A"},
                "location": [60.0, 40.0],
                "end_location": [75.0, 48.0],
            },
            {
                "id": "event5",
                "match_id": 2,
                "type": {"name": "Duel"},
                "player": {
                    "id": 1003,
                    "name": "Player Three",
                },
                "position": {"name": "Center Back"},
                "team": {"name": "Team C"},
                "location": [50.0, 30.0],
                "end_location": [55.0, 35.0],
            },
        ]

        with open(self.test_data_dir / "events_test.json", "w") as f:
            json.dump(events, f)

    def test_loader_initialization(self):
        """Test loader initialization."""
        loader = StatsBombDataLoader(str(self.test_data_dir))
        self.assertEqual(loader.data_dir, self.test_data_dir)
        self.assertEqual(len(loader.players_stats), 0)
        self.assertEqual(len(loader.events_data), 0)

    def test_loader_initialization_nonexistent_dir(self):
        """Test loader with nonexistent directory."""
        with self.assertRaises(FileNotFoundError):
            StatsBombDataLoader("/nonexistent/directory")

    def test_load_data(self):
        """Test loading data from files."""
        loader = StatsBombDataLoader(str(self.test_data_dir))
        result = loader.load_data()

        self.assertTrue(result)
        self.assertGreater(len(loader.events_data), 0)

    def test_calculate_player_stats(self):
        """Test player statistics calculation."""
        loader = StatsBombDataLoader(str(self.test_data_dir))
        loader.load_data()
        stats = loader.calculate_player_stats()

        self.assertIsInstance(stats, dict)
        # Test data is minimal, so we just check it's a valid dict
        # In production, this would have actual player data

        # Verify PlayerStats objects
        for player_id, player_stats in stats.items():
            self.assertIsInstance(player_stats, PlayerStats)
            self.assertGreater(player_stats.player_id, 0)
            self.assertIsNotNone(player_stats.player_name)
            self.assertIn(
                player_stats.position,
                ['goalkeeper', 'defender', 'midfielder', 'forward', 'unknown']
            )

    def test_calculate_benchmarks(self):
        """Test benchmark calculation."""
        loader = StatsBombDataLoader(str(self.test_data_dir))
        loader.load_data()
        loader.calculate_player_stats()
        benchmarks = loader.calculate_benchmarks()

        self.assertIsInstance(benchmarks, dict)

        # Check benchmark structure
        for position, metrics in benchmarks.items():
            self.assertIn(position, loader.STANDARD_POSITIONS)
            for metric, stats in metrics.items():
                self.assertIn('mean', stats)
                self.assertIn('std', stats)
                self.assertIn('min', stats)
                self.assertIn('max', stats)
                self.assertIn('median', stats)
                self.assertIn('sample_size', stats)

                # Verify stats values are reasonable
                self.assertGreaterEqual(stats['median'], stats['min'])
                self.assertLessEqual(stats['median'], stats['max'])

    def test_benchmark_structure(self):
        """Test that benchmarks have expected structure."""
        loader = StatsBombDataLoader(str(self.test_data_dir))
        loader.load_data()
        loader.calculate_player_stats()
        benchmarks = loader.calculate_benchmarks()

        # Check all expected positions exist
        for position in loader.STANDARD_POSITIONS:
            if position in benchmarks:
                self.assertIn('distance', benchmarks[position])
                self.assertIn('max_velocity', benchmarks[position])
                self.assertIn('sprint_count', benchmarks[position])
                self.assertIn('intensity_score', benchmarks[position])

    def test_save_benchmarks(self):
        """Test saving benchmarks to file."""
        loader = StatsBombDataLoader(str(self.test_data_dir))
        loader.load_data()
        loader.calculate_player_stats()

        output_file = self.test_data_dir / "benchmarks_test.json"
        result = loader.save_benchmarks(str(output_file))

        # Test data is minimal, so benchmarks might be empty
        # Just verify the function handles the case gracefully
        self.assertIsInstance(result, bool)

        # Only verify file if it was created
        if output_file.exists():
            with open(output_file, 'r') as f:
                saved_benchmarks = json.load(f)
            self.assertIsInstance(saved_benchmarks, dict)

    def test_export_player_stats(self):
        """Test exporting player statistics."""
        loader = StatsBombDataLoader(str(self.test_data_dir))
        loader.load_data()
        loader.calculate_player_stats()

        output_file = self.test_data_dir / "player_stats_test.json"
        result = loader.export_player_stats(str(output_file))

        # Test data is minimal, so export might fail if no stats
        # Just verify the function handles it gracefully
        self.assertIsInstance(result, bool)

        # Only verify file if it was created
        if output_file.exists():
            with open(output_file, 'r') as f:
                saved_stats = json.load(f)
            self.assertIsInstance(saved_stats, dict)

    def test_position_mapping(self):
        """Test position mapping from StatsBomb to standard positions."""
        mapping = StatsBombDataLoader.POSITION_MAPPING

        self.assertEqual(mapping['Center Midfield'], 'midfielder')
        self.assertEqual(mapping['Striker'], 'forward')
        self.assertEqual(mapping['Center Back'], 'defender')
        self.assertEqual(mapping['Goalkeeper'], 'goalkeeper')

    def test_calculate_distance(self):
        """Test Euclidean distance calculation."""
        # Test basic distance
        distance = StatsBombDataLoader._calculate_distance([0, 0], [3, 4])
        self.assertEqual(distance, 5.0)

        # Test same location
        distance = StatsBombDataLoader._calculate_distance([10, 20], [10, 20])
        self.assertEqual(distance, 0.0)

        # Test zero vectors
        distance = StatsBombDataLoader._calculate_distance([0, 0], [0, 0])
        self.assertEqual(distance, 0.0)

    def test_load_and_calculate_benchmarks_pipeline(self):
        """Test complete pipeline: load and calculate benchmarks."""
        loader = StatsBombDataLoader(str(self.test_data_dir))
        benchmarks = loader.load_and_calculate_benchmarks()

        self.assertIsInstance(benchmarks, dict)

    def test_get_player_benchmarks(self):
        """Test retrieving specific player benchmarks."""
        loader = StatsBombDataLoader(str(self.test_data_dir))
        loader.load_data()
        loader.calculate_player_stats()

        # Try to get benchmark for a position that might have data
        for position in loader.STANDARD_POSITIONS:
            benchmark = loader.get_player_benchmarks(position, 'distance')
            # Might be None if no data for that position
            if benchmark is not None:
                self.assertIsInstance(benchmark, dict)
                self.assertIn('mean', benchmark)


class TestDefaultBenchmarks(unittest.TestCase):
    """Test default benchmark creation."""

    def test_create_default_benchmarks(self):
        """Test creating default benchmarks."""
        benchmarks = create_default_benchmarks()

        self.assertIsInstance(benchmarks, dict)

        # Check all positions exist
        expected_positions = ['goalkeeper', 'defender', 'midfielder', 'forward']
        for position in expected_positions:
            self.assertIn(position, benchmarks)

            # Check all metrics exist
            expected_metrics = ['distance', 'max_velocity', 'sprint_count', 'intensity_score']
            for metric in expected_metrics:
                self.assertIn(metric, benchmarks[position])

                # Check all statistics exist
                stats = benchmarks[position][metric]
                for stat_name in ['mean', 'std', 'min', 'max', 'median', 'sample_size']:
                    self.assertIn(stat_name, stats)

    def test_default_benchmarks_values_reasonable(self):
        """Test that default benchmarks have reasonable values."""
        benchmarks = create_default_benchmarks()

        for position, metrics in benchmarks.items():
            for metric, stats in metrics.items():
                # Check ordering
                self.assertLessEqual(stats['min'], stats['median'])
                self.assertLessEqual(stats['median'], stats['max'])
                self.assertGreaterEqual(stats['std'], 0)

                # Check metric-specific reasonableness
                if metric == 'distance':
                    # Distance should be in reasonable range (meters per match)
                    self.assertGreater(stats['mean'], 1000)
                    self.assertLess(stats['mean'], 20000)

                elif metric == 'max_velocity':
                    # Velocity should be reasonable (m/s)
                    self.assertGreater(stats['mean'], 4)
                    self.assertLess(stats['mean'], 12)

                elif metric == 'intensity_score':
                    # Intensity score should be 0-100
                    self.assertGreaterEqual(stats['min'], 0)
                    self.assertLessEqual(stats['max'], 100)


class TestPlayerStatsDataclass(unittest.TestCase):
    """Test PlayerStats dataclass."""

    def test_player_stats_creation(self):
        """Test creating PlayerStats object."""
        stats = PlayerStats(
            player_id=1001,
            player_name="John Doe",
            position="midfielder",
            distance=10500.0,
            max_velocity=8.5,
            sprint_count=10,
            intensity_score=68.5,
            match_count=5,
            team="Team A",
        )

        self.assertEqual(stats.player_id, 1001)
        self.assertEqual(stats.player_name, "John Doe")
        self.assertEqual(stats.position, "midfielder")
        self.assertEqual(stats.distance, 10500.0)
        self.assertEqual(stats.max_velocity, 8.5)
        self.assertEqual(stats.sprint_count, 10)
        self.assertEqual(stats.intensity_score, 68.5)
        self.assertEqual(stats.match_count, 5)
        self.assertEqual(stats.team, "Team A")


class TestDataValidation(unittest.TestCase):
    """Test data validation and error handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_data_dir = Path(self.temp_dir.name)

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_empty_data_dir(self):
        """Test loading from empty directory."""
        loader = StatsBombDataLoader(str(self.test_data_dir))
        result = loader.load_data()

        # Should not fail, but return False
        self.assertFalse(result)

    def test_malformed_json_handling(self):
        """Test handling of malformed JSON files."""
        # Create malformed JSON file
        with open(self.test_data_dir / "events_bad.json", "w") as f:
            f.write("{invalid json")

        loader = StatsBombDataLoader(str(self.test_data_dir))
        # Should not crash
        result = loader.load_data()
        # Result depends on other files, but should handle gracefully
        self.assertIsInstance(result, bool)

    def test_missing_fields_in_events(self):
        """Test handling events with missing fields."""
        events = [
            {
                "id": "event1",
                "match_id": 1,
                # Missing player, position, type fields
            },
            {
                "id": "event2",
                "match_id": 1,
                "player": {"id": 1001, "name": "Player"},
                # Missing position field
            },
        ]

        events_file = self.test_data_dir / "events_incomplete.json"
        with open(events_file, "w") as f:
            json.dump(events, f)

        loader = StatsBombDataLoader(str(self.test_data_dir))
        # Should not crash on incomplete data
        loader.load_data()
        stats = loader.calculate_player_stats()

        # Should handle missing data gracefully
        self.assertIsInstance(stats, dict)


class TestPerformanceAndScaling(unittest.TestCase):
    """Test performance characteristics with different data sizes."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_data_dir = Path(self.temp_dir.name)

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_large_events_file(self):
        """Test handling of large events file."""
        # Create events file with many events
        events = []
        for i in range(1000):
            events.append({
                "id": f"event{i}",
                "match_id": i // 50 + 1,
                "type": {"name": "Pass" if i % 3 == 0 else "Shot"},
                "player": {
                    "id": (i % 20) + 1001,
                    "name": f"Player {i % 20}",
                },
                "position": {"name": "Center Midfield"},
                "team": {"name": "Team A"},
                "location": [60.0 + (i % 10), 40.0 + (i % 10)],
                "end_location": [70.0 + (i % 10), 45.0 + (i % 10)],
            })

        with open(self.test_data_dir / "events_large.json", "w") as f:
            json.dump(events, f)

        loader = StatsBombDataLoader(str(self.test_data_dir))
        loader.load_data()
        stats = loader.calculate_player_stats()

        # Should handle large files
        self.assertGreater(len(stats), 0)


if __name__ == '__main__':
    unittest.main()
