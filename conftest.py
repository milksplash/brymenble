# Make the SDK (src/) and the sample app (examples/) importable regardless of
# how pytest is invoked (no editable install required).
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
for _dir in (os.path.join(_ROOT, "src"), os.path.join(_ROOT, "examples")):
    if _dir not in sys.path:
        sys.path.insert(0, _dir)

