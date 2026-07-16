# scripts/implr_validate/__main__.py
# Support the runnable-directory form `python scripts/implr_validate <mode>`:
# executing a directory runs this file as the top-level `__main__` module with no
# parent package, so relative imports fail. Put the package parent (scripts/) on
# sys.path and import the package absolutely.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from implr_validate.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
