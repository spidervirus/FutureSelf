# Installation Guide for Future Self Backend

## Python Version

This project requires Python 3.11.9 as specified in `.python-version`.

## Optimized Installation Process

To avoid dependency resolution backtracking and speed up installation, the requirements have been separated into functional groups. You can install them in the recommended order or only install what you need.

### Option 1: Install Everything at Once

```bash
pip install -r requirements-all.txt
```

### Option 2: Install by Groups (Recommended for Development)

Install in this order to minimize dependency conflicts:

```bash
# 1. Core dependencies (lightweight, minimal conflicts)
pip install -r requirements-core.txt

# 2. Astrology dependencies (lightweight)
pip install -r requirements-astrology.txt

# 3. Data manipulation and visualization
pip install -r requirements-data.txt

# 4. Audio processing
pip install -r requirements-audio.txt

# 5. NLP and ML (heaviest dependencies, install last)
pip install -r requirements-nlp.txt
```

### Option 3: Minimal Installation

If you only need specific functionality, install only what you need:

```bash
# Always install core dependencies
pip install -r requirements-core.txt

# Then install only what you need for your specific task
pip install -r requirements-audio.txt  # If working on audio features
# OR
pip install -r requirements-nlp.txt    # If working on NLP features
# etc.
```

## Post-Installation Steps

After installing the dependencies:

1. Download the spaCy model:
   ```bash
   python -m spacy download en_core_web_sm
   ```

2. Create a `.env` file based on `.env.example`

## Troubleshooting

If you encounter installation issues:

1. Try using a fresh virtual environment:
   ```bash
   python -m venv fresh_venv
   source fresh_venv/bin/activate  # On Windows: fresh_venv\Scripts\activate
   ```

2. For ML libraries, consider using pre-compiled wheels:
   ```bash
   pip install torch==2.1.0 --extra-index-url https://download.pytorch.org/whl/cpu  # For CPU-only
   ```

3. For persistent dependency conflicts, try installing with:
   ```bash
   pip install --no-cache-dir -r requirements-all.txt
   ```

4. On macOS, you might need to install additional system dependencies for audio libraries:
   ```bash
   brew install ffmpeg portaudio
   ```