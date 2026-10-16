"""
Modelos Proveedor y ProductoProveedor.

Cubren el requisito 4 del enunciado: "Gestión avanzada de proveedores".
"""

from datetime import datetime

from ..extensions import db


class Proveedor(db.Model):
    """Empresa a la que compramos productos."""

    __tablename__ = "proveedores"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)

    # CIF: identificador fiscal único de la empresa. unique=True impide
    # duplicar el mismo proveedor por error.
    cif = db.Column(db.String(15), unique=True, nullable=False, index=True)

    persona_contacto = db.Column(db.String(120), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    telefono = db.Column(db.String(20), nullable=True)
    direccion = db.Column(db.String(255), nullable=True)

    # Condiciones de pago pactadas (ej. "60 días fecha factura").
    condiciones_pago = db.Column(db.String(100), nullable=True)

    # Plazo medio de entrega comprometido. Es un dato numérico y no texto
    # porque lo vamos a usar para comparar proveedores entre sí.
    plazo_entrega_dias = db.Column(db.Integer, nullable=False, default=7)

    activo = db.Column(db.Boolean, nullable=False, default=True)
    fecha_alta = db.Column(db.DateTime, nullable=False, default=datetime.now)
    observaciones = db.Column(db.Text, nullable=True)

    productos_asociados = db.relationship(
        "ProductoProveedor",
        back_populates="proveedor",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    compras = db.relationship("Compra", back_populates="proveedor", lazy="dynamic")

    @property
    def num_productos(self):
        """Cuántas referencias distintas nos suministra."""
        return self.productos_asociados.count()

    def __repr__(self):
        return f"<Proveedor {self.nombre} ({self.cif})>"


class ProductoProveedor(db.Model):
    """
    Tabla intermedia de la relación MUCHOS A MUCHOS entre productos y proveedores.

    El enunciado dice: "un producto puede estar asociado a varios proveedores".
    Y al revés, un proveedor nos vende muchos productos. Eso es una relación N:M,
    que en el modelo relacional siempre se resuelve con una tabla intermedia.

    IMPORTANTE: esta tabla no se limita a unir dos ids, sino que guarda datos
    PROPIOS de la relación: a qué precio nos vende ESE proveedor ESE producto,
    con qué referencia lo cataloga y en cuántos días lo sirve.

    Por eso la definimos como una clase completa (db.Model) y no con el atajo
    db.Table de SQLAlchemy: db.Table solo sirve cuando la relación no tiene
    atributos. Y son precisamente estos atributos los que hacen posible
    "comparar precios y condiciones entre proveedores" del requisito 4.
    """

    __tablename__ = "producto_proveedor"

    # Restricción de tabla: la pareja (producto, proveedor) no puede repetirse.
    # Impide dar de alta dos veces el mismo proveedor para el mismo producto.
    __table_args__ = (
        db.UniqueConstraint("producto_id", "proveedor_id", name="uq_producto_proveedor"),
    )

    id = db.Column(db.Integer, primary_key=True)

    producto_id = db.Column(db.Integer, db.ForeignKey("productos.id"), nullable=False)
    proveedor_id = db.Column(db.Integer, db.ForeignKey("proveedores.id"), nullable=False)

    producto = db.relationship("Producto", back_populates="proveedores_asociados")
    proveedor = db.relationship("Proveedor", back_populates="productos_asociados")

    # Precio al que este proveedor nos vende este producto.
    precio_coste = db.Column(db.Float, nullable=False, default=0.0)

    # Código con el que el proveedor identifica el producto en su catálogo
    # (normalmente distinto de nuestra referencia interna).
    referencia_proveedor = db.Column(db.String(50), nullable=True)

    # Plazo de entrega para este producto concreto: puede diferir del plazo
    # general del proveedor.
    plazo_entrega_dias = db.Column(db.Integer, nullable=False, default=7)

    # Cantidad mínima que hay que pedir para que el proveedor sirva el pedido.
    cantidad_minima_pedido = db.Column(db.Integer, nullable=False, default=1)

    # Marca cuál es el proveedor habitual para este producto.
    es_preferente = db.Column(db.Boolean, nullable=False, default=False)

    fecha_actualizacion = db.Column(
        db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    @property
    def coste_por_unidad_vendida(self):
        """
        Lo que cuesta UNA unidad de venta (una unidad normal, o una ración)
        comprándola a este proveedor.

        Para un producto normal, precio_coste ya es el precio por unidad y no
        hace falta convertir nada.

        Para un producto que se vende por ración (un barril de cerveza), el
        proveedor cobra por el ENVASE COMPLETO, no por la caña suelta: por
        eso precio_coste guarda el precio del barril entero, y aquí lo
        dividimos entre las raciones que salen de él para saber cuánto
        cuesta de verdad cada caña con este proveedor.
        """
        raciones = self.producto.raciones_por_envase
        if raciones:
            return self.precio_coste / raciones
        return self.precio_coste

    @property
    def margen_resultante(self):
        """
        Margen porcentual que obtendríamos comprando a ESTE proveedor.

        Permite ver de un vistazo cómo afecta al beneficio elegir un proveedor
        u otro, que es justo lo que pide el enunciado.
        """
        pvp = self.producto.precio_venta
        if not pvp:
            return 0.0
        return ((pvp - self.coste_por_unidad_vendida) / pvp) * 100

    def __repr__(self):
        return f"<ProductoProveedor prod={self.producto_id} prov={self.proveedor_id} {self.precio_coste}€>"
