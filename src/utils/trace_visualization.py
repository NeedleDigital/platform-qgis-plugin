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
    Calculate quantile breakpoints for graduated color classification.
    Uses 99th percentile as maximum to remove outliers.

    Args:
        data: List of records
        value_field: Field name containing numeric values

    Returns:
        List of 5 breakpoints [min, 25%, 50%, 75%, 99%]
    """
    values = []
    for record in data:
        val = record.get(value_field)
        if val is not None:
            try:
                values.append(float(val))
            except (ValueError, TypeError):
                pass

    if not values or len(values) < 4:
        # Return default ranges if insufficient data
        return [0, 1, 2, 3, 4]

    # Sort values
    values.sort()
    n = len(values)

    # Calculate quantiles manually (no numpy dependency)
    q0 = values[0]
    q25 = values[n // 4]
    q50 = values[n // 2]
    q75 = values[3 * n // 4]
    # Use 99th percentile instead of max to exclude outliers
    q99_index = int(n * 0.99)
    q99 = values[min(q99_index, n - 1)]

    return [q0, q25, q50, q75, q99]


def apply_graduated_trace_symbology(
    layer: QgsVectorLayer,
    value_field: str,
    quantiles: List[float],
    line_width: float = 2.0
) -> None:
    """
    Apply graduated color rendering to trace layer based on element values.

    Uses a green -> yellow -> orange -> red color ramp for concentration.

    Args:
        layer: Vector layer to style
        value_field: Field name for graduation
        quantiles: Value breakpoints [min, q25, q50, q75, max]
        line_width: Width of trace lines in pixels
    """
    # Define color ramp (green -> yellow -> orange -> red)
    colors = [
        QColor(76, 175, 80),    # Green (low values)
        QColor(255, 235, 59),   # Yellow (low-medium)
        QColor(255, 152, 0),    # Orange (medium-high)
        QColor(244, 67, 54)     # Red (high values)
    ]

    # Create renderer ranges
    ranges = []
    for i in range(4):
        symbol = QgsLineSymbol.createSimple({
            'color': colors[i].name(),
            'width': str(line_width),
            'capstyle': 'round'
        })

        range_obj = QgsRendererRange(
            quantiles[i],
            quantiles[i + 1],
            symbol,
            f"{quantiles[i]:.2f} - {quantiles[i + 1]:.2f}"
        )
        ranges.append(range_obj)

    # Apply graduated renderer
    renderer = QgsGraduatedSymbolRenderer(value_field, ranges)
    layer.setRenderer(renderer)
    layer.triggerRepaint()
