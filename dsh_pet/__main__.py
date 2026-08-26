"""Allow ``python -m dsh_pet`` to launch the pet."""

import sys

from .main import main

if __name__ == "__main__":
    sys.exit(main())
