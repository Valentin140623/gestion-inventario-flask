"""
Paquete de modelos.

Reexportamos aquí todas las clases para poder escribir en el resto del proyecto:

    from app.models import Producto, Venta

en lugar de la ruta completa de cada fichero.

Además, este fichero cumple una función técnica imprescindible: SQLAlchemy solo
crea las tablas de las clases que se hayan IMPORTADO antes de llamar a
db.create_all(). Como app/__init__.py importa este paquete, con una sola línea
quedan registrados todos los modelos.
"""

from .compra import Compra, LineaCompra
from .inventario import MovimientoInventario, TipoMovimiento
from .producto import Categoria, Producto
from .proveedor import ProductoProveedor, Proveedor
from .usuario import PERMISOS_POR_ROL, RolUsuario, Usuario
from .venta import LineaVenta, Venta

# __all__ declara qué nombres se exportan con "from app.models import *".
# Sirve también como índice legible de todo el modelo de datos.
__all__ = [
    "Usuario",
    "RolUsuario",
    "PERMISOS_POR_ROL",
    "Categoria",
    "Producto",
    "Proveedor",
    "ProductoProveedor",
    "Venta",
    "LineaVenta",
    "Compra",
    "LineaCompra",
    "MovimientoInventario",
    "TipoMovimiento",
]
