"""Standalone, local Qalculate calculation service; no Playpen dependencies."""

from .engine import CalculationError, QalculateEngine

__all__ = ["CalculationError", "QalculateEngine"]
__version__ = "0.1.0"
