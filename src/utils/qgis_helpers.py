"""
QGIS Integration Utilities

This module provides specialized utilities for integrating mining data with QGIS,
handling all aspects of spatial data visualization and layer management.

Key Functionality:
    - Point layer creation from mining data (drill holes, assays)
    - Automatic coordinate system handling (Australian GDA2020)
    - Large dataset optimization with chunked processing
    - Memory management for performance
    - OpenStreetMap base layer integration
    - Dynamic styling and visualization
    - Progress tracking for long operations
    - User cancellation support

Technical Features:
    - Supports 1M+ record imports without crashes
    - Intelligent field type detection from data
    - Flexible coordinate field mapping (lat/lon, x/y)
    - Automatic geometry validation
    - Layer positioning and styling management
    - Error handling and user feedback

Coordinate System:
    Uses WGS84 (EPSG:4326) as the coordinate reference system since mining data
    is typically provided in latitude/longitude coordinates. Proper CRS transformations
    are handled automatically when zooming to ensure accurate visualization.

Author: Needle Digital
Contact: divyansh@needle-digital.com
"""

from typing import List, Dict, Any, Optional, Tuple
from qgis.core import (
    QgsVectorLayer, QgsRasterLayer, QgsFeature, QgsGeometry, QgsPoint, QgsField,
    QgsProject, QgsSymbol, QgsSingleSymbolRenderer, QgsMessageLog,
    Qgis, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsPointXY,
    QgsGraduatedSymbolRenderer, QgsRendererRange, QgsLineSymbol, QgsLayerTreeGroup,
    QgsVectorDataProvider
)
from qgis.PyQt.QtCore import QVariant, QMetaType
from qgis.PyQt.QtGui import QColor

# Configuration imports for styling and thresholds
from ..config.constants import (
    DEFAULT_LAYER_STYLE, IMPORT_CHUNK_SIZE, OSM_LAYER_NAME,
    OSM_LAYER_URL, AUTO_ZOOM_THRESHOLD, TRACE_SCALE_THRESHOLD,
    TRACE_DEFAULT_OFFSET_SCALE, TRACE_LINE_WIDTH, COLLAR_POINT_SIZE,
    TRACE_ELEMENT_STACK_OFFSET
)
from .logging import log_error, log_warning
# Import version compatibility utilities for QGIS 3.0+ support
from .qgis_version_compat import create_qgs_field_compatible, get_qgis_version_int


class QGISLayerManager:
    """QGIS Layer Management and Integration Helper.
    
    This class provides comprehensive QGIS integration for mining data visualization,
    handling layer creation, styling, and management with optimization for large datasets.
    
    Key Features:
        - Memory-efficient point layer creation
        - Automatic field type detection and mapping
        - Large dataset chunked processing (prevents crashes)
        - OpenStreetMap base layer management
        - Dynamic styling and visualization
        - Progress tracking with user cancellation
        - Error handling and recovery
    
    Performance Optimizations:
        - Chunked processing for datasets >10,000 records
        - Garbage collection between chunks
        - Memory usage monitoring
        - Smart zoom behavior based on dataset size
        - Efficient geometry creation and validation
    
    Attributes:
        iface (QgisInterface): Reference to QGIS interface for UI integration
                              None if running in headless mode or testing
    """
    
    def __init__(self, iface=None):
        """
        Initialize the QGIS layer manager.
        
        Args:
            iface (QgisInterface, optional): QGIS interface instance for GUI access.
                                           None for headless operations or testing.
                                           Provides access to map canvas, toolbars,
                                           and message bar for user feedback.
        """
        self.iface = iface
    
    def create_point_layer(self, layer_name: str, data: List[Dict[str, Any]],
                          color: Optional[QColor] = None, point_size: float = 3.0) -> Tuple[bool, str]:
        """
        Create a point layer from data.

        Args:
            layer_name: Name for the new layer
            data: List of dictionaries containing point data
            color: Point color (optional)

        Returns:
            Tuple of (success, message)
        """
        try:
            if not data:
                return False, "No data to import"

            # Create layer with WGS84 CRS since data is in lat/lon coordinates
            crs = QgsCoordinateReferenceSystem("EPSG:4326")
            layer = QgsVectorLayer(f"Point?crs={crs.authid()}", layer_name, "memory")

            if not layer.isValid():
                return False, "Failed to create layer"

            # Get data provider
            provider = layer.dataProvider()

            # Define fields based on first record
            fields = self._create_fields_from_data(data[0])
            provider.addAttributes(fields)
            layer.updateFields()

            # Add features
            features = []
            for record in data:
                feature = self._create_feature_from_record(record, layer.fields())
                if feature:
                    features.append(feature)

            provider.addFeatures(features)
            layer.updateExtents()

            # Apply styling with custom point size
            self._apply_layer_styling(layer, color, point_size)
            
            # Add to project
            QgsProject.instance().addMapLayer(layer)
            
            # Zoom to layer if interface available and dataset is not too large
            if self.iface and len(features) <= AUTO_ZOOM_THRESHOLD:
                self._zoom_to_layer(layer)
            elif len(features) > AUTO_ZOOM_THRESHOLD:
                pass
            
            return True, f"Successfully imported {len(features)} records"
            
        except Exception as e:
            error_msg = f"Failed to create layer: {str(e)}"
            log_error(error_msg)
            return False, error_msg
    
    def _create_fields_from_data(self, sample_record: Dict[str, Any]) -> List[QgsField]:
        """Create QGIS fields from sample data record with version compatibility.

        This method automatically handles QgsField creation for different QGIS versions:
        - QGIS 3.0-3.37: Uses QVariant.Type
        - QGIS 3.38+: Uses QMetaType.Type

        Args:
            sample_record: Sample data record to extract field types from

        Returns:
            List of QgsField objects compatible with current QGIS version
        """
        fields = []

        for key, value in sample_record.items():
            # Skip coordinate fields as they're only used for geometry
            if key.lower() in ['latitude', 'longitude', 'lat', 'lon', 'x', 'y']:
                continue

            # Use version-compatible field creation
            # This automatically selects QVariant or QMetaType based on QGIS version
            try:
                field = create_qgs_field_compatible(key, value)
                fields.append(field)
            except Exception as e:
                # Log error but continue with other fields
                log_error(f"Failed to create field '{key}' with value type {type(value).__name__}: {e}")
                # Skip this field and continue processing others
                continue

        return fields
    
    def _create_feature_from_record(self, record: Dict[str, Any], 
                                  layer_fields) -> Optional[QgsFeature]:
        """Create a QGIS feature from a data record."""
        try:
            feature = QgsFeature(layer_fields)
            
            # Extract coordinates
            lat, lon = self._extract_coordinates(record)
            if lat is None or lon is None:
                log_warning(f"Skipping record with invalid coordinates: {record}")
                return None
            
            # Create point geometry
            point = QgsPoint(lon, lat)
            geometry = QgsGeometry(point)
            feature.setGeometry(geometry)
            
            # Set attributes
            for field in layer_fields:
                field_name = field.name()
                if field_name in record:
                    feature.setAttribute(field_name, record[field_name])
            
            return feature
            
        except Exception as e:
            log_error(f"Failed to create feature from record {record}: {e}")
            return None
    
    def _extract_coordinates(self, record: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
        """Extract latitude and longitude from record."""
        # Try different possible coordinate field names
        lat_fields = ['latitude', 'lat', 'y']
        lon_fields = ['longitude', 'lon', 'lng', 'x']
        
        lat = None
        lon = None
        
        for field in lat_fields:
            if field in record and record[field] is not None:
                try:
                    lat = float(record[field])
                    break
                except (ValueError, TypeError):
                    continue
        
        for field in lon_fields:
            if field in record and record[field] is not None:
                try:
                    lon = float(record[field])
                    break
                except (ValueError, TypeError):
                    continue
        
        return lat, lon
    
    def _apply_layer_styling(self, layer: QgsVectorLayer, color: Optional[QColor] = None, point_size: float = None):
        """Apply styling to the layer."""
        try:
            # Use provided color or default
            point_color = color or QColor(DEFAULT_LAYER_STYLE['point_color'])

            # Use provided point size or default
            size = point_size if point_size is not None else DEFAULT_LAYER_STYLE['point_size']

            # Create symbol
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            symbol.setColor(point_color)
            symbol.setSize(size)
            symbol.setOpacity(DEFAULT_LAYER_STYLE['point_transparency'])

            # Apply renderer
            renderer = QgsSingleSymbolRenderer(symbol)
            layer.setRenderer(renderer)

            # Setup hover tooltips (map tips)
            self._setup_hover_tooltips(layer)

            # Refresh layer
            layer.triggerRepaint()

        except Exception as e:
            log_warning(f"Failed to apply layer styling: {e}")


    def _setup_hover_tooltips(self, layer: QgsVectorLayer):
        """Setup hover tooltips (map tips) for the layer showing company name and hole ID (or collar ID as fallback)."""
        try:
            # Get field names from the layer
            field_names = [field.name() for field in layer.fields()]

            # Find company name field - try common variations
            company_field = None
            for field_name in ['company_name', 'company', 'name']:
                if field_name in field_names:
                    company_field = field_name
                    break

            # Find hole ID field - try common variations
            hole_id_field = None
            for field_name in ['hole_id', 'holeid', 'hole_name', 'id']:
                if field_name in field_names:
                    hole_id_field = field_name
                    break

            # Find collar ID field as fallback - try common variations
            collar_id_field = None
            for field_name in ['collar_id', 'collarid', 'collar']:
                if field_name in field_names:
                    collar_id_field = field_name
                    break

            # Only setup tooltips if we have at least one of the required fields
            if not company_field and not hole_id_field and not collar_id_field:
                return

            # Build HTML template for hover tooltip
            tooltip_parts = []

            if company_field:
                tooltip_parts.append(f'<b>Company:</b> [% "{company_field}" %]')

            # Show hole_id if available, otherwise show collar_id as fallback
            if hole_id_field and collar_id_field:
                # Use QGIS expression to show hole_id if not empty, otherwise collar_id
                # COALESCE returns the first non-null value
                tooltip_parts.append(
                    f'<b>Hole ID:</b> [% COALESCE("{hole_id_field}", "{collar_id_field}") %]'
                )
            elif hole_id_field:
                tooltip_parts.append(f'<b>Hole ID:</b> [% "{hole_id_field}" %]')
            elif collar_id_field:
                tooltip_parts.append(f'<b>Collar ID:</b> [% "{collar_id_field}" %]')

            # Create HTML template with good readability (light background, dark text)
            tooltip_html = f"""
            <div style="background-color: #ffffff;
                        border: 2px solid #333333;
                        border-radius: 8px;
                        padding: 8px 12px;
                        font-family: Arial, sans-serif;
                        font-size: 12px;
                        color: #333333;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
                        max-width: 250px;">
                {' | '.join(tooltip_parts)}
            </div>
            """

            # Set the map tip template
            layer.setMapTipTemplate(tooltip_html)


        except Exception as e:
            log_warning(f"Failed to setup hover tooltips: {e}")

    def _setup_trace_tooltips(self, layer: QgsVectorLayer, element: str, value_field: str = 'assay_value'):
        """Setup hover tooltips for trace lines showing depth interval and assay value.

        Args:
            layer: Trace lines vector layer
            element: Element name (e.g., 'Au', 'Cu')
            value_field: Field name containing assay values (default: 'assay_value')
        """
        try:
            field_names = [field.name() for field in layer.fields()]

            # Build tooltip with depth, assay value, and metadata
            tooltip_parts = []

            # Depth interval (from_depth and to_depth)
            if 'from_depth' in field_names and 'to_depth' in field_names:
                tooltip_parts.append('<b>Depth Interval:</b> [% "from_depth" %]m - [% "to_depth" %]m')

            # Assay value (use detected value field)
            if value_field in field_names:
                tooltip_parts.append(f'<b>{element} Value:</b> [% "{value_field}" %] ppm')

            # Interval length
            if 'interval_length' in field_names:
                tooltip_parts.append('<b>Sample Length:</b> [% "interval_length" %]m')

            # Hole ID
            if 'hole_id' in field_names:
                tooltip_parts.append('<b>Hole ID:</b> [% "hole_id" %]')

            # Company name
            if 'company_name' in field_names:
                tooltip_parts.append('<b>Company:</b> [% "company_name" %]')

            # Element name
            if 'assay_element' in field_names:
                tooltip_parts.append('<b>Element:</b> [% "assay_element" %]')

            # Create HTML tooltip with clean styling
            tooltip_html = f"""
            <div style="background-color: #ffffff;
                        border: 2px solid #333333;
                        border-radius: 8px;
                        padding: 10px 14px;
                        font-family: Arial, sans-serif;
                        font-size: 13px;
                        color: #333333;
                        line-height: 1.6;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
                        max-width: 300px;">
                {'<br>'.join(tooltip_parts)}
            </div>
            """

            layer.setMapTipTemplate(tooltip_html)

        except Exception as e:
            log_warning(f"Failed to setup trace tooltips: {e}")

    def _setup_location_tooltips(self, layer: QgsVectorLayer):
        """Setup hover tooltips (map tips) for location-only data showing latitude and longitude."""
        try:
            # Get field names from the layer
            field_names = [field.name() for field in layer.fields()]

            # Debug: Log available field names
            from .logging import log_warning
            log_warning(f"Location tooltip setup - Available fields: {field_names}")

            # Find latitude field - try common variations
            lat_field = None
            for field_name in ['latitude', 'lat', 'y']:
                if field_name in field_names:
                    lat_field = field_name
                    break

            # Find longitude field - try common variations
            lon_field = None
            for field_name in ['longitude', 'lon', 'lng', 'x']:
                if field_name in field_names:
                    lon_field = field_name
                    break

            # Debug: Log found fields
            log_warning(f"Location tooltip setup - Found lat_field: {lat_field}, lon_field: {lon_field}")

            # Only setup tooltips if we have both lat and lon fields
            if not lat_field or not lon_field:
                log_warning(f"Location tooltip setup - Missing fields! Cannot setup tooltips.")
                return

            # Create HTML template with good readability (white background, dark text)
            tooltip_html = f"""
            <div style="background-color: #ffffff;
                        border: 2px solid #333333;
                        border-radius: 8px;
                        padding: 8px 12px;
                        font-family: Arial, sans-serif;
                        font-size: 12px;
                        color: #333333;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
                        max-width: 250px;">
                <b>Latitude:</b> [% "{lat_field}" %]<br/>
                <b>Longitude:</b> [% "{lon_field}" %]
            </div>
            """

            # Set the map tip template
            layer.setMapTipTemplate(tooltip_html)
            log_warning(f"Location tooltip setup - Successfully set map tip template")

        except Exception as e:
            log_warning(f"Failed to setup location tooltips: {e}")

    def _zoom_to_layer(self, layer: QgsVectorLayer):
        """Zoom to the full extent of the layer with proper CRS transformation."""
        try:
            if not self.iface or not layer.isValid():
                return

            # Get layer extent in layer's CRS
            layer_extent = layer.extent()
            if layer_extent.isEmpty():
                log_warning("Layer extent is empty, cannot zoom")
                return

            map_canvas = self.iface.mapCanvas()

            # Get the layer and canvas CRS
            layer_crs = layer.crs()
            canvas_crs = map_canvas.mapSettings().destinationCrs()


            # Transform extent if CRS differs
            extent_to_use = layer_extent
            if layer_crs != canvas_crs:
                transform = QgsCoordinateTransform(layer_crs, canvas_crs, QgsProject.instance())
                try:
                    extent_to_use = transform.transformBoundingBox(layer_extent)
                except Exception as transform_error:
                    log_warning(f"Failed to transform extent: {transform_error}, using original")
                    extent_to_use = layer_extent

            # Add some padding around the data (10% buffer)
            width = extent_to_use.width()
            height = extent_to_use.height()

            if width > 0 and height > 0:
                buffer_x = width * 0.1
                buffer_y = height * 0.1
                extent_to_use.setXMinimum(extent_to_use.xMinimum() - buffer_x)
                extent_to_use.setXMaximum(extent_to_use.xMaximum() + buffer_x)
                extent_to_use.setYMinimum(extent_to_use.yMinimum() - buffer_y)
                extent_to_use.setYMaximum(extent_to_use.yMaximum() + buffer_y)

            # Set the extent to the map canvas
            map_canvas.setExtent(extent_to_use)
            map_canvas.refresh()


        except Exception as e:
            log_error(f"Failed to zoom to layer: {e}")
            # Fallback to default zoom method
            try:
                self.iface.zoomToActiveLayer()
            except Exception as fallback_error:
                log_error(f"Fallback zoom also failed: {fallback_error}")
    
    def show_message(self, message: str, level: Qgis.MessageLevel = Qgis.Info,
                    duration: int = 3, plugin_dialog=None) -> None:
        """Show message in plugin dialog or QGIS interface."""
        try:
            # Convert QGIS message level to plugin message type
            message_type = "info"
            if level == Qgis.Success:
                message_type = "success"
            elif level == Qgis.Warning:
                message_type = "warning"
            elif level == Qgis.Critical:
                message_type = "error"

            # Prefer plugin dialog message if available
            if plugin_dialog and hasattr(plugin_dialog, 'show_plugin_message'):
                plugin_dialog.show_plugin_message(message, message_type, duration * 1000)  # Convert seconds to milliseconds
            elif self.iface:
                self.iface.messageBar().pushMessage("Needle Digital", message, level, duration)
            else:
                # Fallback to message log
                QgsMessageLog.logMessage(f"Needle Digital: {message}", "Plugins", level)
        except Exception as e:
            log_error(f"Failed to show message: {e}")
    
    def add_osm_base_layer(self) -> Tuple[bool, str]:
        """Add OpenStreetMap base layer if it doesn't already exist."""
        try:
            project = QgsProject.instance()
            
            # Check if OSM layer already exists
            existing_layers = project.mapLayersByName(OSM_LAYER_NAME)
            if existing_layers:
                return True, "OpenStreetMap layer already exists"
            
            # Create OSM layer
            osm_layer = QgsRasterLayer(OSM_LAYER_URL, OSM_LAYER_NAME, "wms")
            
            if not osm_layer.isValid():
                error_msg = "Failed to create OpenStreetMap layer"
                log_error(error_msg)
                return False, error_msg
            
            # Add layer to project (at the bottom of layer tree)
            project.addMapLayer(osm_layer, False)  # False = don't add to legend tree yet
            
            # Get root layer tree and add as first (bottom) layer
            root = project.layerTreeRoot()
            root.insertLayer(0, osm_layer)
            
            return True, "OpenStreetMap base layer added successfully"
            
        except Exception as e:
            error_msg = f"Failed to add OpenStreetMap layer: {str(e)}"
            log_error(error_msg)
            return False, error_msg
    
    def create_point_layer_chunked(self, layer_name: str, data: List[Dict[str, Any]],
                                  color: Optional[QColor] = None,
                                  progress_callback: Optional[callable] = None,
                                  point_size: float = 3.0) -> Tuple[bool, str]:
        """
        Create a point layer from large dataset using chunked processing.

        Args:
            layer_name: Name for the new layer
            data: List of dictionaries containing point data
            color: Point color (optional)
            progress_callback: Function to call with progress updates (processed_count, chunk_info)

        Returns:
            Tuple of (success, message)
        """
        try:
            if not data:
                return False, "No data to import"

            total_records = len(data)

            # Create layer with WGS84 CRS since data is in lat/lon coordinates
            crs = QgsCoordinateReferenceSystem("EPSG:4326")
            layer = QgsVectorLayer(f"Point?crs={crs.authid()}", layer_name, "memory")

            if not layer.isValid():
                return False, "Failed to create layer"

            # Get data provider
            provider = layer.dataProvider()

            # Define fields based on first record
            fields = self._create_fields_from_data(data[0])
            provider.addAttributes(fields)
            layer.updateFields()
            
            # Process data in chunks
            chunk_size = IMPORT_CHUNK_SIZE
            processed_count = 0
            total_features_added = 0
            
            for chunk_start in range(0, total_records, chunk_size):
                chunk_end = min(chunk_start + chunk_size, total_records)
                chunk_data = data[chunk_start:chunk_end]
                
                # Update progress
                if progress_callback:
                    chunk_info = f"Processing chunk {chunk_start // chunk_size + 1} of {(total_records + chunk_size - 1) // chunk_size}"
                    progress_callback(processed_count, chunk_info)
                
                # Create features for this chunk
                chunk_features = []
                for record in chunk_data:
                    feature = self._create_feature_from_record(record, layer.fields())
                    if feature:
                        chunk_features.append(feature)
                
                # Add chunk features to layer
                if chunk_features:
                    success = provider.addFeatures(chunk_features)
                    if success:
                        total_features_added += len(chunk_features)
                    else:
                        log_warning(f"Failed to add some features in chunk {chunk_start // chunk_size + 1}")
                
                processed_count += len(chunk_data)
                
                # Update progress after chunk completion
                if progress_callback:
                    progress_callback(processed_count, f"Completed chunk {chunk_start // chunk_size + 1}")
                
                # Process Qt events to keep UI responsive and check for cancellation
                from qgis.PyQt.QtWidgets import QApplication
                QApplication.processEvents()
                
                # Force garbage collection to free memory
                import gc
                del chunk_features, chunk_data
                gc.collect()
            
            # Finalize layer
            layer.updateExtents()

            # Apply styling
            self._apply_layer_styling(layer, color, point_size)
            
            # Add to project
            QgsProject.instance().addMapLayer(layer)
            
            # Zoom to layer if interface available and dataset is not too large
            if self.iface and total_features_added <= AUTO_ZOOM_THRESHOLD:
                self._zoom_to_layer(layer)
            elif total_features_added > AUTO_ZOOM_THRESHOLD:
                pass
            
            success_msg = f"Successfully imported {total_features_added:,} records in {(total_records + chunk_size - 1) // chunk_size} chunks"
            return True, success_msg

        except Exception as e:
            error_msg = f"Failed to create layer with chunked import: {str(e)}"
            log_error(error_msg)
            return False, error_msg

    def create_assay_trace_layer(
        self,
        layer_name: str,
        data: List[Dict[str, Any]],
        color: Optional[QColor] = None,
        element: str = "Unknown",
        value_field: str = "assay_value",
        progress_callback: Optional[callable] = None,
        trace_range_config=None,
        point_size: float = 3.0,
        collar_layer_name: Optional[str] = None,
        trace_layer_name: Optional[str] = None,
        group_name: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Create drill hole trace visualization layers for assay data.

        Creates two layers:
        1. Collar points layer (visible when zoomed out)
        2. Interval trace lines layer (visible when zoomed in)

        Args:
            layer_name: Base name for the layers
            data: List of assay records with lat, lon, from_depth, to_depth, assay_value
            color: Optional color for styling
            element: Element name for the assay data
            value_field: Field name containing assay values (default: 'assay_value')
            progress_callback: Optional callback function(processed_count, message) for progress updates
            trace_range_config: TraceRangeConfiguration for custom range visualization (optional)

        Returns:
            Tuple of (success, message)
        """
        try:
            from .trace_visualization import (
                group_by_collar, get_max_depth_from_data,
                create_trace_line_geometry, calculate_trace_breakpoints,
                apply_graduated_trace_symbology
            )

            if not data:
                return False, "No data to import"

            # DEBUG: Print first record to see structure
            print(f"\n=== TRACE LAYER DEBUG ===")
            print(f"Total records: {len(data)}")
            print(f"First record keys: {list(data[0].keys())}")
            print(f"First record: {data[0]}")
            print(f"Value field: {value_field}")

            # Report progress: Starting
            if progress_callback:
                progress_callback(0, "Grouping samples by collar...")

            # Group samples by drill hole (unique lat/lon)
            holes = group_by_collar(data)
            print(f"Grouped into {len(holes)} collar locations")

            # Get maximum depth for proportional scaling (use final_depth field)
            max_depth = get_max_depth_from_data(data)
            print(f"Max depth: {max_depth}")
            print("=" * 50)

            # Report progress: 10%
            if progress_callback:
                progress_callback(int(len(data) * 0.1), "Creating collar points layer...")

            # Create collar points layer
            collar_name = collar_layer_name or f"{layer_name} - Collars"
            collar_success, collar_layer = self._create_collar_points_layer(
                collar_name,
                holes,
                color or QColor(0, 120, 255),
                value_field,
                point_size
            )

            if not collar_success:
                return False, f"Failed to create collar layer: {collar_layer}"

            # Report progress: 30%
            if progress_callback:
                progress_callback(int(len(data) * 0.3), "Creating trace lines layer...")

            # Create trace lines layer with progress updates
            trace_name = trace_layer_name or f"{layer_name} - Traces"
            trace_success, trace_layer = self._create_trace_lines_layer(
                trace_name,
                data,
                element,
                max_depth,
                progress_callback
            )

            if not trace_success:
                return False, f"Failed to create trace layer: {trace_layer}"

            # Apply scale-dependent visibility
            # Collar points: always visible
            collar_layer.setScaleBasedVisibility(False)

            # Trace lines: visible when zoomed in (smaller scale number = zoomed in)
            trace_layer.setScaleBasedVisibility(True)
            trace_layer.setMaximumScale(1)  # Show when zoomed in (small scale number)
            trace_layer.setMinimumScale(TRACE_SCALE_THRESHOLD)  # Hide when zoomed out (large scale number)

            # Report progress: 85%
            if progress_callback:
                progress_callback(int(len(data) * 0.85), "Applying color classification...")

            # Apply graduated symbology to traces with custom range configuration
            if value_field:
                breakpoints = calculate_trace_breakpoints(data, value_field, trace_range_config)
                apply_graduated_trace_symbology(trace_layer, value_field, breakpoints, TRACE_LINE_WIDTH, trace_range_config)

            # Setup hover tooltips for trace lines
            self._setup_trace_tooltips(trace_layer, element, value_field)

            # Report progress: 95%
            if progress_callback:
                progress_callback(int(len(data) * 0.95), "Adding layers to map...")

            # Create layer group and add layers
            root = QgsProject.instance().layerTreeRoot()
            group_layer_name = group_name or f"{element} Assays"
            group = root.insertGroup(0, group_layer_name)
            group.addLayer(collar_layer)
            group.addLayer(trace_layer)

            # Report progress: 100%
            if progress_callback:
                progress_callback(len(data), "Zooming to layer...")

            # Zoom to collar layer (always zoom)
            if self.iface:
                # Force update the layer extent before zooming
                collar_layer.updateExtents()

                # Get extent and add buffer
                extent = collar_layer.extent()
                print(f"Collar layer extent: {extent}")
                print(f"Extent is empty: {extent.isEmpty()}")

                if not extent.isEmpty():
                    # Add 10% buffer around the data
                    width = extent.width()
                    height = extent.height()
                    buffer_x = width * 0.1
                    buffer_y = height * 0.1
                    extent.setXMinimum(extent.xMinimum() - buffer_x)
                    extent.setXMaximum(extent.xMaximum() + buffer_x)
                    extent.setYMinimum(extent.yMinimum() - buffer_y)
                    extent.setYMaximum(extent.yMaximum() + buffer_y)

                    # Set extent and refresh canvas
                    map_canvas = self.iface.mapCanvas()
                    map_canvas.setExtent(extent)
                    map_canvas.refresh()
                    print(f"Zoomed to extent with buffer: {extent}")
                else:
                    print("WARNING: Collar layer extent is empty - cannot zoom")

            return True, f"Successfully created trace visualization: {len(holes)} collars, {len(data)} intervals"

        except Exception as e:
            error_msg = f"Failed to create trace layer: {str(e)}"
            log_error(error_msg)
            return False, error_msg

    def _find_value_field(self, data: List[Dict[str, Any]], element: str) -> Optional[str]:
        """Find the field name containing element values.

        Args:
            data: List of data records
            element: Element name (e.g., 'Au', 'Cu')

        Returns:
            Field name or None if not found
        """
        if not data:
            return None

        first_record = data[0]

        # Try lowercase element name
        element_lower = element.lower()
        if element_lower in first_record:
            return element_lower

        # Try uppercase element name
        element_upper = element.upper()
        if element_upper in first_record:
            return element_upper

        # Try 'value' field
        if 'value' in first_record:
            return 'value'

        # Try to find any numeric field that's not depth/coordinate
        exclude_fields = ['from_depth', 'to_depth', 'lat', 'lon', 'latitude', 'longitude',
                         'hole_id', 'sample_id', 'max_depth']
        for key in first_record.keys():
            if key.lower() not in exclude_fields:
                val = first_record[key]
                try:
                    float(val)
                    return key
                except (ValueError, TypeError):
                    continue

        return None

    def _create_collar_points_layer(
        self,
        layer_name: str,
        holes: Dict[Tuple[float, float], List[Dict]],
        color: QColor,
        value_field: Optional[str] = None,
        point_size: float = 3.0
    ) -> Tuple[bool, Optional[QgsVectorLayer]]:
        """Create point layer for drill hole collars.

        IMPORTANT: For QGIS memory layers, use provider.addFeatures() directly.
        DO NOT use layer.startEditing() / layer.commitChanges() - that pattern is
        for file-based layers only (shapefiles, GeoPackage, etc.).
        """
        try:
            crs = QgsCoordinateReferenceSystem("EPSG:4326")
            layer = QgsVectorLayer(f"Point?crs={crs.authid()}", layer_name, "memory")

            if not layer.isValid():
                return False, None

            provider = layer.dataProvider()

            # Define fields (pass sample values, not QVariant types)
            fields = [
                create_qgs_field_compatible('hole_id', "DH0001"),      # String sample
                create_qgs_field_compatible('lat', 0.0),               # Double sample
                create_qgs_field_compatible('lon', 0.0),               # Double sample
                create_qgs_field_compatible('sample_count', 0),        # Int sample
                create_qgs_field_compatible('max_value', 0.0)          # Double sample
            ]
            provider.addAttributes(fields)
            layer.updateFields()

            # Add layer to project BEFORE adding features (some QGIS versions require this)
            QgsProject.instance().addMapLayer(layer, False)

            # Build all features first, then add in batch (same pattern as trace lines)
            all_features = []
            hole_id = 1
            for (lat, lon), samples in holes.items():
                feature = QgsFeature(layer.fields())

                # Create point geometry
                point_geom = QgsGeometry.fromPointXY(QgsPointXY(lon, lat))
                feature.setGeometry(point_geom)

                # Debug first feature
                if hole_id == 1:
                    print(f"First collar point: lat={lat}, lon={lon}")
                    print(f"Geometry valid: {point_geom.isGeosValid()}")
                    print(f"Geometry type: {point_geom.type()}")
                    print(f"WKT: {point_geom.asWkt()}")

                # Calculate stats for this hole using the detected value field
                values = []
                if value_field:
                    values = [s.get(value_field, 0) for s in samples if s.get(value_field) is not None]
                max_val = max(values) if values else 0

                # Prepare attribute data
                attr_data = {
                    'hole_id': f"DH{hole_id:04d}",
                    'lat': lat,
                    'lon': lon,
                    'sample_count': len(samples),
                    'max_value': max_val
                }

                # Set attributes by iterating over fields (same pattern as trace lines)
                for field in layer.fields():
                    field_name = field.name()
                    if field_name in attr_data:
                        feature.setAttribute(field_name, attr_data[field_name])

                # Debug first feature attributes after setting
                if hole_id == 1:
                    print(f"First feature attributes after setting: {feature.attributes()}")
                    print(f"Feature is valid: {feature.isValid()}")
                    for i, field in enumerate(layer.fields()):
                        print(f"  Field {i}: {field.name()} = {feature.attribute(field.name())}")

                all_features.append(feature)
                hole_id += 1

            # Validate a few features before adding
            print(f"Total features to add: {len(all_features)}")
            if all_features:
                for i in range(min(3, len(all_features))):
                    f = all_features[i]
                    print(f"Feature {i}: geom_valid={f.geometry().isGeosValid()}, has_geom={f.hasGeometry()}, attr_count={len(f.attributes())}")

            # Add all features to provider in batch
            success, added_features = provider.addFeatures(all_features)
            print(f"Collar add features result: {success}, features added: {len(added_features) if success else 0}")

            # Check for errors
            if not success:
                # Try to get more detailed error info
                print(f"Provider capabilities: {provider.capabilities()}")
                print(f"Layer is valid: {layer.isValid()}")
                print(f"Layer CRS: {layer.crs().authid()}")
                print(f"Provider supports AddFeatures: {provider.capabilities() & QgsVectorDataProvider.AddFeatures}")

                # Try adding just the first feature to see if there's a specific error
                print(f"\nTrying to add first feature alone...")
                test_success, test_added = provider.addFeatures([all_features[0]])
                print(f"Single feature add result: {test_success}")

            # Force extent recalculation
            layer.updateExtents()

            print(f"Collar layer feature count: {layer.featureCount()}")
            print(f"Collar layer extent after adding: {layer.extent()}")
            print(f"Collar layer extent isEmpty: {layer.extent().isEmpty()}")

            # Apply styling with custom point size
            self._apply_layer_styling(layer, color, point_size)

            # Layer already added to project above (before adding features)
            return True, layer

        except Exception as e:
            log_error(f"Failed to create collar layer: {str(e)}")
            return False, None

    def _create_trace_lines_layer(
        self,
        layer_name: str,
        data: List[Dict[str, Any]],
        element: str,
        max_depth: Optional[float],
        progress_callback: Optional[callable] = None
    ) -> Tuple[bool, Optional[QgsVectorLayer]]:
        """Create line layer for drill hole trace intervals with chunked progress updates.

        IMPORTANT: For QGIS memory layers, use provider.addFeatures() directly.
        DO NOT use layer.startEditing() / layer.commitChanges() - that pattern is
        for file-based layers only (shapefiles, GeoPackage, etc.).

        Args:
            layer_name: Name for the trace lines layer
            data: List of assay records
            element: Element name
            max_depth: Maximum depth value
            progress_callback: Optional callback for progress updates

        Returns:
            Tuple of (success, layer or None)
        """
        try:
            from .trace_visualization import create_trace_line_geometry

            crs = QgsCoordinateReferenceSystem("EPSG:4326")
            layer = QgsVectorLayer(f"LineString?crs={crs.authid()}", layer_name, "memory")

            if not layer.isValid():
                return False, None

            provider = layer.dataProvider()

            # Define fields based on first record
            if data:
                fields = self._create_fields_from_data(data[0])
                # Add depth-specific fields
                fields.extend([
                    create_qgs_field_compatible('interval_length', QVariant.Double),
                    create_qgs_field_compatible('midpoint_depth', QVariant.Double)
                ])
                provider.addAttributes(fields)
                layer.updateFields()

            # Create line features with progress updates (use provider.addFeatures for memory layers)
            total_records = len(data)
            chunk_size = 1000  # Update progress and add features in chunks

            all_features = []
            for idx, record in enumerate(data):
                feature = QgsFeature(layer.fields())

                # Create trace line geometry
                line_geom = create_trace_line_geometry(
                    record,
                    max_depth,
                    TRACE_DEFAULT_OFFSET_SCALE
                )
                feature.setGeometry(line_geom)

                # Set attributes
                for field in layer.fields():
                    field_name = field.name()
                    if field_name == 'interval_length':
                        from_d = float(record.get('from_depth', 0))
                        to_d = float(record.get('to_depth', from_d))
                        feature.setAttribute(field_name, to_d - from_d)
                    elif field_name == 'midpoint_depth':
                        from_d = float(record.get('from_depth', 0))
                        to_d = float(record.get('to_depth', from_d))
                        feature.setAttribute(field_name, (from_d + to_d) / 2)
                    else:
                        feature.setAttribute(field_name, record.get(field_name))

                all_features.append(feature)

                # Update progress every chunk_size records
                if progress_callback and (idx + 1) % chunk_size == 0:
                    # Progress from 30% to 85% during trace creation
                    progress_pct = 0.3 + (0.55 * (idx + 1) / total_records)
                    progress_callback(int(total_records * progress_pct), f"Creating trace lines ({idx + 1:,}/{total_records:,})...")

            # Add all features to provider (correct pattern for memory layers)
            success, added_features = provider.addFeatures(all_features)
            print(f"Trace lines add features result: {success}, features added: {len(added_features) if success else 0}")

            layer.updateExtents()

            print(f"Trace layer feature count: {layer.featureCount()}")

            # Add to project
            QgsProject.instance().addMapLayer(layer, False)  # Don't add to legend yet

            return True, layer

        except Exception as e:
            log_error(f"Failed to create trace lines layer: {str(e)}")
            return False, None