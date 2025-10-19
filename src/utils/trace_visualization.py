"""
Drill Hole Trace Visualization Utilities

This module provides specialized functions for creating trace line visualizations
for assay data with depth intervals. It handles the conversion of point-based
assay data into linestring geometries that visualize depth intervals.

Key Features:
    - Group assay samples by drill hole (collar location)
    - Create vertical trace lines showing depth intervals
    - Scale-dependent visibility (show traces only when zoomed in)
    - Graduated color rendering based on element concentration
    - Multi-element support with offset stacking

Author: Needle Digital
Contact: divyansh@needle-digital.com
"""

from typing import List, Dict, Any, Tuple, Optional
from qgis.core import (
    QgsPointXY, QgsGeometry, QgsFeature, QgsField, QgsVectorLayer,
    QgsGraduatedSymbolRenderer, QgsRendererRange, QgsLineSymbol,
    QgsProject, QgsLayerTreeGroup, QgsCoordinateReferenceSystem
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor


def group_by_collar(data: List[Dict[str, Any]]) -> Dict[Tuple[float, float], List[Dict]]:
    """
    Group assay samples by unique collar location (lat, lon).

    Args:
        data: List of assay records with lat/lon coordinates

    Returns:
        Dictionary mapping (lat, lon) tuples to list of samples at that location
    """
    holes = {}
    for record in data:
        # Support both 'lat'/'lon' and 'latitude'/'longitude' field names
        lat = record.get('lat') or record.get('latitude', 0)
        lon = record.get('lon') or record.get('longitude', 0)

        # Round to 6 decimal places (~0.1m precision) for grouping
        lat = round(float(lat), 6)
        lon = round(float(lon), 6)
        key = (lat, lon)

        if key not in holes:
            holes[key] = []
        holes[key].append(record)

    return holes


def get_max_depth_from_data(data: List[Dict[str, Any]]) -> Optional[float]:
    """
    Extract maximum depth from data if available.

    Args:
        data: List of assay records

    Returns:
        Maximum depth value or None if not available
    """
    max_depths = []

    for record in data:
        # Try final_depth field first (max depth of hole)
        if 'final_depth' in record and record['final_depth'] is not None:
            try:
                max_depths.append(float(record['final_depth']))
            except (ValueError, TypeError):
                pass
        # Fallback to to_depth
        elif 'to_depth' in record and record['to_depth'] is not None:
            try:
                max_depths.append(float(record['to_depth']))
            except (ValueError, TypeError):
                pass

    return max(max_depths) if max_depths else None


def create_trace_line_geometry(
    record: Dict[str, Any],
    max_depth_global: Optional[float] = None,
    offset_scale: float = 500.0
) -> QgsGeometry:
    """
    Create LineString geometry for a single assay interval.

    The line extends horizontally from the collar location, with offset
    proportional to depth to create a side-view trace effect.

    Args:
        record: Assay record with lat/latitude, lon/longitude, from_depth, to_depth
        max_depth_global: Maximum depth in dataset (for proportional offset)
        offset_scale: Scale factor for offset calculation

    Returns:
        LineString geometry representing the interval
    """
    # Support both 'lat'/'lon' and 'latitude'/'longitude' field names
    lat = record.get('lat') or record.get('latitude', 0)
    lon = record.get('lon') or record.get('longitude', 0)
    from_depth = float(record.get('from_depth', 0))
    to_depth = float(record.get('to_depth', from_depth + 10))

    # Calculate midpoint depth for offset
    midpoint_depth = (from_depth + to_depth) / 2

    # Calculate offset magnitude for line length (longer lines for better visibility)
    if max_depth_global and max_depth_global > 0:
        # Proportional offset based on total depth (0.01 degrees ≈ 1.1 km)
        offset = midpoint_depth / max_depth_global * 0.01
    else:
        # Fixed scale offset (0.01 degrees ≈ 1.1 km at equator)
        offset = midpoint_depth / offset_scale * 0.01

    # Create line from collar at 30° left of vertical
    # 30° left of vertical means: 60° from horizontal
    # dx = -offset * sin(30°) = -offset * 0.5 (leftward)
    # dy = offset * cos(30°) = offset * 0.866 (upward)
    import math
    angle_rad = math.radians(30)
    dx = -offset * math.sin(angle_rad)  # Negative for leftward
    dy = offset * math.cos(angle_rad)   # Positive for northward (upward)

    start_point = QgsPointXY(lon, lat)
    end_point = QgsPointXY(lon + dx, lat + dy)

    return QgsGeometry.fromPolylineXY([start_point, end_point])


def evaluate_boundary_formula(
    formula,
    data_stats: Dict[str, float]
) -> float:
    """
    Evaluate a boundary formula to get numeric value.

    Args:
        formula: BoundaryFormula object
        data_stats: Dictionary with keys: 'mean', 'std_dev', 'min', 'max', 'percentiles'

    Returns:
        Numeric value for the boundary
    """
    from ..config.trace_ranges import RangeType

    if formula.formula_type == RangeType.DIRECT_PPM:
        return formula.value

    elif formula.formula_type == RangeType.MEAN_MULTIPLIER:
        return data_stats['mean'] * formula.value

    elif formula.formula_type == RangeType.STDDEV_MULTIPLIER:
        return data_stats['mean'] + (data_stats['std_dev'] * formula.value)

    elif formula.formula_type == RangeType.PERCENTILE:
        # Get percentile from precomputed percentiles dict
        percentiles = data_stats.get('percentiles', {})
        p_value = int(formula.value)
        if p_value in percentiles:
            return percentiles[p_value]
        else:
            # Fallback: approximate from available percentiles
            # Use max value if percentile not available
            return data_stats.get('max', 0.0)

    return 0.0


def calculate_data_statistics(data: List[Dict[str, Any]], value_field: str) -> Dict[str, float]:
    """
    Calculate statistical measures for data.

    Args:
        data: List of records
        value_field: Field name containing numeric values

    Returns:
        Dictionary with statistical measures
    """
    values = []
    for record in data:
        val = record.get(value_field)
        if val is not None:
            try:
                values.append(float(val))
            except (ValueError, TypeError):
                pass

    if not values or len(values) < 10:
        # Return default stats if insufficient data
        return {
            'min': 0.0,
            'max': 100.0,
            'mean': 50.0,
            'std_dev': 10.0,
            'percentiles': {50: 50.0, 75: 75.0, 90: 90.0, 95: 95.0, 98: 98.0, 99: 99.0}
        }

    # Sort values
    values.sort()
    n = len(values)

    # Calculate basic stats
    minimum = values[0]
    maximum = values[-1]
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / n
    std_dev = variance ** 0.5

    # Calculate percentiles
    percentiles = {}
    for p in [50, 75, 90, 95, 98, 99]:
        p_index = int(n * (p / 100.0))
        percentiles[p] = values[min(p_index, n - 1)]

    return {
        'min': minimum,
        'max': maximum,
        'mean': mean,
        'std_dev': std_dev,
        'percentiles': percentiles
    }


def calculate_trace_breakpoints(
    data: List[Dict[str, Any]],
    value_field: str,
    range_config=None
) -> List[float]:
    """
    Calculate breakpoints for trace visualization based on configuration.

    Args:
        data: List of records
        value_field: Field name containing numeric values
        range_config: TraceRangeConfiguration object (optional, uses industry standard if None)

    Returns:
        List of breakpoint values matching the range configuration
    """
    # Calculate data statistics
    stats = calculate_data_statistics(data, value_field)

    # If no custom config, use industry standard (backward compatibility)
    if range_config is None:
        from ..config.trace_ranges import get_industry_standard_preset
        range_config = get_industry_standard_preset()

    # Evaluate all boundary formulas
    breakpoints = []

    # First breakpoint: lower boundary of first range
    first_lower = evaluate_boundary_formula(range_config.ranges[0].lower_boundary, stats)
    # Use actual min if first boundary is 0 (common pattern)
    if first_lower == 0.0:
        first_lower = stats['min']
    breakpoints.append(first_lower)

    # Add upper boundary of each range
    for trace_range in range_config.ranges:
        upper_value = evaluate_boundary_formula(trace_range.upper_boundary, stats)
        breakpoints.append(upper_value)

    # Ensure monotonically increasing (fix any formula evaluation issues)
    for i in range(1, len(breakpoints)):
        if breakpoints[i] <= breakpoints[i - 1]:
            # Add small increment to avoid equal values
            breakpoints[i] = breakpoints[i - 1] + 0.01

    return breakpoints


# Keep backward-compatible function name
def calculate_value_quantiles(data: List[Dict[str, Any]], value_field: str) -> List[float]:
    """
    Calculate statistical breakpoints for geological data classification.

    DEPRECATED: Use calculate_trace_breakpoints() instead for custom range support.
    This function maintained for backward compatibility with existing code.

    Uses mean and standard deviation to define background vs anomaly ranges,
    following industry best practices for geochemical data visualization.

    Args:
        data: List of records
        value_field: Field name containing numeric values

    Returns:
        List of 7 breakpoints [min, mean, mean+1σ, mean+2σ, p95, p98, p99]

    Classification Scheme:
        - Background Low: min → mean
        - Background Normal: mean → mean + 1σ
        - Elevated: mean + 1σ → mean + 2σ
        - Anomalous: mean + 2σ → 95th percentile
        - High Anomaly: 95th → 98th percentile
        - Ore Grade: 98th → 99th percentile
    """
    # Use new function with industry standard preset
    return calculate_trace_breakpoints(data, value_field, None)


def apply_graduated_trace_symbology(
    layer: QgsVectorLayer,
    value_field: str,
    quantiles: List[float],
    line_width: float = 2.0,
    range_config=None
) -> None:
    """
    Apply graduated color rendering to trace layer based on statistical classification.

    Uses custom or default color scheme for trace visualization.

    Args:
        layer: Vector layer to style
        value_field: Field name for graduation
        quantiles: Statistical breakpoints calculated from data
        line_width: Width of trace lines in pixels
        range_config: TraceRangeConfiguration object (optional, uses industry standard if None)
    """
    # If no custom config, use industry standard (backward compatibility)
    if range_config is None:
        from ..config.trace_ranges import get_industry_standard_preset
        range_config = get_industry_standard_preset()

    # Get colors and names from configuration
    colors = range_config.get_colors()
    names = range_config.get_names()

    # Number of ranges should match quantiles - 1
    num_ranges = len(quantiles) - 1

    # Create renderer ranges
    ranges = []
    for i in range(num_ranges):
        # Get color and name for this range
        color = colors[i] if i < len(colors) else QColor(150, 150, 150)
        name = names[i] if i < len(names) else f"Range {i + 1}"

        symbol = QgsLineSymbol.createSimple({
            'color': color.name(),
            'width': str(line_width),
            'capstyle': 'flat',
            'joinstyle': 'miter'
        })

        # Format label with value range and name
        label = f"{name}: {quantiles[i]:.1f} - {quantiles[i + 1]:.1f}"

        range_obj = QgsRendererRange(
            quantiles[i],
            quantiles[i + 1],
            symbol,
            label
        )
        ranges.append(range_obj)

    # Apply graduated renderer
    renderer = QgsGraduatedSymbolRenderer(value_field, ranges)
    layer.setRenderer(renderer)
    layer.triggerRepaint()
