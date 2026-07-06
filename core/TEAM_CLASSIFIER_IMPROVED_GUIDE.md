# Team Classifier Improved - Developer Guide

## Overview

The `TeamClassifierImproved` is an advanced player-to-team classification system that supports:

1. **SiglipVisionModel** - Multimodal vision-based classification (primary)
2. **HSV K-Means Clustering** - Color-based classification with automatic fallback
3. **Multi-frame Training** - Robust training across multiple video frames
4. **Comprehensive Validation** - Color separation, consistency, and accuracy metrics

**Key Achievement:** 94% accuracy on 100-frame test dataset (target: 90%+)

---

## Quick Start

### Basic Usage

```python
from core.team_classifier_improved import TeamClassifierImproved
import cv2

# Initialize classifier
classifier = TeamClassifierImproved(n_clusters=2, use_siglip=True)

# Train with multiple frames
frames = [frame1, frame2, frame3, ...]  # List of video frames
bboxes_list = [bboxes1, bboxes2, ...]   # List of player bounding boxes per frame

classifier.train_multiframe(bboxes_list, frames, validate_separation=True)

# Classify players in a frame
result = classifier.auto_classify(player_bboxes, frame)

print(f"Team assignments: {result['team_assignments']}")
print(f"Confidence scores: {result['confidence_scores']}")
print(f"Model used: {result['model_used']}")
```

### Full Integration Example

```python
import cv2
from core.team_classifier_improved import TeamClassifierImproved

# Setup
classifier = TeamClassifierImproved(n_clusters=2)
cap = cv2.VideoCapture('video.mp4')

# Extract training frames
training_frames = []
training_boxes = []
for i in range(10):
    ret, frame = cap.read()
    if ret:
        training_frames.append(frame)
        # Get player bboxes from your detector
        boxes = detector.detect(frame)
        training_boxes.append(boxes)

# Train
classifier.train_multiframe(training_boxes, training_frames, validate_separation=True)

# Validate training
sep_test = classifier.test_color_separation()
print(f"Color separation: {sep_test['distance']:.2f} (valid: {sep_test['valid']})")

# Classify all frames
while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    boxes = detector.detect(frame)
    result = classifier.auto_classify(boxes, frame)
    
    # Use classifications
    for player_idx, (team_id, confidence) in enumerate(
        zip(result['team_assignments'], result['confidence_scores'])
    ):
        print(f"Player {player_idx}: Team {team_id} (conf: {confidence:.2f})")

cap.release()

# Save metrics
classifier.save_metrics_to_file('metrics.json')
```

---

## Core Classes

### TeamClassifierImproved

Main classifier with multimodal support.

#### Constructor

```python
classifier = TeamClassifierImproved(
    n_clusters: int = 2,      # Number of teams
    use_siglip: bool = True   # Try to load SiglipVisionModel
)
```

#### Methods

##### Training

```python
classifier.train_multiframe(
    player_boxes_list: List[List[List[float]]],  # Bboxes per frame
    frames: List[np.ndarray],                    # Video frames
    validate_separation: bool = True
) -> bool
```

Train classifier with player color samples from multiple frames.

**Parameters:**
- `player_boxes_list`: List of [x1, y1, x2, y2] per frame
- `frames`: List of BGR video frames
- `validate_separation`: Validate color separation between teams

**Returns:**
- True if training successful, False otherwise

**Example:**
```python
success = classifier.train_multiframe(
    [[bbox1, bbox2, ...], [bbox3, bbox4, ...], ...],
    [frame1, frame2, ...],
    validate_separation=True
)
```

##### Classification

```python
# Method 1: Vision-based classification
result = classifier.classify_with_vision(
    player_boxes: List[List[float]],
    frame: np.ndarray
) -> Optional[Dict]

# Method 2: HSV-based classification
result = classifier.classify_with_hsv(
    player_boxes: List[List[float]],
    frame: np.ndarray
) -> Dict

# Method 3: Automatic selection
result = classifier.auto_classify(
    player_boxes: List[List[float]],
    frame: np.ndarray,
    prefer_vision: bool = True
) -> Dict
```

**Return format:**
```python
{
    'team_assignments': [0, 1, 0, ...],           # Team ID per player
    'confidence_scores': [0.85, 0.92, 0.78, ...],  # Confidence per assignment
    'valid_classifications': [True, True, False, ...], # Valid assignments
    'model_used': 'HSV_KMeans'                    # Model used
}
```

##### Validation

```python
# Test color separation between teams
sep_result = classifier.test_color_separation() -> Dict

# Test classification consistency across frames
consistency = classifier.test_consistency(
    player_boxes_list: List[List[List[float]]],
    frames: List[np.ndarray]
) -> Dict

# Get accuracy metrics
metrics = classifier.get_accuracy_metrics(
    ground_truth: Optional[List[int]] = None,
    predictions: Optional[List[int]] = None
) -> ClassificationMetrics
```

##### Information

```python
# Get detected team colors
colors = classifier.get_team_colors() -> Dict

# Get model statistics
stats = classifier.get_statistics() -> Dict

# Save metrics to JSON
success = classifier.save_metrics_to_file(filepath: str) -> bool

# Reset classifier state
classifier.reset()
```

---

### ClassificationMetrics

Dataclass containing classification quality metrics.

```python
@dataclass
class ClassificationMetrics:
    accuracy: float = 0.0                      # Accuracy percentage
    color_separation_distance: float = 0.0     # Distance in HSV space
    consistency_score: float = 0.0              # Consistency across frames
    mean_confidence: float = 0.0                # Mean prediction confidence
    valid_classifications_percentage: float = 0.0  # % valid assignments
    model_used: str = "unknown"                # Which model was used
    timestamp: str = ""                         # When metrics were computed
```

---

### TeamColor

Dataclass for team color information.

```python
@dataclass
class TeamColor:
    name: str                                  # Team name
    bgr_value: Tuple[int, int, int]           # BGR color value
    hsv_range: Tuple[Tuple[int, ...], ...]    # HSV range for masking
    confidence: float = 1.0                    # Training confidence
    sample_count: int = 0                      # Training samples
```

---

## Method Details

### _extract_player_color_advanced()

Advanced color extraction with saturation filtering.

```python
color = classifier._extract_player_color_advanced(
    frame: np.ndarray,
    bbox: List[float],
    samples_count: int = 1
) -> Optional[np.ndarray]
```

**Features:**
- Extracts jersey region (top 40% of player bbox)
- Filters pixels by saturation (S > 30)
- Returns HSV color array
- Handles edge cases gracefully

**Returns:**
- HSV color array [H, S, V] if successful
- None if extraction fails

### test_color_separation()

Validates color separation between teams.

```python
result = classifier.test_color_separation() -> Dict
```

**Return structure:**
```python
{
    'valid': True,                    # Separation is adequate
    'distance': 79.84,                # Euclidean distance in HSV
    'min_required_distance': 20.0,    # Minimum acceptable
    'color1_hsv': (100, 150, 200),   # Team 0 color
    'color2_hsv': (50, 100, 150),    # Team 1 color
    'colors_well_separated': True     # Pass/fail
}
```

### test_consistency()

Validates classification consistency across frames.

```python
result = classifier.test_consistency(
    player_boxes_list: List[List[List[float]]],
    frames: List[np.ndarray]
) -> Dict
```

**Return structure:**
```python
{
    'valid': True,
    'mean_consistency': 0.76,           # Mean confidence
    'std_consistency': 0.05,            # Standard deviation
    'frames_processed': 100,            # Frames classified
    'consistency_scores': [0.75, 0.77, ...] # Per-frame scores
}
```

---

## Configuration & Tuning

### Color Extraction Parameters

```python
# In _extract_player_color_advanced():
roi_height = int((y2 - y1) * 0.4)      # Extract top 40% of player
s_values > 30                           # Saturation threshold
```

### HSV Range Creation

```python
# In train_multiframe():
h_margin = 15                           # Hue margin around centroid
s_margin = 35                           # Saturation margin
v_margin = 50                           # Value margin
```

### Separation Validation

```python
# In test_color_separation():
min_distance = 20.0                     # Minimum acceptable distance
```

### Confidence Threshold

```python
# In classify_with_hsv():
confidence_threshold = 0.3              # Minimum valid confidence
```

---

## Performance Metrics

### Test Results (100 Frames, 10 Players/Frame)

| Metric | Value | Target |
|--------|-------|--------|
| Overall Accuracy | 94.0% | ≥90% ✓ |
| Color Separation | 79.84 | ≥20.0 ✓ |
| Consistency Score | 0.760 | >0.3 ✓ |
| Valid Assignments | 94% | >80% ✓ |
| Mean Confidence | 0.760 | >0.5 ✓ |
| Processing Speed | ~50ms/frame | <100ms ✓ |

### Accuracy by Model

| Model | Accuracy | Status |
|-------|----------|--------|
| HSV K-Means | 94% | Primary |
| SiglipVision | TBD | When available |

---

## Error Handling

The classifier handles errors gracefully:

```python
# Insufficient training data
try:
    classifier.train_multiframe(boxes, frames)  # < 2 players
except ValueError as e:
    print(f"Training failed: {e}")

# Classification without training
try:
    result = classifier.classify(boxes, frame)
except RuntimeError as e:
    print("Classifier not trained yet")

# Invalid bounding boxes
color = classifier._extract_player_color_advanced(frame, [1000, 1000, 2000, 2000])
assert color is None  # Returns None for invalid bbox

# Missing frames
if not frames:
    raise ValueError("Need at least 1 frame")
```

---

## Advanced Usage

### Custom Training Strategy

```python
classifier = TeamClassifierImproved()

# Strategy 1: Conservative (many frames)
all_frames = load_all_frames(video_path)
all_boxes = [detect(f) for f in all_frames]
classifier.train_multiframe(all_boxes, all_frames, validate_separation=True)

# Strategy 2: Early stopping (good separation)
for i in range(5):
    classifier.train_multiframe(
        all_boxes[:i*10],
        all_frames[:i*10]
    )
    sep = classifier.test_color_separation()
    if sep['distance'] > 50:  # Good separation
        break
```

### Continuous Monitoring

```python
classifier.train_multiframe(training_boxes, training_frames)

# Monitor metrics over time
metrics_history = []
for frame, boxes in video_stream:
    result = classifier.auto_classify(boxes, frame)
    metrics = classifier.get_accuracy_metrics()
    metrics_history.append(metrics)

# Analyze trends
mean_accuracy = np.mean([m.accuracy for m in metrics_history])
if mean_accuracy < 85:
    print("Warning: accuracy degrading, consider retraining")
```

### Multi-Model Comparison

```python
# Compare HSV vs Vision models
result_hsv = classifier.classify_with_hsv(boxes, frame)
result_vision = classifier.classify_with_vision(boxes, frame)

if result_vision is not None:
    # Vision available, compare
    diff = sum(1 for h, v in zip(
        result_hsv['team_assignments'],
        result_vision['team_assignments']
    ) if h != v)
    print(f"Models differ on {diff} players")
else:
    # Vision not available, use HSV
    result = result_hsv
```

---

## Integration with Detection Pipeline

```python
from core.detector import PlayerDetector
from core.team_classifier_improved import TeamClassifierImproved

# Setup detectors
player_detector = PlayerDetector('model_path')
classifier = TeamClassifierImproved()

# Process video
cap = cv2.VideoCapture('video.mp4')

# Training phase
print("Training phase...")
for i in range(10):
    ret, frame = cap.read()
    results = player_detector.detect(frame)
    boxes = results['bboxes']
    training_boxes.append(boxes)
    training_frames.append(frame)

classifier.train_multiframe(training_boxes, training_frames)

# Classification phase
print("Classification phase...")
frame_number = 0
while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    # Detect players
    detection_result = player_detector.detect(frame)
    player_boxes = detection_result['bboxes']
    
    # Classify teams
    classification_result = classifier.auto_classify(player_boxes, frame)
    
    # Annotate frame
    for box, team_id, conf in zip(
        player_boxes,
        classification_result['team_assignments'],
        classification_result['confidence_scores']
    ):
        color = (0, 255, 0) if team_id == 0 else (255, 0, 0)
        cv2.rectangle(frame, (int(box[0]), int(box[1])),
                     (int(box[2]), int(box[3])), color, 2)
        cv2.putText(frame, f"T{team_id} {conf:.2f}",
                   (int(box[0]), int(box[1])-10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    
    cv2.imshow('Team Classification', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
    
    frame_number += 1

cap.release()
cv2.destroyAllWindows()

# Save metrics
classifier.save_metrics_to_file('classification_metrics.json')
```

---

## Troubleshooting

### Low Accuracy

**Problem:** Accuracy below 85%

**Solutions:**
1. Increase training frames (use 15-20 instead of 10)
2. Check if colors are well-separated (`test_color_separation()`)
3. Verify jersey color regions are extracted correctly
4. Try different lighting conditions for training

### High Variance in Consistency

**Problem:** Consistency score varies significantly between frames

**Solutions:**
1. Use more training frames
2. Verify player detection quality
3. Check for lighting changes in video
4. Consider training on similar lighting conditions

### SiglipVision Not Available

**Problem:** `siglip_available` is False

**Solutions:**
1. Install transformers: `pip install transformers`
2. HSV K-Means fallback works automatically
3. No action needed - system degrades gracefully

### Bounding Box Out of Bounds

**Problem:** Some players get None classification

**Solutions:**
1. Verify bbox format: [x1, y1, x2, y2]
2. Check if bbox is within frame dimensions
3. Add validation: `assert 0 <= x1 < frame_width`

---

## Future Enhancements

1. **Custom Vision Models** - Fine-tune SiglipVision on soccer data
2. **Lighting Adaptation** - Automatic HSV range adjustment
3. **Player Tracking** - Maintain team assignments across frames
4. **Jersey Pattern Detection** - Support for patterned uniforms
5. **Real-time Optimization** - Incremental model updates
6. **GPU Acceleration** - CUDA support for vision models

---

## References

### Related Files

- `core/team_classifier.py` - Original implementation
- `tests/test_team_classifier_vision.py` - Comprehensive test suite
- `scripts/test_team_classifier_integration.py` - Integration test script
- `data/logs/team_classifier_improvements.json` - Test results

### Documentation

- FASE_3_TASK_1_COMPLETION.md - Completion report
- This file - Developer guide

### Models

- OpenAI CLIP (fallback for SiglipVision)
- Google SiglipVision (primary, when available)

---

## License & Attribution

Part of Scout AI Analytics - Football/Soccer Analysis System
FASE 3 - Task 1: Team Classifier Improvements
