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


def group_by_collar(data: List[Dict[str, Any]]) -> Dict[Tuple[str, str, str], List[Dict]]:
    """
    Group assay samples by unique drill hole (hole_id + state) with fallback to coordinates.

    This function uses a hybrid approach to group samples:
    1. Primary: Group by (hole_id, state, 'id') if both are available
    2. Fallback: Group by (lat_lon_string, '', 'coords') if hole_id or state is missing

    The third element in the key tuple is a type identifier ('id' or 'coords') to
    distinguish between the two grouping methods.

    Args:
        data: List of assay records with hole_id, state, and/or coordinates

    Returns:
        Dictionary mapping (identifier, state, type) tuples to list of samples,
        sorted by from_depth in ascending order

    Examples:
        - Hole with ID and state: ("DDH-001", "NSW", "id")
        - Hole with ID, no state: ("RC-045", "Unknown", "id")
        - Hole without ID: ("-31.234567_115.789012", "", "coords")
    """
    from ..utils.logging import log_warning

    holes = {}
    for record in data:
        hole_id = record.get('hole_id', '').strip() if record.get('hole_id') else ''
        state = record.get('state', '').strip() if record.get('state') else ''

        # Primary grouping: Use hole_id + state if hole_id exists
        if hole_id:
            # Use state if available, otherwise use 'Unknown'
            state_value = state if state else 'Unknown'
            key = (hole_id, state_value, 'id')
        else:
            # Fallback: Use coordinates if no hole_id
            # Support both 'lat'/'lon' and 'latitude'/'longitude' field names
            lat = record.get('lat') or record.get('latitude', 0)
            lon = record.get('lon') or record.get('longitude', 0)

            try:
                # Round to 6 decimal places (~0.1m precision) for grouping
                lat = round(float(lat), 6)
                lon = round(float(lon), 6)

                # Create coordinate-based identifier
                coord_id = f"{lat}_{lon}"
                key = (coord_id, '', 'coords')

                # Log warning for first occurrence
                if key not in holes:
                    log_warning(f"Record without hole_id found at ({lat}, {lon}) - using coordinate-based grouping")
            except (ValueError, TypeError) as e:
                log_warning(f"Invalid coordinates for record without hole_id: {e}")
                # Use a fallback key for records with neither hole_id nor valid coordinates
                key = ('INVALID_RECORD', '', 'coords')

        if key not in holes:
            holes[key] = []
        holes[key].append(record)

    # Sort intervals within each hole by from_depth
    for key in holes:
        holes[key].sort(key=lambda r: float(r.get('from_depth', 0)))

    return holes


def create_continuous_trace_segments(
    intervals: List[Dict[str, Any]],
    max_depth_global: Optional[float] = None,
    offset_scale: float = 500.0
) -> List[Tuple[Dict[str, Any], float, float]]:
    """
    Create continuous trace segments including gap-filling segments.

    This ensures the trace line is continuous from collar (depth 0) to the maximum depth,
    filling any gaps between assay intervals.

    Args:
        intervals: Sorted list of assay records for a single drill hole
        max_depth_global: Maximum depth in dataset
        offset_scale: Scale factor for offset calculation

    Returns:
        List of tuples (record, from_depth, to_depth) for creating continuous segments
    """
    if not intervals:
        return []

    segments = []

    # Get collar location from first interval
    first_interval = intervals[0]
    first_from_depth = float(first_interval.get('from_depth', 0))

    # Add leading segment from collar (0) to first interval if needed
    if first_from_depth > 0.001:  # Only if gap is meaningful (> 1mm)
        # Create gap-filling segment from 0 to first interval
        segments.append((first_interval, 0.0, first_from_depth))

    # Add all assay intervals
    for i, interval in enumerate(intervals):
        from_depth = float(interval.get('from_depth', 0))
        to_depth = float(interval.get('to_depth', from_depth + 10))

        # Only add segment if it has meaningful length (> 1mm)
        if abs(to_depth - from_depth) > 0.001:
            segments.append((interval, from_depth, to_depth))

        # Check if there's a gap to the next interval
        if i < len(intervals) - 1:
            next_interval = intervals[i + 1]
            next_from_depth = float(next_interval.get('from_depth', to_depth))

            # If there's a meaningful gap (> 1mm), add a connecting segment
            if next_from_depth > to_depth + 0.001:
                # Use current interval's data for the gap segment
                segments.append((interval, to_depth, next_from_depth))

    return segments


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
    offset_scale: float = 500.0,
    from_depth: Optional[float] = None,
    to_depth: Optional[float] = None
) -> QgsGeometry:
    """
    Create LineString geometry for a single assay interval.

    Creates a line segment representing the actual depth interval from from_depth to to_depth,
    extending in the azimuth direction. This ensures sequential intervals don't overlap.

    Args:
        record: Assay record with lat/latitude, lon/longitude, azimuth (optional)
        max_depth_global: Maximum depth in dataset (for proportional offset)
        offset_scale: Scale factor for offset calculation
        from_depth: Start depth of interval (overrides record value if provided)
        to_depth: End depth of interval (overrides record value if provided)

    Returns:
        LineString geometry representing the interval from from_depth to to_depth
    """
    import math

    # Support both 'lat'/'lon' and 'latitude'/'longitude' field names
    lat = record.get('lat') or record.get('latitude', 0)
    lon = record.get('lon') or record.get('longitude', 0)

    # Use provided depths or fall back to record values
    if from_depth is None:
        from_depth = float(record.get('from_depth', 0))
    if to_depth is None:
        to_depth = float(record.get('to_depth', from_depth + 10))

    # Get azimuth if available (can be None, negative, or positive)
    azimuth = record.get('azimuth')

    # Calculate offset for start and end points based on actual depths
    # This creates sequential segments instead of overlapping lines
    if max_depth_global and max_depth_global > 0:
        # Proportional offset based on total depth (0.01 degrees ≈ 1.1 km)
        start_offset = from_depth / max_depth_global * 0.01
        end_offset = to_depth / max_depth_global * 0.01
    elif offset_scale > 0:
        # Fixed scale offset (0.01 degrees ≈ 1.1 km at equator)
        start_offset = from_depth / offset_scale * 0.01
        end_offset = to_depth / offset_scale * 0.01
    else:
        # Fallback to fixed offset to prevent division by zero
        start_offset = from_depth * 0.00001
        end_offset = to_depth * 0.00001

    # Calculate trace direction based on azimuth
    if azimuth is not None:
        try:
            azimuth_value = float(azimuth)
            # Azimuth is a compass bearing: 0° = North, 90° = East, 180° = South, 270° = West
            # Convert azimuth to radians for calculation
            azimuth_rad = math.radians(azimuth_value)

            # Calculate dx and dy based on azimuth for start and end points
            # In geographic coordinates:
            # - dx (change in longitude) = offset * sin(azimuth)
            # - dy (change in latitude) = offset * cos(azimuth)
            start_dx = start_offset * math.sin(azimuth_rad)
            start_dy = start_offset * math.cos(azimuth_rad)
            end_dx = end_offset * math.sin(azimuth_rad)
            end_dy = end_offset * math.cos(azimuth_rad)
        except (ValueError, TypeError):
            # If azimuth is invalid, default to vertical line (straight down)
            start_dx = 0
            start_dy = -start_offset  # Negative = move south (downward)
            end_dx = 0
            end_dy = -end_offset
    else:
        # No azimuth provided - create vertical line (straight down)
        start_dx = 0
        start_dy = -start_offset  # Negative = move south (downward)
        end_dx = 0
        end_dy = -end_offset

    # Start point at from_depth position, end point at to_depth position
    start_point = QgsPointXY(lon + start_dx, lat + start_dy)
    end_point = QgsPointXY(lon + end_dx, lat + end_dy)

    # CRITICAL: Prevent zero-length lines which can crash Qt
    # If start and end are the same (or very close), return None to skip this segment
    MIN_LINE_LENGTH = 0.00001  # Minimum line length in degrees (~1 meter)

    if abs(start_point.x() - end_point.x()) < MIN_LINE_LENGTH and \
       abs(start_point.y() - end_point.y()) < MIN_LINE_LENGTH:
        # Skip zero-length segments entirely - don't create geometry
        return None

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

    # Calculate basic stats with division by zero protection
    minimum = values[0]
    maximum = values[-1]

    if n > 0:
        mean = sum(values) / n
        variance = sum((x - mean) ** 2 for x in values) / n
        std_dev = variance ** 0.5
    else:
        # Should never happen due to check above, but added for safety
        mean = 0.0
        variance = 0.0
        std_dev = 0.0

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
        range_config: TraceRangeConfiguration object (optional, uses default if None)

    Returns:
        List of breakpoint values matching the range configuration
    """
    # Calculate data statistics
    stats = calculate_data_statistics(data, value_field)

    # If no custom config, use default (backward compatibility)
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
    # Use new function with default preset
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
    Includes special grey range for gap segments (no assay data).

    Args:
        layer: Vector layer to style
        value_field: Field name for graduation
        quantiles: Statistical breakpoints calculated from data
        line_width: Width of trace lines in pixels
        range_config: TraceRangeConfiguration object (optional, uses Default if None)
    """
    # If no custom config, use Default (backward compatibility)
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

    # FIRST: Add special grey range for gap segments (no assay data)
    # Gap segments have assay_value = 0.0001 (see qgis_helpers.py line 1211)
    gap_symbol = QgsLineSymbol.createSimple({
        'color': "#A5A5A5AD",  # Medium grey
        'width': str(line_width),  # Same width as regular lines
        'capstyle': 'flat',
        'joinstyle': 'miter',
        'line_style': 'solid'  # Solid line (continuous)
    })

    gap_range = QgsRendererRange(
        0.0,           # Lower bound
        0.001,         # Upper bound (captures 0.0001 gap value)
        gap_symbol,
        "No Assay Data"
    )
    ranges.append(gap_range)

    # THEN: Add regular assay value ranges
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
