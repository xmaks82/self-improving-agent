"""Bundled skills registration."""

from .commit import register as _reg_commit
from .review import register as _reg_review
from .simplify import register as _reg_simplify
from .debug_skill import register as _reg_debug


def init_bundled_skills():
    """Register all bundled skills. Call once at startup."""
    _reg_commit()
    _reg_review()
    _reg_simplify()
    _reg_debug()
