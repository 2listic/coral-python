# coral-python
Coral for python libraries

## Installation

### Prerequisites
- Python 3.6+
- [uv](https://github.com/astral-sh/uv) installed 

### Setup

```bash
# Create virtual environment
uv venv

# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows

# Install dependencies
uv pip install -r requirements.txt
```

### Managing Dependencies

**Install a new package:**
```bash
uv pip install <package-name>
echo "<package-name>" >> requirements.in  # Track what YOU installed
uv pip freeze > requirements.txt  # Lock all versions
```

**Update all packages:**
```bash
uv pip install --upgrade -r requirements.txt
uv pip freeze > requirements.txt
```