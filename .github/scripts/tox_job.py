"""
Generate the appropriate tox job name to match the current
version of python available. For use with Github Actions
or via `tox $(pythonX.Y scripts/tox_job.py)`.

Example:

    $ python3.8 tox_job.py
    py38

"""

import sys


major, minor, *_ = sys.version_info
print(f"py{major}{minor}")
