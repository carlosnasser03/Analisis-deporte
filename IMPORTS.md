# Scout AI - Import Structure Documentation

## Overview

This document describes the import structure and how to properly use the Scout AI package across different execution contexts.

## Project Structure

```
scout-ai/
├── core/                          # Core analysis modules
│   ├── __init__.py
│   ├── detector.py
│   ├── tracker.py
│   ├── team_classifier.py
│   └── ... (other modules)
├── pipeline/                      # Main processing pipeline
│   ├── __init__.py
│   ├── frame_processor.py         # Processes individual frames
│   ├── video_processor.py         # Processes complete videos
│   ├── video_processor_fase3.py   # End-to-end integrated pipeline
│   └── ... (other modules)
├── utils/                         # Utility functions
│   ├── __init__.py
│   ├── video_reader.py
│   ├── validators.py
│   └── ... (other utilities)
├── tests/                         # Test suite
│   ├── __init__.py
│   ├── test_import_validation.py  # Import validation tests
│   └── ... (other tests)
├── deep_sort_integration/         # Deep SORT tracking integration
├── football_tracking_integration/ # Football-specific tracking
├── pyproject.toml                 # Project configuration
├── 1_preparar.py                  # Setup script
├── 2_analizar.py                  # Main analysis script
└── README.md                      # Project README
```

## Import Patterns

### 1. **Scripts from Project Root** (Most Common)

When running scripts from the project root directory, all modules should be imported using absolute imports:

```python
# File: 2_analizar.py (in project root)
from core.detector import BallDetector
from pipeline.frame_processor import FrameProcessor
from utils.video_reader import VideoReader
```

This works because:
- When you run `python 2_analizar.py`, Python adds the current directory to `sys.path`
- The project root is in `sys.path`, so `core`, `pipeline`, and `utils` are accessible

### 2. **Within Modules (Inter-module imports)**

When importing from one module to another within the project, use absolute imports:

```python
# File: pipeline/video_processor.py
from pipeline.frame_processor import FrameProcessor, FrameData
from utils.video_reader import VideoReader, OpenCVVideoReader
from core.team_classifier import TeamClassifier
```

Why not relative imports (`from ..utils.video_reader`)? 
- Relative imports fail when modules are imported as scripts or from different contexts
- Absolute imports work consistently across all execution contexts

### 3. **Within-Package Imports** (Same directory)

For imports within the same package (same directory), relative imports with single dot (`.`) are acceptable:

```python
# File: utils/__init__.py
from .video_splitter import VideoSplitter
from .validators import ValidationResult
```

## Migration Changes

### Fixed Imports (from relative to absolute)

The following files were updated to use absolute imports instead of relative imports with `..`:

**File: `pipeline/frame_processor.py`**
```python
# Before (BROKEN)
from ..utils.video_reader import ColorSpaceConverter

# After (FIXED)
from utils.video_reader import ColorSpaceConverter
```

**File: `pipeline/video_processor.py`**
```python
# Before (BROKEN)
from .frame_processor import FrameProcessor, FrameData
from ..utils.video_reader import VideoReader, OpenCVVideoReader

# After (FIXED)
from pipeline.frame_processor import FrameProcessor, FrameData
from utils.video_reader import VideoReader, OpenCVVideoReader
```

**File: `pipeline/video_processor_fase3.py`**
```python
# Before (BROKEN)
from .frame_processor import FrameProcessor, FrameData
from ..utils.video_reader import VideoReader, OpenCVVideoReader
from ..core.team_classifier import TeamClassifier
from ..core.tracker import PlayerTracker
from ..core.jersey_number_detector import JerseyNumberDetector

# After (FIXED)
from pipeline.frame_processor import FrameProcessor, FrameData
from utils.video_reader import VideoReader, OpenCVVideoReader
from core.team_classifier import TeamClassifier
from core.tracker import PlayerTracker
from core.jersey_number_detector import JerseyNumberDetector
```

### Enhanced Error Reporting

**File: `pipeline/__init__.py`**

Updated to log import errors instead of silently suppressing them:

```python
import logging

logger = logging.getLogger(__name__)

try:
    from .video_processor import VideoProcessor, ProcessingConfig, ProcessingResult
except ImportError as e:
    logger.error(f"Failed to import VideoProcessor: {e}")
    VideoProcessor = None
```

Now when imports fail, errors are logged instead of being silently ignored.

## Validation

A comprehensive test suite validates all import patterns:

```bash
pytest tests/test_import_validation.py -v
```

This test suite verifies:
- Direct imports from project root
- Package imports 
- No circular dependencies
- No silent import failures
- Dependencies can be instantiated

## Running Scripts

### From Project Root

```bash
# Add project root to sys.path automatically
python 2_analizar.py
python 1_preparar.py

# Or explicitly
python -m pipeline.video_processor
```

### Running Tests

```bash
# Run import validation tests
pytest tests/test_import_validation.py -v

# Run all tests
pytest tests/ -v
```

## Troubleshooting

### ImportError: attempted relative import beyond top-level package

This error means code is trying to use relative imports (`..`) when the module isn't part of an installed package.

**Solution**: Update imports to use absolute imports (as documented above).

### ImportError: No module named 'core' / 'pipeline' / 'utils'

This error means the project root isn't in `sys.path`.

**Solution**: 
1. Run scripts from the project root directory
2. Or add the project root to `sys.path` manually:
   ```python
   import sys
   from pathlib import Path
   sys.path.insert(0, str(Path(__file__).parent))
   ```

### Import succeeds but class is None

This indicates a silent import failure in `pipeline/__init__.py`. Check the logs:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

from pipeline import VideoProcessor
# Now you'll see error messages in the logs
```

## Best Practices

1. **Always use absolute imports** for inter-module imports
2. **Keep imports explicit** - import exactly what you need
3. **Test imports** - use `pytest tests/test_import_validation.py` to verify
4. **Log errors** - don't silently catch ImportError exceptions
5. **Run from project root** - this ensures `sys.path` is configured correctly

## Configuration

Project configuration is defined in `pyproject.toml`:
- Python version requirements
- Dependencies
- Test configuration
- Code formatting rules
- Type checking configuration

Refer to `pyproject.toml` for the complete project configuration.
