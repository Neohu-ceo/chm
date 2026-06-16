"""Analysis modules for codebase health metrics."""

from .hotspots import HotspotAnalyzer
from .authors import AuthorAnalyzer
from .pulse import PulseAnalyzer
from .complexity import ComplexityAnalyzer
from .dead_code import DeadCodeAnalyzer
from .dependencies import DependencyAnalyzer
from .test_coverage import TestCoverageAnalyzer
from .duplication import DuplicationAnalyzer

__all__ = [
    "HotspotAnalyzer",
    "AuthorAnalyzer",
    "PulseAnalyzer",
    "ComplexityAnalyzer",
    "DeadCodeAnalyzer",
    "DependencyAnalyzer",
    "TestCoverageAnalyzer",
    "DuplicationAnalyzer",
]
