# packages/implr_validate/implr_validate/__main__.py
# Supports `python -m implr_validate`. The package is installed, so no sys.path
# manipulation is needed here — that was only required by the retired
# runnable-directory form `python scripts/implr_validate`.
import sys

from implr_validate.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
