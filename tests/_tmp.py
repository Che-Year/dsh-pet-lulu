"""Test helpers: workspace-local temporary directories.

The sandbox this test suite may run under denies writes to the system TEMP
directory and to directories created by ``tempfile.mkdtemp``, so tests
create and clean up their own directories inside the workspace instead.
"""

import os
import shutil
import uuid
from contextlib import contextmanager

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
TMP_ROOT = os.path.join(TESTS_DIR, "tmp-work")


def make_tmp_dir() -> str:
    os.makedirs(TMP_ROOT, exist_ok=True)
    path = os.path.join(TMP_ROOT, "t-" + uuid.uuid4().hex[:10])
    os.makedirs(path)
    return path


@contextmanager
def tmp_dir():
    path = make_tmp_dir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
