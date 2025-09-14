#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="cpp_ufgsg"
YML_FILE="environment.yml"

if [[ ! -f "pyproject.toml" || ! -d "src/cpp" ]]; then
  echo "Run this script from the repository root where pyproject.toml and src/ exist."
  exit 1
fi

# try to locate conda if not on PATH
if ! command -v conda >/dev/null 2>&1; then
  if [[ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]]; then
    # shellcheck disable=SC1091
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
  elif [[ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]]; then
    # shellcheck disable=SC1091
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
  fi
fi

if ! command -v conda >/dev/null 2>&1; then
  echo "Conda not found. Install Miniconda or Anaconda and try again."
  exit 1
fi

# create environment
if conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  echo "Updating existing environment: $ENV_NAME"
  conda env update -n "$ENV_NAME" -f "$YML_FILE"
else
  echo "Creating environment: $ENV_NAME"
  conda env create -f "$YML_FILE"
fi

# editable install of this package
echo "Installing this repo into $ENV_NAME (editable)..."
conda run -n "$ENV_NAME" pip install -e .

# verify core versions
echo "Verifying versions..."
conda run -n "$ENV_NAME" python - <<'PY'
import sys, numpy, shapely, matplotlib
from shapely.geos import geos_version_string
print("python", sys.version.split()[0])
print("numpy", numpy.__version__)
print("shapely", shapely.__version__)
print("matplotlib", matplotlib.__version__)
print("geos", geos_version_string)
PY

echo
echo "Done. Activate the environment:"
echo "  conda activate $ENV_NAME"

