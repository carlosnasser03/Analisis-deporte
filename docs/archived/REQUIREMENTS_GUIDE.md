# Scout AI Analytics - Requirements and Dependencies Guide

## Overview

This document provides comprehensive information about all Python dependencies required to run the Scout AI Analytics football/soccer analysis system.

**Project:** Scout AI Analytics - Football/Soccer Video Analysis System  
**Analysis Date:** 2026-07-06  
**Python Version:** 3.8+ (tested on 3.9, 3.10, 3.11)

---

## Quick Start

### Installation (Production)
```bash
pip install -r requirements.txt
```

### Installation (Development)
```bash
pip install -r requirements-dev.txt
```

### Initial Setup
```bash
python 1_preparar.py
```

---

## Dependencies Breakdown

### Core Vision & Detection (12 packages)

| Package | Version | Purpose | Required |
|---------|---------|---------|----------|
| `ultralytics` | >=8.0.0,<9.0.0 | YOLO object detection | ✓ Yes |
| `opencv-python` | >=4.8.0,<5.0.0 | Computer vision processing | ✓ Yes |
| `supervision` | ==0.29.0 | Detection utilities & ByteTrack | ✓ Yes |

### Data Science & Analysis (4 packages)

| Package | Version | Purpose | Required |
|---------|---------|---------|----------|
| `numpy` | >=1.24.0,<2.0.0 | Numerical computing | ✓ Yes |
| `pandas` | >=2.0.0,<3.0.0 | Data structures & analysis | ✓ Yes |
| `scipy` | >=1.10.0,<2.0.0 | Scientific computing | ✓ Yes |
| `scikit-learn` | >=1.3.0,<2.0.0 | Machine learning (KMeans) | ✓ Yes |

### Configuration & Utilities (4 packages)

| Package | Version | Purpose | Required |
|---------|---------|---------|----------|
| `pyyaml` | >=6.0,<7.0 | YAML config parsing | ✓ Yes |
| `tqdm` | >=4.66.0,<5.0.0 | Progress bars | ✗ Optional |
| `Pillow` | >=10.0.0,<11.0.0 | Image processing | ✗ Optional |
| `psutil` | >=5.9.0,<6.0.0 | System monitoring | ✗ Optional |

### OCR (Optical Character Recognition) (2 packages)

| Package | Version | Purpose | Required |
|---------|---------|---------|----------|
| `paddleocr` | >=2.7.0.3 | Jersey number detection | ✗ Optional |
| `easyocr` | >=1.6.0,<2.0.0 | OCR fallback | ✗ Optional |

### Report Generation & Visualization (2 packages)

| Package | Version | Purpose | Required |
|---------|---------|---------|----------|
| `reportlab` | >=4.0.0,<5.0.0 | PDF generation | ✗ Optional |
| `plotly` | >=5.17.0,<6.0.0 | Interactive charts | ✗ Optional |

### Inference Optimization (3 packages)

| Package | Version | Purpose | Required |
|---------|---------|---------|----------|
| `openvino` | >=2023.0.0,<2025.0.0 | Intel optimization | ✗ Optional |
| `onnx` | >=1.14.0,<2.0.0 | Model format | ✗ Optional |
| `gdown` | >=4.7.0,<5.0.0 | Drive downloads | ✗ Optional |

### Local Packages (1 package)

| Package | Source | Purpose |
|---------|--------|---------|
| `sports` | ./sports-main | Roboflow soccer utilities |

---

## Total Package Count

- **Production Dependencies:** 19 packages
- **Development Dependencies:** 9 additional packages
- **Local Packages:** 1 (sports)

---

## Installation Modes

### Mode 1: Production Only (Minimal)
```bash
pip install -r requirements.txt
```
**Use Case:** Running the analysis pipeline in production environments.

### Mode 2: Development (Full)
```bash
pip install -r requirements-dev.txt
```
**Includes:** Everything from `requirements.txt` PLUS development tools.

### Mode 3: Custom Installation
Pick and choose from specific package categories:

```bash
# Core vision only
pip install ultralytics opencv-python supervision==0.29.0 numpy pandas scipy scikit-learn pyyaml

# Add reporting
pip install reportlab plotly

# Add OCR
pip install paddleocr easyocr

# Add optimization
pip install openvino onnx gdown
```

---

## Setup Sequence

### Step 1: Create Virtual Environment (Recommended)
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Run Initial Setup
```bash
python 1_preparar.py
```
This script will:
1. Install any missing dependencies
2. Download the Roboflow `sports` package
3. Download the YOLO models
4. Download test videos
5. Export models to OpenVINO format

### Step 4: Verify Installation
```bash
python scripts/0_validate.py
```

### Step 5: Run Analysis
```bash
python 2_analizar.py [video_file] [options]
```

---

## Version Compatibility Matrix

### Tested Combinations
| Python | NumPy | Pandas | UltraLytics | Supervision | OpenCV | Status |
|--------|-------|--------|-------------|-------------|--------|--------|
| 3.9 | 1.24+ | 2.0+ | 8.0+ | 0.29.0 | 4.8+ | ✓ Verified |
| 3.10 | 1.24+ | 2.0+ | 8.0+ | 0.29.0 | 4.8+ | ✓ Verified |
| 3.11 | 1.24+ | 2.0+ | 8.0+ | 0.29.0 | 4.8+ | ✓ Verified |

### Known Breaking Changes
- **NumPy 2.x**: Uses different memory layout, generally compatible
- **Pandas 3.x**: CSV operations compatible, monitor for subtle changes
- **Pillow 12.x**: New features added, backward compatible

---

## System Requirements

### Hardware
- **Minimum:** 4GB RAM, modern processor
- **Recommended:** 8GB+ RAM, Intel processor (for OpenVINO optimization)
- **GPU:** Optional (NVIDIA CUDA or Intel Arc)

### Disk Space
- Python packages: ~2-3 GB
- YOLO models: ~500 MB
- OCR models: ~200 MB (downloaded on first use)
- Test videos: ~500 MB

### Operating Systems
- ✓ Windows 10/11
- ✓ macOS (Intel/Apple Silicon)
- ✓ Linux (Ubuntu 18.04+)

---

## Optional Features & When to Install

### PDF Report Generation
```bash
pip install reportlab>=4.0.0
```
**Install if:** You need to generate PDF match reports.

### Interactive Dashboards
```bash
pip install plotly>=5.17.0
```
**Install if:** You need to create interactive statistics dashboards.

### Jersey Number Detection
```bash
pip install paddleocr>=2.7.0.3
```
**Install if:** You need to detect and recognize jersey numbers.

### CPU/iGPU Optimization
```bash
pip install openvino>=2023.0.0
```
**Install if:** You have an Intel processor and want optimized inference.

---

## Troubleshooting

### Issue: Import Error for `sports`
**Solution:**
```bash
python 1_preparar.py
# or manually:
pip install ./sports-main
```

### Issue: CUDA/GPU not found
**Solution:** This is expected on CPU systems. UltraLytics will use CPU automatically.

### Issue: PaddleOCR download fails
**Solution:** Use EasyOCR as fallback:
```bash
pip install easyocr
# The code automatically falls back if paddleocr fails
```

### Issue: ReportLab fonts missing
**Solution:**
```bash
pip install reportlab[fonts]
```

### Issue: OpenVINO export fails
**Solution:** OpenVINO is optional. Skip if not needed:
```bash
# Uninstall
pip uninstall openvino
# The system will use .pt models instead
```

---

## Version Management

### How to Update All Packages
```bash
pip install --upgrade -r requirements.txt
```

### How to Update Specific Package
```bash
pip install --upgrade ultralytics
pip install --upgrade 'numpy>=1.24.0'
```

### How to Lock Versions (Reproducibility)
```bash
pip freeze > requirements-lock.txt
# Later:
pip install -r requirements-lock.txt
```

---

## Development Workflow

### Code Quality Checks
```bash
# Format code
black core/ pipeline/ utils/

# Check linting
flake8 core/ pipeline/ utils/

# Type checking
mypy core/ pipeline/ utils/

# Sort imports
isort core/ pipeline/ utils/
```

### Running Tests
```bash
# Run all tests
pytest tests/

# With coverage
pytest tests/ --cov=core --cov=pipeline --cov=utils

# Verbose output
pytest tests/ -v
```

---

## Dependency Analysis Details

Full dependency analysis available in:
- `data/logs/requirements_analysis.json` - Complete package documentation
- `data/logs/installed_versions.json` - Current installation snapshot

---

## License & Attribution

### Key Dependencies
- **UltraLytics:** [AGPL-3.0](https://github.com/ultralytics/ultralytics)
- **OpenCV:** [Apache 2.0](https://github.com/opencv/opencv)
- **Supervision:** [MIT](https://github.com/roboflow/supervision)
- **Scikit-Learn:** [BSD 3-Clause](https://github.com/scikit-learn/scikit-learn)
- **NumPy/Pandas:** [BSD 3-Clause](https://numpy.org)
- **Plotly:** [MIT](https://github.com/plotly/plotly.py)
- **ReportLab:** [BSD 3-Clause](https://www.reportlab.com)

---

## Getting Help

### For Installation Issues
1. Check Python version: `python --version`
2. Verify pip version: `pip --version`
3. Check venv activation: `which python` (should show venv path)
4. Review `data/logs/installed_versions.json` for compatibility

### For Dependency Conflicts
1. Use a fresh virtual environment
2. Install requirements.txt in order
3. Check OS-specific issues (Windows vs Linux vs macOS)

### For Version Questions
See `data/logs/requirements_analysis.json` for detailed version rationale.

---

## Summary Table

| Aspect | Value |
|--------|-------|
| Total Packages | 28 |
| Core/Required | 9 |
| Optional | 10 |
| Development | 9 |
| Installation Size | ~2-3 GB |
| Python Requirement | 3.8+ |
| Main Framework | UltraLytics 8.0+ |
| Core Data Libs | NumPy, Pandas, SciPy, Scikit-Learn |
| Report Generation | ReportLab + Plotly |
| OCR Options | PaddleOCR + EasyOCR |
| Optimization | OpenVINO |

---

**Last Updated:** 2026-07-06  
**Analyzer:** Scout AI Dependency Tool  
**Version:** 1.0
