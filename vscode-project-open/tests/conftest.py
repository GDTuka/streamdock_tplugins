"""Add the plugin root to sys.path so `src.*` imports work in tests."""

import os
import sys

_PLUGIN_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)
