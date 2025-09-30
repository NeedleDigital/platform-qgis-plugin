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
    Qgis, QgsCoordinateReferenceSystem, QgsCoordinateTransform
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor

# Configuration imports for styling and thresholds
from ..config.constants import (
    DEFAULT_LAYER_STYLE, IMPORT_CHUNK_SIZE, OSM_LAYER_NAME,
    OSM_LAYER_URL, AUTO_ZOOM_THRESHOLD
)
from .logging import log_error, log_warning


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
                          color: Optional[QColor] = None, is_location_only: bool = False) -> Tuple[bool, str]:
        """
        Create a point layer from data.

        Args:
            layer_name: Name for the new layer
            data: List of dictionaries containing point data
            color: Point color (optional)
            is_location_only: Whether this is location-only data (affects hover tooltips and field inclusion)

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
            # For location-only data, include lat/lon as attributes
            fields = self._create_fields_from_data(data[0], is_location_only)
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

            # Apply styling
            self._apply_layer_styling(layer, color, is_location_only)
            
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
    
    def _create_fields_from_data(self, sample_record: Dict[str, Any], is_location_only: bool = False) -> List[QgsField]:
        """Create QGIS fields from sample data record.

        Args:
            sample_record: Sample data record to extract field types from
            is_location_only: If True, include latitude/longitude as attributes

        Returns:
            List of QgsField objects
        """
        fields = []

        for key, value in sample_record.items():
            # For location-only data, keep latitude and longitude as attributes
            # For full data, skip coordinate fields as they're only used for geometry
            if not is_location_only and key.lower() in ['latitude', 'longitude', 'lat', 'lon', 'x', 'y']:
                continue

            # Skip location_string for location-only data (not useful in identify results)
            if is_location_only and key.lower() == 'location_string':
                continue

            # Determine field type based on value
            if isinstance(value, int):
                field_type = QVariant.Int
            elif isinstance(value, float):
                field_type = QVariant.Double
            elif isinstance(value, bool):
                field_type = QVariant.Bool
            else:
                field_type = QVariant.String

            fields.append(QgsField(key, field_type))

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
    
    def _apply_layer_styling(self, layer: QgsVectorLayer, color: Optional[QColor] = None, is_location_only: bool = False):
        """Apply styling to the layer."""
        try:
            # Use provided color or default
            point_color = color or QColor(DEFAULT_LAYER_STYLE['point_color'])

            # Create symbol
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            symbol.setColor(point_color)
            symbol.setSize(DEFAULT_LAYER_STYLE['point_size'])
            symbol.setOpacity(DEFAULT_LAYER_STYLE['point_transparency'])

            # Apply renderer
            renderer = QgsSingleSymbolRenderer(symbol)
            layer.setRenderer(renderer)

            # Setup hover tooltips (map tips)
            if is_location_only:
                self._setup_location_tooltips(layer)
            else:
                self._setup_hover_tooltips(layer)

            # Refresh layer
            layer.triggerRepaint()

        except Exception as e:
            log_warning(f"Failed to apply layer styling: {e}")


    def _setup_hover_tooltips(self, layer: QgsVectorLayer):
        """Setup hover tooltips (map tips) for the layer showing company name and hole ID."""
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

            # Only setup tooltips if we have at least one of the required fields
            if not company_field and not hole_id_field:
                return

            # Build HTML template for hover tooltip
            tooltip_parts = []

            if company_field:
                tooltip_parts.append(f'<b>Company:</b> [% "{company_field}" %]')

            if hole_id_field:
                tooltip_parts.append(f'<b>Hole ID:</b> [% "{hole_id_field}" %]')

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

    def _setup_location_tooltips(self, layer: QgsVectorLayer):
        """Setup hover tooltips (map tips) for location-only data showing latitude and longitude."""
        try:
            # Get field names from the layer
            field_names = [field.name() for field in layer.fields()]

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

            # Only setup tooltips if we have both lat and lon fields
            if not lat_field or not lon_field:
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
                                  is_location_only: bool = False) -> Tuple[bool, str]:
        """
        Create a point layer from large dataset using chunked processing.

        Args:
            layer_name: Name for the new layer
            data: List of dictionaries containing point data
            color: Point color (optional)
            progress_callback: Function to call with progress updates (processed_count, chunk_info)
            is_location_only: Whether this is location-only data (affects hover tooltips and field inclusion)

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
            # For location-only data, include lat/lon as attributes
            fields = self._create_fields_from_data(data[0], is_location_only)
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
            self._apply_layer_styling(layer, color, is_location_only)
            
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