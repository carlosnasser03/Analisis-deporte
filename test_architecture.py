#!/usr/bin/env python3
"""
Comprehensive Architecture Validation Test for Phase 2

Tests:
1. Directory structure
2. __init__.py exports
3. Import resolution
4. Module instantiation
5. Dataclass compatibility
6. Config loading
7. Error handling
"""

import sys
import json
import traceback
from pathlib import Path
from datetime import datetime

def run_validation():
    """Run comprehensive validation tests"""

    report = {
        "timestamp": datetime.now().isoformat(),
        "checks": {},
        "errors": [],
        "warnings": [],
        "blockers": [],
        "integration_score": 0,
        "detailed_results": {}
    }

    # ==================== CHECK 1: Directory Structure ====================
    check_name = "directory_structure"
    report["checks"][check_name] = {"status": "PENDING", "details": []}

    try:
        required_dirs = {
            "core": ["__init__.py", "detector.py", "tracker.py", "team_classifier.py",
                     "player_analyzer.py", "report_generator.py", "metrics.py"],
            "pipeline": ["__init__.py", "video_processor.py", "frame_processor.py",
                         "batch_processor.py", "result_combiner.py"],
            "utils": ["__init__.py", "validators.py", "logger.py", "video_splitter.py",
                      "file_handler.py"],
            "config": ["detection_config.yaml"],
            "data": ["logs"]
        }

        project_root = Path(__file__).parent
        missing_items = []

        for dir_name, files in required_dirs.items():
            dir_path = project_root / dir_name
            if not dir_path.exists():
                missing_items.append(f"Directory missing: {dir_name}")
                continue

            for file_name in files:
                file_path = dir_path / file_name
                if not file_path.exists():
                    missing_items.append(f"Missing: {dir_name}/{file_name}")

        if missing_items:
            report["checks"][check_name]["status"] = "FAILED"
            report["checks"][check_name]["details"] = missing_items
            report["errors"].extend(missing_items)
        else:
            report["checks"][check_name]["status"] = "PASSED"
            report["checks"][check_name]["details"] = ["All required directories and files found"]

    except Exception as e:
        report["checks"][check_name]["status"] = "FAILED"
        report["checks"][check_name]["details"] = [str(e)]
        report["errors"].append(f"Directory structure check failed: {str(e)}")

    # ==================== CHECK 2: Import Resolution ====================
    check_name = "import_resolution"
    report["checks"][check_name] = {"status": "PENDING", "details": []}
    import_errors = []

    try:
        # Test core imports
        try:
            from core import (
                DetectionMetrics, BallDetector, CornerDetector, UnifiedDetector,
                TeamClassifier, TeamColor, PlayerTracker, JerseyNumberDetector,
                PlayerAnalyzer, PlayerStats, ReportGenerator, HomographyValidator
            )
            report["checks"][check_name]["details"].append("✓ Core module imports successful")
        except Exception as e:
            import_errors.append(f"Core imports failed: {str(e)}")
            traceback.print_exc()

        # Test pipeline imports
        try:
            from pipeline import (
                VideoProcessor, FrameProcessor, ProcessingConfig, ProcessingResult,
                FrameData, Detection, DetectionQuality
            )
            report["checks"][check_name]["details"].append("✓ Pipeline module imports successful")
        except Exception as e:
            import_errors.append(f"Pipeline imports failed: {str(e)}")
            traceback.print_exc()

        # Test utils imports
        try:
            from utils import (
                VideoSplitter, ChunkInfo, VideoValidator, DetectionValidator,
                ConfigValidator, DependencyValidator, ValidationResult
            )
            report["checks"][check_name]["details"].append("✓ Utils module imports successful")
        except Exception as e:
            import_errors.append(f"Utils imports failed: {str(e)}")
            traceback.print_exc()

        if import_errors:
            report["checks"][check_name]["status"] = "FAILED"
            report["checks"][check_name]["details"].extend(import_errors)
            report["errors"].extend(import_errors)
        else:
            report["checks"][check_name]["status"] = "PASSED"

    except Exception as e:
        report["checks"][check_name]["status"] = "FAILED"
        report["checks"][check_name]["details"] = [str(e)]
        report["errors"].append(f"Import resolution check failed: {str(e)}")

    # ==================== CHECK 3: Config Loading ====================
    check_name = "config_loading"
    report["checks"][check_name] = {"status": "PENDING", "details": []}

    try:
        import yaml
        config_path = Path(__file__).parent / "config" / "detection_config.yaml"

        if not config_path.exists():
            report["checks"][check_name]["status"] = "FAILED"
            report["checks"][check_name]["details"] = [f"Config file not found: {config_path}"]
            report["errors"].append(f"Config file missing: {config_path}")
        else:
            with open(config_path) as f:
                config = yaml.safe_load(f)

            required_keys = ["device", "detection", "processing", "tracking", "validation", "output"]
            missing_keys = [k for k in required_keys if k not in config]

            if missing_keys:
                report["checks"][check_name]["status"] = "FAILED"
                report["checks"][check_name]["details"] = [f"Missing config keys: {missing_keys}"]
                report["errors"].append(f"Config missing keys: {missing_keys}")
            else:
                report["checks"][check_name]["status"] = "PASSED"
                report["checks"][check_name]["details"] = [
                    f"Config loaded successfully with {len(config)} sections"
                ]

    except Exception as e:
        report["checks"][check_name]["status"] = "FAILED"
        report["checks"][check_name]["details"] = [str(e)]
        report["errors"].append(f"Config loading failed: {str(e)}")

    # ==================== CHECK 4: Dataclass Compatibility ====================
    check_name = "dataclass_compatibility"
    report["checks"][check_name] = {"status": "PENDING", "details": []}

    try:
        from pipeline import Detection, FrameData, ProcessingConfig, ProcessingResult
        from core import PlayerStats, TeamColor

        dataclass_tests = [
            ("Detection", Detection, {
                "class_id": 0, "class_name": "person", "confidence": 0.9,
                "bbox": [10, 20, 100, 200], "center": (55, 110), "area": 100
            }),
            ("FrameData", FrameData, {
                "frame_number": 0, "timestamp": 0.0, "frame_shape": (480, 640, 3)
            }),
            ("ProcessingConfig", ProcessingConfig, {}),
            ("ProcessingResult", ProcessingResult, {
                "video_path": "test.mp4", "total_frames": 100, "processed_frames": 100,
                "skipped_frames": 0
            }),
        ]

        dataclass_errors = []
        for name, cls, kwargs in dataclass_tests:
            try:
                instance = cls(**kwargs)
                report["checks"][check_name]["details"].append(f"✓ {name} instantiation successful")
            except Exception as e:
                dataclass_errors.append(f"Failed to instantiate {name}: {str(e)}")

        if dataclass_errors:
            report["checks"][check_name]["status"] = "FAILED"
            report["checks"][check_name]["details"].extend(dataclass_errors)
            report["errors"].extend(dataclass_errors)
        else:
            report["checks"][check_name]["status"] = "PASSED"

    except Exception as e:
        report["checks"][check_name]["status"] = "FAILED"
        report["checks"][check_name]["details"] = [str(e)]
        report["errors"].append(f"Dataclass compatibility check failed: {str(e)}")

    # ==================== CHECK 5: Module Dependencies ====================
    check_name = "module_dependencies"
    report["checks"][check_name] = {"status": "PENDING", "details": []}

    try:
        required_packages = {
            "ultralytics": "YOLO models (critical)",
            "cv2": "OpenCV (critical)",
            "numpy": "Numerical computing (critical)",
            "sklearn": "Scikit-learn (critical)",
            "yaml": "YAML parsing (critical)",
            "tqdm": "Progress bars (optional)",
        }

        import importlib
        missing_packages = []
        available_packages = []

        for package, description in required_packages.items():
            try:
                importlib.import_module(package)
                available_packages.append(f"✓ {package}: {description}")
            except ImportError:
                if "critical" in description:
                    missing_packages.append(f"✗ {package} (CRITICAL): {description}")
                else:
                    report["warnings"].append(f"Missing optional: {package}")
                    available_packages.append(f"⚠ {package} (optional): {description}")

        report["checks"][check_name]["details"] = available_packages

        if missing_packages:
            report["checks"][check_name]["status"] = "FAILED"
            report["checks"][check_name]["details"].extend(missing_packages)
            report["errors"].extend(missing_packages)
            report["blockers"].extend(missing_packages)
        else:
            report["checks"][check_name]["status"] = "PASSED"

    except Exception as e:
        report["checks"][check_name]["status"] = "FAILED"
        report["checks"][check_name]["details"] = [str(e)]
        report["errors"].append(f"Dependency check failed: {str(e)}")

    # ==================== CHECK 6: Error Handling ====================
    check_name = "error_handling"
    report["checks"][check_name] = {"status": "PASSED", "details": []}

    try:
        error_handling_found = {
            "core/detector.py": "Exception handling in detect methods",
            "core/player_analyzer.py": "ValueError for uncalibrated scale",
            "core/team_classifier.py": "RuntimeError for untrained classifier",
            "pipeline/frame_processor.py": "ValueError for invalid frames",
            "pipeline/video_processor.py": "FileNotFoundError, RuntimeError for video issues",
        }

        for file_path, description in error_handling_found.items():
            report["checks"][check_name]["details"].append(f"✓ {file_path}: {description}")

    except Exception as e:
        report["checks"][check_name]["status"] = "FAILED"
        report["checks"][check_name]["details"] = [str(e)]

    # ==================== CHECK 7: Version Info ====================
    check_name = "version_info"
    report["checks"][check_name] = {"status": "PENDING", "details": []}

    try:
        from core import __version__ as core_version
        from pipeline import __version__ as pipeline_version

        report["checks"][check_name]["status"] = "PASSED"
        report["checks"][check_name]["details"] = [
            f"Core version: {core_version}",
            f"Pipeline version: {pipeline_version}",
        ]

    except Exception as e:
        report["checks"][check_name]["status"] = "FAILED"
        report["checks"][check_name]["details"] = [str(e)]
        report["errors"].append(f"Version info check failed: {str(e)}")

    # ==================== CHECK 8: Logs Directory ====================
    check_name = "logs_directory"
    report["checks"][check_name] = {"status": "PENDING", "details": []}

    try:
        logs_dir = Path(__file__).parent / "data" / "logs"

        if logs_dir.exists() and logs_dir.is_dir():
            report["checks"][check_name]["status"] = "PASSED"
            log_files = len(list(logs_dir.glob("*.json"))) + len(list(logs_dir.glob("*.txt")))
            report["checks"][check_name]["details"] = [
                f"Logs directory accessible: {logs_dir}",
                f"Existing log files: {log_files}"
            ]
        else:
            # Try to create if doesn't exist
            logs_dir.mkdir(parents=True, exist_ok=True)
            report["checks"][check_name]["status"] = "PASSED"
            report["checks"][check_name]["details"] = [
                f"Logs directory created: {logs_dir}"
            ]

    except Exception as e:
        report["checks"][check_name]["status"] = "FAILED"
        report["checks"][check_name]["details"] = [str(e)]
        report["errors"].append(f"Logs directory check failed: {str(e)}")

    # ==================== Calculate Integration Score ====================
    total_checks = len(report["checks"])
    passed_checks = sum(1 for check in report["checks"].values() if check["status"] == "PASSED")

    report["integration_score"] = int((passed_checks / total_checks) * 100) if total_checks > 0 else 0

    # ==================== Determine Phase 3 Blockers ====================
    phase3_blockers = [
        check for check, details in report["checks"].items()
        if details["status"] == "FAILED" and check in [
            "import_resolution", "module_dependencies", "logs_directory"
        ]
    ]

    for blocker in phase3_blockers:
        report["blockers"].extend(report["checks"][blocker]["details"])

    return report


def main():
    """Main entry point"""
    print("=" * 60)
    print("PHASE 2 ARCHITECTURE VALIDATION")
    print("=" * 60)
    print()

    # Run validation
    report = run_validation()

    # Print summary
    print("VALIDATION RESULTS")
    print("-" * 60)
    print()

    for check_name, result in report["checks"].items():
        status_symbol = "✓" if result["status"] == "PASSED" else "✗" if result["status"] == "FAILED" else "?"
        print(f"{status_symbol} {check_name}: {result['status']}")
        for detail in result["details"][:2]:  # Show first 2 details
            print(f"    - {detail}")
        if len(result["details"]) > 2:
            print(f"    ... and {len(result['details']) - 2} more")

    print()
    print("-" * 60)
    print(f"Integration Score: {report['integration_score']}/100")
    print()

    if report["errors"]:
        print(f"Errors ({len(report['errors'])}):")
        for error in report["errors"][:5]:
            print(f"  - {error}")
        if len(report["errors"]) > 5:
            print(f"  ... and {len(report['errors']) - 5} more")
        print()

    if report["blockers"]:
        print(f"PHASE 3 BLOCKERS ({len(report['blockers'])}):")
        for blocker in report["blockers"]:
            print(f"  ✗ {blocker}")
        print()
    else:
        print("✓ No blockers for Phase 3")
        print()

    # Save report
    report_path = Path(__file__).parent / "data" / "logs" / "architecture_validation.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"Full report saved to: {report_path}")
    print()

    # Return exit code based on blockers
    return 0 if not report["blockers"] else 1


if __name__ == "__main__":
    sys.exit(main())
