"""
Modelos Venta y LineaVenta.

Implementan la parte de ventas del requisito 3: "registrar ventas que
actualicen automáticamente el stock".
"""

from datetime import datetime

from ..extensions import db


class Venta(db.Model):
    """
    Cabecera de una venta (el "ticket" o factura).

    Guarda los datos comunes: cuándo, a quién y quién la registró. Los
    productos vendidos van en la tabla lineas_venta.
    """

    __tablename__ = "ventas"

    id = db.Column(db.Integer, primary_key=True)

    # Número de documento legible para el usuario (V-2026-0001). El id de la
    # base de datos es un detalle interno; el número de venta es lo que
    # aparece en los listados y en los informes.
    numero = db.Column(db.String(20), unique=True, nullable=False, index=True)

    # index=True porque casi todas las consultas de análisis filtran u ordenan
    # por fecha ("beneficio entre dos fechas", "evolución por periodo"). Un
    # índice hace esas consultas mucho más rápidas.
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)

    cliente = db.Column(db.String(150), nullable=True)

    # Quién registró la venta. Nos da trazabilidad: siempre se sabe qué
    # usuario hizo cada operación.
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    usuario = db.relationship("Usuario", back_populates="ventas")

    observaciones = db.Column(db.Text, nullable=True)

    # Una venta tiene muchas líneas. cascade="all, delete-orphan" significa:
    # si se borra la venta, se borran sus líneas (no tiene sentido que
    # sobrevivan líneas huérfanas sin cabecera).
    lineas = db.relationship(
        "LineaVenta",
        back_populates="venta",
        cascade="all, delete-orphan",
    )

    # -- Totales calculados -------------------------------------------------
    # Igual que con el margen del producto: son datos derivados de las líneas,
    # así que los calculamos en vez de guardarlos, para que sea imposible que
    # el total no cuadre con el detalle.

    @property
    def total(self):
        """Importe total facturado (suma de los subtotales de cada línea)."""
        return sum(linea.subtotal for linea in self.lineas)

    @property
    def total_coste(self):
        """Lo que nos costó a nosotros la mercancía vendida."""
        return sum(linea.cantidad * linea.coste_unitario for linea in self.lineas)

    @property
    def beneficio(self):
        """Beneficio bruto de la venta: lo que ingresamos menos lo que costó."""
        return self.total - self.total_coste

    @property
    def margen_porcentual(self):
        """Margen de la venta completa, en porcentaje sobre el total."""
        if not self.total:
            return 0.0
        return (self.beneficio / self.total) * 100

    @property
    def num_articulos(self):
        """Número total de unidades vendidas en esta venta."""
        return sum(linea.cantidad for linea in self.lineas)

    def __repr__(self):
        return f"<Venta {self.numero} - {self.total:.2f}€>"


class LineaVenta(db.Model):
    """
    Cada producto incluido en una venta.

    Es la tabla intermedia que resuelve el "una venta puede incluir varios
    productos" del enunciado (relación N:M entre ventas y productos).
    """

    __tablename__ = "lineas_venta"

    id = db.Column(db.Integer, primary_key=True)

    venta_id = db.Column(db.Integer, db.ForeignKey("ventas.id"), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey("productos.id"), nullable=False)

    venta = db.relationship("Venta", back_populates="lineas")
    producto = db.relationship("Producto", back_populates="lineas_venta")

    cantidad = db.Column(db.Integer, nullable=False, default=1)

    # ---------------------------------------------------------------------
    # Estos dos campos son la decisión de diseño más importante del modelo.
    #
    # Podríamos leer el precio y el coste desde producto.precio_venta y
    # producto.coste_adquisicion en lugar de duplicarlos aquí. Sería un error:
    # esos campos cambian con el tiempo. Si en enero vendimos a 100€ un producto
    # que costaba 70€, y en marzo el proveedor sube el coste a 90€, el beneficio
    # de la venta de enero seguiría siendo 30€... pero la aplicación mostraría
    # 10€, porque estaría usando el coste actual.
    #
    # Guardando una COPIA del precio y del coste en el momento de la venta,
    # el histórico queda congelado y las métricas de beneficio son fieles a la
    # realidad. Esta es la única redundancia intencionada del modelo: aquí no
    # es un dato derivado, es un dato histórico.
    # ---------------------------------------------------------------------
    precio_unitario = db.Column(db.Float, nullable=False)
    coste_unitario = db.Column(db.Float, nullable=False)

    @property
    def subtotal(self):
        """Importe de esta línea."""
        return self.cantidad * self.precio_unitario

    @property
    def beneficio(self):
        """Beneficio bruto obtenido con esta línea."""
        return (self.precio_unitario - self.coste_unitario) * self.cantidad

    @property
    def margen_porcentual(self):
        """Margen de esta línea, en porcentaje."""
        if not self.precio_unitario:
            return 0.0
        return ((self.precio_unitario - self.coste_unitario) / self.precio_unitario) * 100

    def __repr__(self):
        return f"<LineaVenta venta={self.venta_id} prod={self.producto_id} x{self.cantidad}>"
