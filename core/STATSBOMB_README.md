# StatsBomb Data Loader Module

## Overview

The StatsBomb Data Loader is a comprehensive module for loading, processing, and analyzing StatsBomb open data. It calculates performance benchmarks for football players by position, enabling comparative analysis against expected performance standards.

## Features

- **Data Loading**: Seamlessly loads StatsBomb JSON data (competitions, matches, events)
- **Player Statistics**: Calculates comprehensive player metrics including:
  - Distance covered per match (in meters)
  - Maximum velocity (in m/s)
  - Sprint count (high-intensity movements)
  - Intensity score (0-100 scale)
- **Position-based Benchmarks**: Generates statistical benchmarks for 4 player positions:
  - Goalkeeper
  - Defender
  - Midfielder
  - Forward
- **Statistical Analysis**: Provides mean, standard deviation, min, max, and median for each metric
- **Error Handling**: Robust handling of missing/malformed data
- **Export Capabilities**: Save benchmarks and player stats to JSON

## Installation

### Prerequisites

- Python 3.7+
- `requests` library (for data downloading)
- Standard library only for core functionality

### Setup

```bash
# No additional dependencies needed for core module
# Optional: Install requests for downloading data
pip install requests
```

## Quick Start

### 1. Download StatsBomb Data

```bash
python scripts/download_statsbomb_data.py
```

This downloads data from 3 competitions:
- Premier League (380 matches, 2015/2016 season)
- La Liga (38 matches, 2017/2018 season)
- Champions League (17 matches from multiple seasons)

### 2. Generate Benchmarks

```bash
python scripts/generate_statsbomb_benchmarks.py
```

This processes all downloaded data and generates `statsbomb_benchmarks.json` with position-based benchmarks.

### 3. Use in Code

```python
from core.statsbomb_data_loader import StatsBombDataLoader

# Initialize loader
loader = StatsBombDataLoader('core/data/statsbomb_raw')

# Load and process data
loader.load_data()
loader.calculate_player_stats()

# Get benchmarks
benchmarks = loader.calculate_benchmarks()

# Use benchmarks
midfielder_distance_mean = benchmarks['midfielder']['distance']['mean']
# Result: ~10800 meters
```

## Module Structure

### Core Classes

#### `PlayerStats` (dataclass)
Represents individual player statistics from a competition:

```python
@dataclass
class PlayerStats:
    player_id: int
    player_name: str
    position: str  # 'goalkeeper', 'defender', 'midfielder', 'forward'
    distance: float  # meters per match
    max_velocity: float  # m/s
    sprint_count: int  # high-intensity actions
    intensity_score: float  # 0-100
    match_count: int
    team: str
```

#### `StatsBombDataLoader`
Main class for data processing:

```python
class StatsBombDataLoader:
    def __init__(self, data_dir: str) -> None
    def load_data(self) -> bool
    def calculate_player_stats(self) -> Dict[int, PlayerStats]
    def calculate_benchmarks(self) -> Dict[str, Dict[str, Dict[str, float]]]
    def load_and_calculate_benchmarks(self) -> Dict[str, Dict[str, Dict[str, float]]]
    def save_benchmarks(self, output_file: str) -> bool
    def export_player_stats(self, output_file: str) -> bool
    def get_player_benchmarks(self, position: str, metric: str) -> Optional[Dict[str, float]]
```

### Functions

#### `create_default_benchmarks()`
Returns pre-calculated benchmarks based on football analytics literature. Useful when StatsBomb data is unavailable.

## Benchmark Structure

Benchmarks are organized as nested dictionaries:

```python
{
    "midfielder": {
        "distance": {
            "mean": 10800.0,
            "std": 1400.0,
            "min": 7500.0,
            "max": 14500.0,
            "median": 10850.0,
            "sample_size": 150
        },
        "max_velocity": {...},
        "sprint_count": {...},
        "intensity_score": {...}
    },
    "defender": {...},
    "forward": {...},
    "goalkeeper": {...}
}
```

## Metrics Explained

### Distance Covered
- **Unit**: Meters per match
- **Calculation**: Sum of distances between consecutive player positions (estimated from event locations)
- **Benchmark Range**: 4200-10800m depending on position
- **Interpretation**: Higher distance indicates more running, typically expected for midfielders and defenders

### Max Velocity
- **Unit**: m/s (meters per second)
- **Calculation**: Estimated from event distances divided by assumed event duration
- **Benchmark Range**: 6.5-9.2 m/s
- **Interpretation**: Peak speed during actions; defenders and forwards typically show higher max velocities

### Sprint Count
- **Unit**: Number of sprints per match
- **Calculation**: High-intensity actions (passes/duels >5m, shots, tackles)
- **Benchmark Range**: 2-10 sprints per match
- **Interpretation**: Higher values indicate more explosive/intense play

### Intensity Score
- **Unit**: 0-100 scale
- **Calculation**: Ratio of high-intensity actions to total actions
- **Benchmark Range**: 35-71 depending on position
- **Interpretation**: Measures involvement and engagement level; forwards typically show higher intensity

## Data Sources

### Downloaded Data

The module downloads from the StatsBomb Open Data repository:
- **Competitions**: 80 different leagues/tournaments
- **Matches**: Full match data including lineups
- **Events**: 3000-5000 events per match (passes, shots, tackles, etc.)

**Repository**: https://github.com/statsbomb/open-data

### Data Organization

```
core/data/statsbomb_raw/
├── competitions.json
├── matches_Champions_League_*.json
├── matches_Premier_League_*.json
├── matches_La_Liga_*.json
├── events_Champions_League_*.json
├── events_Premier_League_*.json
├── events_La_Liga_*.json
└── [competition_key]/
    ├── match_[id].json
    ├── match_[id].json
    └── ...
```

## Position Mapping

The module maps StatsBomb's detailed positions to 4 standard positions:

| StatsBomb Position | Standard Position |
|---|---|
| Goalkeeper | Goalkeeper |
| Center Back, Right Back, Left Back, Fullback, Wing Back | Defender |
| Center Midfield, Attacking Midfield, Defensive Midfield, Wing, Left/Right Midfield | Midfielder |
| Striker, Center Forward, Left/Right Winger | Forward |

## Usage Examples

### Example 1: Load and Analyze a Specific Player

```python
from core.statsbomb_data_loader import StatsBombDataLoader

loader = StatsBombDataLoader('core/data/statsbomb_raw')
loader.load_data()
player_stats = loader.calculate_player_stats()

# Find a midfielder
for player in player_stats.values():
    if player.position == 'midfielder':
        print(f"{player.player_name}: {player.distance:.0f}m, {player.intensity_score:.1f}% intensity")
        break
```

### Example 2: Compare Player to Benchmark

```python
benchmarks = loader.calculate_benchmarks()
midfielder_benchmark = benchmarks['midfielder']['distance']

player_distance = 11000  # meters
percentile = (player_distance - midfielder_benchmark['min']) / \
             (midfielder_benchmark['max'] - midfielder_benchmark['min']) * 100

print(f"Player is in {percentile:.1f}th percentile for distance")
```

### Example 3: Export for Use in Video Analysis

```python
loader.save_benchmarks('core/data/statsbomb_benchmarks.json')
loader.export_player_stats('core/data/player_stats.json')

# Now use in other modules:
# from video_analysis import VideoAnalyzer
# analyzer = VideoAnalyzer(benchmark_file='core/data/statsbomb_benchmarks.json')
```

## Testing

Run the comprehensive test suite:

```bash
python -m pytest tests/test_statsbomb_loader.py -v
```

Test coverage includes:
- Data loading and validation
- Statistics calculation accuracy
- Benchmark structure and reasonableness
- Error handling for missing/malformed data
- Large file processing
- Default benchmark creation

## Performance Characteristics

- **Data Loading**: ~2-5 minutes for all StatsBomb data (2500+ matches)
- **Processing**: ~10-15 minutes to calculate all player statistics
- **Benchmark Generation**: ~5 minutes
- **Memory Usage**: ~1-2 GB for full dataset

### Optimization Tips

1. **Partial Loading**: Load specific competition data by filtering the data directory
2. **Caching**: Save benchmarks to JSON to avoid recalculation
3. **Parallel Processing**: Modify `calculate_player_stats()` to use multiprocessing for large datasets

## Integration with Other Modules

### With Video Analysis

```python
from core.statsbomb_data_loader import StatsBombDataLoader
from core.player_analyzer import PlayerAnalyzer

loader = StatsBombDataLoader('core/data/statsbomb_raw')
benchmarks = loader.load_and_calculate_benchmarks()

analyzer = PlayerAnalyzer(benchmarks=benchmarks)
analyzer.analyze_video('video.mp4')
```

### With Distance/Velocity Calculator

```python
from core.distance_velocity_calculator import DistanceVelocityCalculator
from core.statsbomb_data_loader import StatsBombDataLoader

loader = StatsBombDataLoader('core/data/statsbomb_raw')
benchmarks = loader.calculate_benchmarks()

calculator = DistanceVelocityCalculator(
    benchmark_distance=benchmarks['midfielder']['distance']['mean'],
    benchmark_velocity=benchmarks['midfielder']['max_velocity']['mean']
)
```

## Error Handling

The module gracefully handles:

- **Missing Data Files**: Falls back to default benchmarks
- **Malformed JSON**: Logs warning and continues processing
- **Missing Fields**: Skips incomplete records
- **Network Errors** (during download): Automatic retry with exponential backoff
- **Large Files**: Streams processing where possible

## Troubleshooting

### Issue: "Data directory not found"
**Solution**: Run `scripts/download_statsbomb_data.py` first to download data

### Issue: "No benchmarks calculated"
**Solution**: Check that events were loaded (should see log messages). Ensure minimum 3 matches per position.

### Issue: Slow performance on large datasets
**Solution**: 
- Load partial data by working with subdirectories
- Use default benchmarks instead
- Run on machine with 4GB+ RAM

### Issue: Different benchmark values on repeated runs
**Solution**: Normal variation if including/excluding different match seasons. Use consistent data subsets.

## Contributing

To improve this module:

1. Add support for additional metrics
2. Enhance position detection accuracy
3. Implement parallel processing for large datasets
4. Add validation against actual tracking data

## License

StatsBomb Open Data is available under Creative Commons Attribution 4.0 International.
This module is part of the Scout AI project.

## References

- StatsBomb Open Data: https://github.com/statsbomb/open-data
- Statsbomb Event Data Documentation: https://github.com/statsbomb/open-data/wiki
- Football Analytics: "Moneyball" principles applied to football

## Support

For issues or questions:
1. Check the test file `tests/test_statsbomb_loader.py` for usage examples
2. Review `examples/statsbomb_usage_example.py` for detailed examples
3. Check the docstrings in `core/statsbomb_data_loader.py`
