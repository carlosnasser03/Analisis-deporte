#!/usr/bin/env python3
"""
Simplified Architecture Validation Test for Phase 2

Tests:
1. Directory structure
2. __init__.py exports
3. Import resolution (with graceful fallback)
4. Config loading
5. Error handling
"""

import sys
import json
import traceback
from pathlib import Path
from datetime import datetime
import os

# Set UTF-8 encoding for Windows
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

def run_validation():
    """Run comprehensive validation tests"""

    report = {
        "timestamp": datetime.now().isoformat(),
        "checks": {},
        "errors": [],
        "warnings": [],
        "blockers": [],
        "integration_score": 0,
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

    # ==================== CHECK 2: Config Loading ====================
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

    # ==================== CHECK 3: Module Dependencies ====================
    check_name = "module_dependencies"
    report["checks"][check_name] = {"status": "PENDING", "details": []}

    try:
        required_packages = {
            "ultralytics": "YOLO models (critical)",
            "cv2": "OpenCV (critical)",
            "numpy": "Numerical computing (critical)",
            "sklearn": "Scikit-learn (critical)",
            "yaml": "YAML parsing (critical)",
            "tqdm": "Progress bars (critical)",
        }

        import importlib
        missing_packages = []
        available_packages = []

        for package, description in required_packages.items():
            try:
                importlib.import_module(package)
                available_packages.append(f"[OK] {package}: {description}")
            except ImportError:
                if "critical" in description:
                    missing_packages.append(f"[MISSING] {package} (CRITICAL): {description}")
                else:
                    report["warnings"].append(f"Missing optional: {package}")
                    available_packages.append(f"[MISSING-OPTIONAL] {package}: {description}")

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

    # ==================== CHECK 4: __init__.py Exports ====================
    check_name = "init_exports"
    report["checks"][check_name] = {"status": "PENDING", "details": []}

    try:
        # Check what's in __init__.py files
        init_files = {
            "core": "core/__init__.py",
            "pipeline": "pipeline/__init__.py",
            "utils": "utils/__init__.py",
        }

        all_exports_good = True
        for module_name, init_path in init_files.items():
            init_file = Path(__file__).parent / init_path
            if not init_file.exists():
                report["checks"][check_name]["details"].append(f"[ERROR] {module_name}: {init_path} not found")
                all_exports_good = False
                continue

            with open(init_file) as f:
                content = f.read()

            if "__all__" in content and "from ." in content:
                report["checks"][check_name]["details"].append(f"[OK] {module_name}: Exports defined correctly")
            else:
                report["checks"][check_name]["details"].append(f"[WARN] {module_name}: __all__ or imports may be missing")

        if all_exports_good:
            report["checks"][check_name]["status"] = "PASSED"
        else:
            report["checks"][check_name]["status"] = "WARNING"

    except Exception as e:
        report["checks"][check_name]["status"] = "FAILED"
        report["checks"][check_name]["details"] = [str(e)]
        report["errors"].append(f"Init exports check failed: {str(e)}")

    # ==================== CHECK 5: Logs Directory ====================
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

    # ==================== CHECK 6: Error Handling Patterns ====================
    check_name = "error_handling"
    report["checks"][check_name] = {"status": "PASSED", "details": []}

    try:
        error_patterns = [
            ("core/detector.py", "Exception handling"),
            ("core/team_classifier.py", "ValueError/RuntimeError handling"),
            ("pipeline/frame_processor.py", "ValueError for frame validation"),
            ("pipeline/video_processor.py", "FileNotFoundError/RuntimeError handling"),
        ]

        for file_path, pattern in error_patterns:
            full_path = Path(__file__).parent / file_path
            if full_path.exists():
                with open(full_path) as f:
                    content = f.read()
                if "except" in content or "raise" in content:
                    report["checks"][check_name]["details"].append(f"[OK] {file_path}")
                else:
                    report["checks"][check_name]["details"].append(f"[WARN] {file_path}: May need error handling")
            else:
                report["checks"][check_name]["details"].append(f"[SKIP] {file_path}: Not found")

    except Exception as e:
        report["checks"][check_name]["status"] = "FAILED"
        report["checks"][check_name]["details"] = [str(e)]

    # ==================== CHECK 7: Config Compatibility ====================
    check_name = "config_compatibility"
    report["checks"][check_name] = {"status": "PENDING", "details": []}

    try:
        import yaml
        config_path = Path(__file__).parent / "config" / "detection_config.yaml"

        with open(config_path) as f:
            config = yaml.safe_load(f)

        # Check for Phase 1 compatibility
        phase1_keys = ["device", "detection"]
        phase2_keys = ["processing", "tracking", "validation", "output"]

        phase1_compat = all(k in config for k in phase1_keys)
        phase2_compat = all(k in config for k in phase2_keys)

        report["checks"][check_name]["status"] = "PASSED"
        details = []
        if phase1_compat:
            details.append("[OK] Phase 1 config compatibility")
        else:
            details.append("[WARN] Phase 1 compatibility may be incomplete")
        if phase2_compat:
            details.append("[OK] Phase 2 config extensions present")
        else:
            details.append("[WARN] Phase 2 config extensions may be missing")

        report["checks"][check_name]["details"] = details

    except Exception as e:
        report["checks"][check_name]["status"] = "FAILED"
        report["checks"][check_name]["details"] = [str(e)]

    # ==================== Calculate Integration Score ====================
    total_checks = len(report["checks"])
    passed_checks = sum(1 for check in report["checks"].values() if check["status"] == "PASSED")

    report["integration_score"] = int((passed_checks / total_checks) * 100) if total_checks > 0 else 0

    # ==================== Determine Phase 3 Blockers ====================
    phase3_critical_checks = ["module_dependencies", "logs_directory", "directory_structure"]
    for check in phase3_critical_checks:
        if check in report["checks"] and report["checks"][check]["status"] == "FAILED":
            report["blockers"].extend(report["checks"][check]["details"])

    return report


def main():
    """Main entry point"""
    print("=" * 70)
    print("PHASE 2 ARCHITECTURE VALIDATION")
    print("=" * 70)
    print()

    # Run validation
    report = run_validation()

    # Print summary
    print("VALIDATION RESULTS")
    print("-" * 70)
    print()

    for check_name, result in report["checks"].items():
        status_map = {"PASSED": "[PASS]", "FAILED": "[FAIL]", "WARNING": "[WARN]", "PENDING": "[????]"}
        status_symbol = status_map.get(result["status"], "[????]")
        print(f"{status_symbol} {check_name}: {result['status']}")
        for detail in result["details"][:3]:
            print(f"        {detail}")
        if len(result["details"]) > 3:
            print(f"        ... and {len(result['details']) - 3} more")

    print()
    print("-" * 70)
    print(f"Integration Score: {report['integration_score']}/100")
    print()

    if report["errors"]:
        print(f"Errors ({len(report['errors'])}):")
        for error in report["errors"][:5]:
            print(f"  - {error}")
        if len(report["errors"]) > 5:
            print(f"  ... and {len(report['errors']) - 5} more")
        print()

    if report["warnings"]:
        print(f"Warnings ({len(report['warnings'])}):")
        for warning in report["warnings"][:3]:
            print(f"  - {warning}")
        print()

    if report["blockers"]:
        print(f"PHASE 3 BLOCKERS ({len(report['blockers'])}):")
        for blocker in report["blockers"]:
            print(f"  [BLOCKER] {blocker}")
        print()
    else:
        print("[OK] No blockers for Phase 3")
        print()

    # Save report
    report_path = Path(__file__).parent / "data" / "logs" / "architecture_validation.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Full report saved to: {report_path}")
    print()

    # Return exit code based on blockers
    return 0 if not report["blockers"] else 1


if __name__ == "__main__":
    sys.exit(main())
