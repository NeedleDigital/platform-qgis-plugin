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

    # Calculate horizontal offset (longer lines for better visibility)
    if max_depth_global and max_depth_global > 0:
        # Proportional offset based on total depth (0.01 degrees ≈ 1.1 km)
        offset = midpoint_depth / max_depth_global * 0.01
    else:
        # Fixed scale offset (0.01 degrees ≈ 1.1 km at equator)
        offset = midpoint_depth / offset_scale * 0.01

    # Create line from collar extending to the right
    start_point = QgsPointXY(lon, lat)
    end_point = QgsPointXY(lon + offset, lat)

    return QgsGeometry.fromPolylineXY([start_point, end_point])


def calculate_value_quantiles(data: List[Dict[str, Any]], value_field: str) -> List[float]:
    """
    Calculate statistical breakpoints for geological data classification.

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
    values = []
    for record in data:
        val = record.get(value_field)
        if val is not None:
            try:
                values.append(float(val))
            except (ValueError, TypeError):
                pass

    if not values or len(values) < 10:
        # Return default ranges if insufficient data
        return [0, 1, 2, 3, 4, 5, 6]

    # Sort values
    values.sort()
    n = len(values)

    # Calculate statistics
    minimum = values[0]

    # Calculate mean
    mean = sum(values) / n

    # Calculate standard deviation
    variance = sum((x - mean) ** 2 for x in values) / n
    std_dev = variance ** 0.5

    # Calculate mean + 1σ and mean + 2σ
    mean_plus_1sigma = mean + std_dev
    mean_plus_2sigma = mean + (2 * std_dev)

    # Calculate high percentiles
    p95_index = int(n * 0.95)
    p98_index = int(n * 0.98)
    p99_index = int(n * 0.99)

    p95 = values[min(p95_index, n - 1)]
    p98 = values[min(p98_index, n - 1)]
    p99 = values[min(p99_index, n - 1)]

    # Ensure values are monotonically increasing
    # (mean+2σ might exceed p95 in some distributions)
    mean_plus_1sigma = min(mean_plus_1sigma, p95)
    mean_plus_2sigma = min(mean_plus_2sigma, p95)

    return [minimum, mean, mean_plus_1sigma, mean_plus_2sigma, p95, p98, p99]


def apply_graduated_trace_symbology(
    layer: QgsVectorLayer,
    value_field: str,
    quantiles: List[float],
    line_width: float = 2.0
) -> None:
    """
    Apply graduated color rendering to trace layer based on statistical classification.

    Uses a blue → purple sequential color ramp following geological best practices,
    with colors representing statistical significance of assay values.

    Args:
        layer: Vector layer to style
        value_field: Field name for graduation
        quantiles: Statistical breakpoints [min, mean, mean+1σ, mean+2σ, p95, p98, p99]
        line_width: Width of trace lines in pixels

    Color Scheme:
        - Dark Blue: Background Low (min → mean)
        - Light Blue: Background Normal (mean → mean+1σ)
        - Yellow: Elevated (mean+1σ → mean+2σ)
        - Orange: Anomalous (mean+2σ → 95%)
        - Red: High Anomaly (95% → 98%)
        - Purple: Ore Grade (98% → 99%)
    """
    # Define sequential color ramp (blue → purple) with geological meaning
    colors = [
        QColor(25, 118, 210),   # Dark Blue - Background Low
        QColor(100, 181, 246),  # Light Blue - Background Normal
        QColor(255, 235, 59),   # Yellow - Elevated
        QColor(255, 152, 0),    # Orange - Anomalous
        QColor(244, 67, 54),    # Red - High Anomaly
        QColor(156, 39, 176)    # Purple - Ore Grade
    ]

    # Define labels with geological meaning
    labels = [
        "Background Low (< Mean)",
        "Normal (Mean to +1σ)",
        "Elevated (+1σ to +2σ)",
        "Anomalous (+2σ to 95%)",
        "High Anomaly (95-98%)",
        "Ore Grade (98-99%)"
    ]

    # Create renderer ranges
    ranges = []
    for i in range(6):
        symbol = QgsLineSymbol.createSimple({
            'color': colors[i].name(),
            'width': str(line_width),
            'capstyle': 'round'
        })

        # Format label with value range and geological meaning
        label = f"{labels[i]}: {quantiles[i]:.1f} - {quantiles[i + 1]:.1f}"

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
