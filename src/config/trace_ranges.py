"""
Trace Range Configuration for Assay Visualization

This module provides configuration classes and presets for customizable trace range
visualization in assay data. Users can define custom statistical classification ranges
with different boundary formula types and color schemes.

Key Features:
    - Multiple boundary formula types (direct PPM, mean multipliers, std dev, percentiles)
    - Predefined presets (Industry Standard, Conservative, Aggressive)
    - Custom range configuration support
    - Validation for range boundaries

Author: Needle Digital
Contact: divyansh@needle-digital.com
"""

from enum import Enum
from typing import List, Tuple, Optional
from qgis.PyQt.QtGui import QColor


class RangeType(Enum):
    """Types of boundary formulas for range configuration."""
    DIRECT_PPM = "Direct PPM"
    MEAN_MULTIPLIER = "Mean ×"
    STDDEV_MULTIPLIER = "StdDev ×"
    PERCENTILE = "Percentile"


class BoundaryFormula:
    """Represents a boundary formula for trace range calculation.

    A boundary can be defined as:
    - Direct PPM value (e.g., 500 ppm)
    - Mean multiplier (e.g., Mean × 2)
    - Standard deviation multiplier (e.g., Mean + StdDev × 1.5)
    - Percentile (e.g., 95th percentile)
    """

    def __init__(self, formula_type: RangeType, value: float):
        """
        Initialize boundary formula.

        Args:
            formula_type: Type of formula
            value: Numeric value for the formula
                - DIRECT_PPM: actual PPM value (e.g., 500.0)
                - MEAN_MULTIPLIER: multiplier (e.g., 2.0 for Mean × 2)
                - STDDEV_MULTIPLIER: multiplier (e.g., 1.0 for Mean + 1σ)
                - PERCENTILE: percentile value 0-100 (e.g., 95.0 for 95th percentile)
        """
        self.formula_type = formula_type
        self.value = value

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'type': self.formula_type.name,
            'value': self.value
        }

    @staticmethod
    def from_dict(data: dict) -> 'BoundaryFormula':
        """Create from dictionary."""
        return BoundaryFormula(
            RangeType[data['type']],
            float(data['value'])
        )

    def __str__(self) -> str:
        """String representation for display."""
        if self.formula_type == RangeType.DIRECT_PPM:
            return f"{self.value:.1f} ppm"
        elif self.formula_type == RangeType.MEAN_MULTIPLIER:
            return f"Mean × {self.value:.1f}"
        elif self.formula_type == RangeType.STDDEV_MULTIPLIER:
            return f"Mean + {self.value:.1f}σ"
        elif self.formula_type == RangeType.PERCENTILE:
            return f"{self.value:.0f}th %ile"
        return str(self.value)


class TraceRange:
    """Represents a single trace range with name, color, and boundaries."""

    def __init__(
        self,
        name: str,
        color: QColor,
        lower_boundary: BoundaryFormula,
        upper_boundary: BoundaryFormula
    ):
        """
        Initialize trace range.

        Args:
            name: Display name for the range (e.g., "Background Low")
            color: QColor for rendering
            lower_boundary: Lower boundary formula
            upper_boundary: Upper boundary formula
        """
        self.name = name
        self.color = color
        self.lower_boundary = lower_boundary
        self.upper_boundary = upper_boundary

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'name': self.name,
            'color': self.color.name(),
            'lower': self.lower_boundary.to_dict(),
            'upper': self.upper_boundary.to_dict()
        }

    @staticmethod
    def from_dict(data: dict) -> 'TraceRange':
        """Create from dictionary."""
        return TraceRange(
            data['name'],
            QColor(data['color']),
            BoundaryFormula.from_dict(data['lower']),
            BoundaryFormula.from_dict(data['upper'])
        )


class TraceRangeConfiguration:
    """Complete trace range configuration with multiple ranges."""

    def __init__(self, ranges: List[TraceRange], preset_name: str = "Custom"):
        """
        Initialize trace range configuration.

        Args:
            ranges: List of TraceRange objects
            preset_name: Name of the preset or "Custom"
        """
        self.ranges = ranges
        self.preset_name = preset_name

    def get_breakpoints_count(self) -> int:
        """Get number of breakpoints needed (ranges + 1)."""
        return len(self.ranges) + 1

    def get_names(self) -> List[str]:
        """Get list of range names."""
        return [r.name for r in self.ranges]

    def get_colors(self) -> List[QColor]:
        """Get list of range colors."""
        return [r.color for r in self.ranges]

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'preset_name': self.preset_name,
            'ranges': [r.to_dict() for r in self.ranges]
        }

    @staticmethod
    def from_dict(data: dict) -> 'TraceRangeConfiguration':
        """Create from dictionary."""
        return TraceRangeConfiguration(
            [TraceRange.from_dict(r) for r in data['ranges']],
            data.get('preset_name', 'Custom')
        )


# ============================================================================
# PRESET CONFIGURATIONS
# ============================================================================

def get_industry_standard_preset() -> TraceRangeConfiguration:
    """
    Industry Standard preset - current default implementation.

    6 ranges based on mean ± σ and high percentiles:
    - Background Low: min → mean
    - Normal: mean → mean + 1σ
    - Elevated: mean + 1σ → mean + 2σ
    - Anomalous: mean + 2σ → 95%
    - High Anomaly: 95% → 98%
    - Ore Grade: 98% → 99%
    """
    ranges = [
        TraceRange(
            "Background Low (< Mean)",
            QColor(25, 118, 210),  # Dark Blue
            BoundaryFormula(RangeType.DIRECT_PPM, 0.0),  # Will be replaced with actual min
            BoundaryFormula(RangeType.MEAN_MULTIPLIER, 1.0)
        ),
        TraceRange(
            "Normal (Mean to +1σ)",
            QColor(100, 181, 246),  # Light Blue
            BoundaryFormula(RangeType.MEAN_MULTIPLIER, 1.0),
            BoundaryFormula(RangeType.STDDEV_MULTIPLIER, 1.0)
        ),
        TraceRange(
            "Elevated (+1σ to +2σ)",
            QColor(255, 235, 59),  # Yellow
            BoundaryFormula(RangeType.STDDEV_MULTIPLIER, 1.0),
            BoundaryFormula(RangeType.STDDEV_MULTIPLIER, 2.0)
        ),
        TraceRange(
            "Anomalous (+2σ to 95%)",
            QColor(255, 152, 0),  # Orange
            BoundaryFormula(RangeType.STDDEV_MULTIPLIER, 2.0),
            BoundaryFormula(RangeType.PERCENTILE, 95.0)
        ),
        TraceRange(
            "High Anomaly (95-98%)",
            QColor(244, 67, 54),  # Red
            BoundaryFormula(RangeType.PERCENTILE, 95.0),
            BoundaryFormula(RangeType.PERCENTILE, 98.0)
        ),
        TraceRange(
            "Ore Grade (98-99%)",
            QColor(156, 39, 176),  # Purple
            BoundaryFormula(RangeType.PERCENTILE, 98.0),
            BoundaryFormula(RangeType.PERCENTILE, 99.0)
        )
    ]

    return TraceRangeConfiguration(ranges, "Industry Standard")


def get_conservative_preset() -> TraceRangeConfiguration:
    """
    Conservative preset - more ranges with tighter intervals.

    8 ranges with finer granularity:
    - Very Low: min → mean - 0.5σ
    - Low: mean - 0.5σ → mean
    - Normal: mean → mean + 0.5σ
    - Elevated: mean + 0.5σ → mean + 1σ
    - Moderately Anomalous: mean + 1σ → mean + 1.5σ
    - Anomalous: mean + 1.5σ → mean + 2σ
    - High Anomaly: mean + 2σ → 95%
    - Very High: 95% → 99%
    """
    ranges = [
        TraceRange(
            "Very Low",
            QColor(200, 230, 255),  # Very Light Blue
            BoundaryFormula(RangeType.DIRECT_PPM, 0.0),
            BoundaryFormula(RangeType.STDDEV_MULTIPLIER, -0.5)
        ),
        TraceRange(
            "Low",
            QColor(100, 200, 255),  # Light Blue
            BoundaryFormula(RangeType.STDDEV_MULTIPLIER, -0.5),
            BoundaryFormula(RangeType.MEAN_MULTIPLIER, 1.0)
        ),
        TraceRange(
            "Normal",
            QColor(50, 150, 255),  # Blue
            BoundaryFormula(RangeType.MEAN_MULTIPLIER, 1.0),
            BoundaryFormula(RangeType.STDDEV_MULTIPLIER, 0.5)
        ),
        TraceRange(
            "Elevated",
            QColor(100, 255, 100),  # Light Green
            BoundaryFormula(RangeType.STDDEV_MULTIPLIER, 0.5),
            BoundaryFormula(RangeType.STDDEV_MULTIPLIER, 1.0)
        ),
        TraceRange(
            "Moderately Anomalous",
            QColor(255, 255, 0),  # Yellow
            BoundaryFormula(RangeType.STDDEV_MULTIPLIER, 1.0),
            BoundaryFormula(RangeType.STDDEV_MULTIPLIER, 1.5)
        ),
        TraceRange(
            "Anomalous",
            QColor(255, 200, 0),  # Light Orange
            BoundaryFormula(RangeType.STDDEV_MULTIPLIER, 1.5),
            BoundaryFormula(RangeType.STDDEV_MULTIPLIER, 2.0)
        ),
        TraceRange(
            "High Anomaly",
            QColor(255, 100, 0),  # Orange
            BoundaryFormula(RangeType.STDDEV_MULTIPLIER, 2.0),
            BoundaryFormula(RangeType.PERCENTILE, 95.0)
        ),
        TraceRange(
            "Very High",
            QColor(200, 0, 0),  # Dark Red
            BoundaryFormula(RangeType.PERCENTILE, 95.0),
            BoundaryFormula(RangeType.PERCENTILE, 99.0)
        )
    ]

    return TraceRangeConfiguration(ranges, "Conservative")


def get_aggressive_preset() -> TraceRangeConfiguration:
    """
    Aggressive preset - fewer ranges focused on anomalies.

    4 ranges emphasizing high-value anomalies:
    - Background: min → mean + 2σ
    - Elevated: mean + 2σ → 95%
    - High Grade: 95% → 98%
    - Ore Grade: 98% → 99%
    """
    ranges = [
        TraceRange(
            "Background",
            QColor(150, 150, 150),  # Gray
            BoundaryFormula(RangeType.DIRECT_PPM, 0.0),
            BoundaryFormula(RangeType.STDDEV_MULTIPLIER, 2.0)
        ),
        TraceRange(
            "Elevated",
            QColor(255, 235, 59),  # Yellow
            BoundaryFormula(RangeType.STDDEV_MULTIPLIER, 2.0),
            BoundaryFormula(RangeType.PERCENTILE, 95.0)
        ),
        TraceRange(
            "High Grade",
            QColor(255, 152, 0),  # Orange
            BoundaryFormula(RangeType.PERCENTILE, 95.0),
            BoundaryFormula(RangeType.PERCENTILE, 98.0)
        ),
        TraceRange(
            "Ore Grade",
            QColor(156, 39, 176),  # Purple
            BoundaryFormula(RangeType.PERCENTILE, 98.0),
            BoundaryFormula(RangeType.PERCENTILE, 99.0)
        )
    ]

    return TraceRangeConfiguration(ranges, "Aggressive")


def get_preset_by_name(name: str) -> TraceRangeConfiguration:
    """
    Get preset configuration by name.

    Args:
        name: Preset name ("Industry Standard", "Conservative", "Aggressive")

    Returns:
        TraceRangeConfiguration for the preset
    """
    presets = {
        "Industry Standard": get_industry_standard_preset,
        "Conservative": get_conservative_preset,
        "Aggressive": get_aggressive_preset
    }

    if name in presets:
        return presets[name]()
    else:
        # Default to Industry Standard
        return get_industry_standard_preset()


def get_available_presets() -> List[str]:
    """Get list of available preset names."""
    return ["Industry Standard", "Conservative", "Aggressive"]
