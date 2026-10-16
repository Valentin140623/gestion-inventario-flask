"""
Modelos Compra y LineaCompra.

El enunciado pide, en el requisito 4, "almacenar histórico de compras" a los
proveedores. Estas dos tablas son ese histórico, y son las que permiten después
calcular qué proveedor resulta más rentable o eficiente.

La estructura es simétrica a la de las ventas (cabecera + líneas), porque el
problema es el mismo: un documento que incluye varios productos.
"""

from datetime import datetime

from ..extensions import db


class Compra(db.Model):
    """Pedido de compra realizado a un proveedor."""

    __tablename__ = "compras"

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), unique=True, nullable=False, index=True)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)

    proveedor_id = db.Column(db.Integer, db.ForeignKey("proveedores.id"), nullable=False)
    proveedor = db.relationship("Proveedor", back_populates="compras")

    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    usuario = db.relationship("Usuario", back_populates="compras")

    # Fecha en la que la mercancía llegó realmente al almacén. Comparándola
    # con la fecha del pedido obtenemos el plazo de entrega REAL, que es la
    # métrica que de verdad permite evaluar la eficiencia de un proveedor
    # (frente al plazo que promete en el contrato).
    fecha_recepcion = db.Column(db.DateTime, nullable=True)

    observaciones = db.Column(db.Text, nullable=True)

    lineas = db.relationship(
        "LineaCompra",
        back_populates="compra",
        cascade="all, delete-orphan",
    )

    @property
    def total(self):
        """Importe total de la compra."""
        return sum(linea.subtotal for linea in self.lineas)

    @property
    def num_articulos(self):
        """Unidades totales recibidas."""
        return sum(linea.cantidad for linea in self.lineas)

    @property
    def dias_entrega_real(self):
        """
        Días que tardó realmente en llegar el pedido.

        Devuelve None si aún no se ha recibido. El atributo .days de un
        timedelta (la resta de dos fechas) nos da los días enteros.
        """
        if not self.fecha_recepcion:
            return None
        return (self.fecha_recepcion - self.fecha).days

    def __repr__(self):
        return f"<Compra {self.numero} - {self.total:.2f}€>"


class LineaCompra(db.Model):
    """Cada producto incluido en un pedido de compra."""

    __tablename__ = "lineas_compra"

    id = db.Column(db.Integer, primary_key=True)

    compra_id = db.Column(db.Integer, db.ForeignKey("compras.id"), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey("productos.id"), nullable=False)

    compra = db.relationship("Compra", back_populates="lineas")
    producto = db.relationship("Producto", back_populates="lineas_compra")

    cantidad = db.Column(db.Integer, nullable=False, default=1)

    # Precio pagado en ESTA compra concreta. Por el mismo motivo que en las
    # ventas: es un dato histórico, no debe cambiar si mañana cambia la tarifa.
    # Comparar este campo entre proveedores a lo largo del tiempo es lo que
    # permite detectar quién sube precios y quién los mantiene.
    precio_unitario = db.Column(db.Float, nullable=False)

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def __repr__(self):
        return f"<LineaCompra compra={self.compra_id} prod={self.producto_id} x{self.cantidad}>"
