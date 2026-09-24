"""
test_import_validation.py - Validation test for module imports

Tests that all modules can be imported cleanly from multiple contexts:
1. Direct imports as script (sys.path from project root)
2. Package imports from test runner
3. No circular dependencies
4. No silent import failures

Author: Scout AI
Date: 2026-09-24
"""

import sys
import pytest
from pathlib import Path

# Get project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestCoreImports:
    """Test core module imports"""

    def test_import_detector(self):
        """Test core.detector import"""
        from core.detector import BallDetector
        assert BallDetector is not None

    def test_import_tracker(self):
        """Test core.tracker import"""
        from core.tracker import PlayerTracker
        assert PlayerTracker is not None

    def test_import_team_classifier(self):
        """Test core.team_classifier import"""
        from core.team_classifier import TeamClassifier
        assert TeamClassifier is not None


class TestUtilsImports:
    """Test utils module imports"""

    def test_import_video_reader(self):
        """Test utils.video_reader import"""
        from utils.video_reader import VideoReader, ColorSpaceConverter
        assert VideoReader is not None
        assert ColorSpaceConverter is not None

    def test_import_validators(self):
        """Test utils.validators import"""
        from utils.validators import ValidationResult
        assert ValidationResult is not None


class TestPipelineImports:
    """Test pipeline module imports - the critical ones with previously broken imports"""

    def test_import_frame_processor(self):
        """Test pipeline.frame_processor import (was failing with relative imports)"""
        from pipeline.frame_processor import FrameProcessor, FrameData
        assert FrameProcessor is not None
        assert FrameData is not None

    def test_import_video_processor(self):
        """Test pipeline.video_processor import (was failing with relative imports)"""
        from pipeline.video_processor import VideoProcessor, ProcessingConfig
        assert VideoProcessor is not None
        assert ProcessingConfig is not None

    def test_import_video_processor_fase3(self):
        """Test pipeline.video_processor_fase3 import (was failing with relative imports)"""
        from pipeline.video_processor_fase3 import VideoProcessorFase3
        assert VideoProcessorFase3 is not None

    def test_import_from_pipeline_package(self):
        """Test that pipeline package exports work correctly"""
        from pipeline import (
            VideoProcessor,
            FrameProcessor,
            VideoProcessorFase3
        )
        # These should NOT be None - no silent failures
        assert VideoProcessor is not None, \
            "pipeline.VideoProcessor is None - import failed silently"
        assert FrameProcessor is not None, \
            "pipeline.FrameProcessor is None - import failed silently"
        assert VideoProcessorFase3 is not None, \
            "pipeline.VideoProcessorFase3 is None - import failed silently"

    def test_frame_processor_has_dependencies(self):
        """Test that FrameProcessor can access its dependencies"""
        from pipeline.frame_processor import FrameProcessor

        # Create an instance to verify dependencies work
        processor = FrameProcessor()
        assert processor.color_converter is not None, \
            "FrameProcessor.color_converter is None - ColorSpaceConverter import failed"

    def test_video_processor_has_dependencies(self):
        """Test that VideoProcessor can access frame_processor dependency"""
        from pipeline.video_processor import VideoProcessor
        from pipeline.frame_processor import FrameProcessor

        assert VideoProcessor is not None
        assert FrameProcessor is not None


class TestIntegrationImports:
    """Test integration module imports"""

    def test_import_deep_sort(self):
        """Test deep_sort_integration import"""
        from deep_sort_integration.deep_sort_tracker import DeepSortTracker
        assert DeepSortTracker is not None

    def test_import_football_tracking(self):
        """Test football_tracking_integration import"""
        # Test that the module can be imported successfully
        import football_tracking_integration
        assert football_tracking_integration is not None


class TestCircularDependencies:
    """Test for circular dependencies"""

    def test_no_circular_import_pipeline(self):
        """Ensure pipeline modules don't create circular imports"""
        # This test passes if it doesn't raise ImportError or circular import errors
        from pipeline import FrameProcessor, VideoProcessor
        assert FrameProcessor is not None
        assert VideoProcessor is not None


class TestImportPaths:
    """Test that imports work from various path configurations"""

    def test_absolute_import_from_project_root(self):
        """Test absolute imports work when project root is in sys.path"""
        # This is the configuration used by most scripts
        assert str(PROJECT_ROOT) in sys.path

        # These imports should work
        from utils.video_reader import ColorSpaceConverter
        from core.detector import BallDetector
        from pipeline.frame_processor import FrameProcessor

        assert ColorSpaceConverter is not None
        assert BallDetector is not None
        assert FrameProcessor is not None


# Pytest configuration
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
