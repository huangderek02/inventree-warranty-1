# warranty/__init__.py
# Keep this lightweight; do not import Django / InvenTree here.
PLUGIN_VERSION = "0.2.0"

from .core import Warranty  # OK: core only uses plugin mixins at runtime

__all__ = ["Warranty", "PLUGIN_VERSION"]
