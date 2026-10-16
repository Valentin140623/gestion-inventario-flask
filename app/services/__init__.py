"""
Paquete de servicios: la lógica de negocio de la aplicación.

Aquí vive todo lo que NO es ni base de datos ni interfaz: las reglas de la
empresa. Mantenerlo separado de las vistas tiene tres ventajas:

  - Se puede probar sin levantar el servidor web.
  - La misma función sirve para una vista web, un comando de consola o un
    informe en PDF, sin duplicar nada.
  - Las vistas quedan cortas y legibles: reciben datos, llaman al servicio y
    devuelven una plantilla.
"""

from .inventario import (
    ErrorInventario,
    ajustar_stock,
    entrada_stock,
    registrar_movimiento,
    salida_stock,
)
from .ventas import anular_venta, crear_compra, crear_venta, generar_numero

__all__ = [
    "ErrorInventario",
    "registrar_movimiento",
    "entrada_stock",
    "salida_stock",
    "ajustar_stock",
    "crear_venta",
    "anular_venta",
    "crear_compra",
    "generar_numero",
]
