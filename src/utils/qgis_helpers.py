"""
QGIS integration utilities for the Needle Digital Mining Data Importer plugin.
"""

from typing import List, Dict, Any, Optional, Tuple
from qgis.core import (
    QgsVectorLayer, QgsFeature, QgsGeometry, QgsPoint, QgsField, 
    QgsProject, QgsSymbol, QgsSingleSymbolRenderer, QgsMessageLog,
    Qgis, QgsCoordinateReferenceSystem
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor

from ..config.constants import DEFAULT_LAYER_STYLE
from .logging import get_logger

logger = get_logger(__name__)

class QGISLayerManager:
    """Helper class for managing QGIS layers."""
    
    def __init__(self, iface=None):
        """
        Initialize the layer manager.
        
        Args:
            iface: QGIS interface instance
        """
        self.iface = iface
    
    def create_point_layer(self, layer_name: str, data: List[Dict[str, Any]], 
                          color: Optional[QColor] = None) -> Tuple[bool, str]:
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
            
            # Create layer with CRS (Australian GDA2020)
            crs = QgsCoordinateReferenceSystem("EPSG:7844")
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
            
            # Apply styling
            self._apply_layer_styling(layer, color)
            
            # Add to project
            QgsProject.instance().addMapLayer(layer)
            
            # Zoom to layer if interface available
            if self.iface:
                self.iface.zoomToActiveLayer()
            
            logger.info(f"Created layer '{layer_name}' with {len(features)} features")
            return True, f"Successfully imported {len(features)} records"
            
        except Exception as e:
            error_msg = f"Failed to create layer: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def _create_fields_from_data(self, sample_record: Dict[str, Any]) -> List[QgsField]:
        """Create QGIS fields from sample data record."""
        fields = []
        
        for key, value in sample_record.items():
            # Skip coordinate fields as they're handled separately
            if key.lower() in ['latitude', 'longitude', 'lat', 'lon', 'x', 'y']:
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
                logger.warning(f"Skipping record with invalid coordinates: {record}")
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
            logger.error(f"Failed to create feature from record {record}: {e}")
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
    
    def _apply_layer_styling(self, layer: QgsVectorLayer, color: Optional[QColor] = None):
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
            
            # Refresh layer
            layer.triggerRepaint()
            
        except Exception as e:
            logger.warning(f"Failed to apply layer styling: {e}")
    
    def show_message(self, message: str, level: Qgis.MessageLevel = Qgis.Info, 
                    duration: int = 3) -> None:
        """Show message in QGIS interface."""
        try:
            if self.iface:
                self.iface.messageBar().pushMessage("Needle Digital", message, level, duration)
            else:
                # Fallback to message log
                QgsMessageLog.logMessage(f"Needle Digital: {message}", "Plugins", level)
        except Exception as e:
            logger.error(f"Failed to show message: {e}")