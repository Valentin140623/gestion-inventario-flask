"""
Modelo MovimientoInventario.

Cubre el requisito 3: "Debe existir un historial completo de movimientos de
inventario (entradas, salidas y ajustes)".

Este modelo funciona como un LIBRO DIARIO del almacén: cada vez que el stock de
un producto cambia, por el motivo que sea, se anota aquí una línea que nunca se
modifica ni se borra. El campo stock_actual del producto es solo la "foto" del
momento presente; esta tabla es la película completa de cómo se llegó hasta ahí.

Gracias a ella se puede auditar cualquier descuadre: si el stock no cuadra con
el almacén físico, se recorre el historial y se ve exactamente qué pasó, cuándo
y qué usuario lo hizo.
"""

import enum
from datetime import datetime

from ..extensions import db


class TipoMovimiento(enum.Enum):
    """Los tres tipos de movimiento que contempla el enunciado."""

    ENTRADA = "Entrada"   # Llega mercancía (compra a proveedor, devolución de cliente)
    SALIDA = "Salida"     # Sale mercancía (venta, rotura, devolución a proveedor)
    AJUSTE = "Ajuste"     # Corrección tras un inventario físico


class MovimientoInventario(db.Model):
    """Una anotación en el historial de inventario."""

    __tablename__ = "movimientos_inventario"

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)

    producto_id = db.Column(db.Integer, db.ForeignKey("productos.id"), nullable=False)
    producto = db.relationship("Producto", back_populates="movimientos")

    tipo = db.Column(db.Enum(TipoMovimiento), nullable=False)

    # Cantidad CON SIGNO: positiva si el stock aumenta, negativa si disminuye.
    #
    # Alternativa descartada: guardar siempre cantidades positivas y deducir el
    # signo del tipo de movimiento. Se descartó porque los ajustes pueden ir en
    # las dos direcciones (un recuento físico puede dar más o menos unidades de
    # las esperadas), y porque con el signo incorporado sumar la columna da
    # directamente la variación neta de stock de un periodo.
    cantidad = db.Column(db.Integer, nullable=False)

    # Stock que quedó DESPUÉS de aplicar este movimiento.
    #
    # Es información redundante (podría recalcularse sumando todos los
    # movimientos anteriores), pero se guarda a propósito: permite reconstruir
    # el stock de cualquier fecha pasada con una sola consulta, en vez de tener
    # que recorrer y sumar todo el histórico. Es la misma idea que el saldo que
    # aparece en cada línea del extracto bancario.
    stock_resultante = db.Column(db.Integer, nullable=False)

    # Explicación legible del movimiento ("Venta V-2026-0001", "Rotura").
    motivo = db.Column(db.String(200), nullable=True)

    # Documento que originó el movimiento, si lo hay. Lo guardamos como texto
    # ("V-2026-0001", "C-2026-0004") en lugar de como clave foránea porque un
    # movimiento puede venir de una venta, de una compra o de nada (un ajuste
    # manual): una única clave foránea no podría apuntar a tres tablas distintas.
    documento_referencia = db.Column(db.String(20), nullable=True, index=True)

    # Quién lo hizo: trazabilidad completa.
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    usuario = db.relationship("Usuario", back_populates="movimientos")

    @property
    def es_entrada(self):
        """True si el movimiento suma unidades al almacén."""
        return self.cantidad > 0

    def __repr__(self):
        signo = "+" if self.cantidad > 0 else ""
        return f"<Movimiento {self.tipo.value} prod={self.producto_id} {signo}{self.cantidad}>"
