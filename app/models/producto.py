"""
Modelos Categoria y Producto.

Van juntos en el mismo fichero porque son inseparables: un producto siempre
pertenece a una categoría.
"""

from datetime import datetime

from ..extensions import db


class Categoria(db.Model):
    """Familia a la que pertenece un producto (Entrantes, Bebidas, Postres...)."""

    __tablename__ = "categorias"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), unique=True, nullable=False)
    descripcion = db.Column(db.String(255), nullable=True)

    # Relación "uno a muchos": una categoría tiene muchos productos.
    # lazy="dynamic" hace que categoria.productos devuelva una CONSULTA en vez
    # de una lista ya cargada: así podemos seguir filtrando
    # (categoria.productos.filter_by(activo=True)) sin traer todo de la BD.
    productos = db.relationship("Producto", back_populates="categoria", lazy="dynamic")

    def __repr__(self):
        return f"<Categoria {self.nombre}>"


class Producto(db.Model):
    """
    Producto del catálogo.

    Contiene los campos que pide el enunciado: nombre, categoría, precio de
    venta, coste de adquisición, margen (calculado), stock actual y referencia
    interna; más algunos campos adicionales útiles para la gestión.
    """

    __tablename__ = "productos"

    id = db.Column(db.Integer, primary_key=True)

    # Referencia interna de la empresa (SKU). Única: es el código con el que
    # el almacén identifica el producto.
    referencia = db.Column(db.String(30), unique=True, nullable=False, index=True)

    nombre = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)

    # Clave foránea: enlaza este producto con una fila de la tabla categorias.
    categoria_id = db.Column(db.Integer, db.ForeignKey("categorias.id"), nullable=False)
    categoria = db.relationship("Categoria", back_populates="productos")

    # Precio al que se lo vendemos al cliente (sin IVA).
    precio_venta = db.Column(db.Float, nullable=False, default=0.0)

    # Coste al que nosotros lo compramos. Es el coste de referencia actual;
    # el coste real de cada compra concreta se guarda en las líneas de compra.
    coste_adquisicion = db.Column(db.Float, nullable=False, default=0.0)

    # Unidades disponibles ahora mismo. Este campo NO se toca a mano desde las
    # vistas: solo lo modifica el servicio de inventario, que a la vez registra
    # el movimiento correspondiente. Así stock e historial nunca se desincronizan.
    stock_actual = db.Column(db.Integer, nullable=False, default=0)

    # Umbral por debajo del cual hay que reponer.
    stock_minimo = db.Column(db.Integer, nullable=False, default=5)

    ubicacion_almacen = db.Column(db.String(50), nullable=True)

    # -- Venta por ración (bebidas de barril o botella) ---------------------
    #
    # Algunos productos no se compran y se venden en la misma unidad: un
    # barril de cerveza de 30 L se compra entero pero se vende por cañas de
    # 0,3 L. Estos tres campos describen esa conversión.
    #
    # IMPORTANTE: coste_adquisicion y stock_actual (arriba) siempre se
    # guardan en la unidad que se VENDE (la copa/ración), nunca en el
    # envase completo. Así el resto de la aplicación (margen, alertas,
    # informes) no necesita saber nada de barriles: para ella este producto
    # es una unidad más con su coste y su stock, igual que cualquier otro.
    se_vende_por_racion = db.Column(db.Boolean, nullable=False, default=False)

    # Contenido total del envase de compra, en mililitros (30000 = barril de 30 L).
    contenido_envase_ml = db.Column(db.Float, nullable=True)

    # Tamaño de la ración de venta, en mililitros (300 = caña de 0,3 L).
    tamano_racion_ml = db.Column(db.Float, nullable=True)

    # Nombre de la ración para mostrarlo en pantalla ("caña", "copa", "chupito").
    nombre_racion = db.Column(db.String(30), nullable=True)

    # Baja lógica: en vez de borrar el producto (lo que rompería el histórico
    # de ventas), lo marcamos como inactivo y deja de aparecer en el catálogo.
    activo = db.Column(db.Boolean, nullable=False, default=True)

    fecha_alta = db.Column(db.DateTime, nullable=False, default=datetime.now)

    # Relaciones hacia las tablas que dependen de este producto.
    # cascade="all, delete-orphan": si algún día se borra físicamente un
    # producto, se borran también sus enlaces con proveedores y sus movimientos.
    proveedores_asociados = db.relationship(
        "ProductoProveedor",
        back_populates="producto",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    lineas_venta = db.relationship("LineaVenta", back_populates="producto", lazy="dynamic")
    lineas_compra = db.relationship("LineaCompra", back_populates="producto", lazy="dynamic")
    movimientos = db.relationship(
        "MovimientoInventario",
        back_populates="producto",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    # -- Campos calculados automáticamente ---------------------------------
    #
    # El enunciado pide que el margen se calcule automáticamente. Lo hacemos
    # con @property: son atributos que NO se guardan en la base de datos, sino
    # que se calculan al vuelo cada vez que se consultan.
    #
    # ¿Por qué no guardarlo como una columna más?
    # Porque es un DATO DERIVADO: depende de precio_venta y coste_adquisicion.
    # Si lo guardásemos, cada vez que alguien cambiara el precio habría que
    # acordarse de recalcular el margen; si se olvida una sola vez, la base de
    # datos queda inconsistente. Calculándolo al vuelo, es imposible que se
    # desincronice. En diseño de bases de datos esto se llama evitar redundancia.
    #
    # Desde una plantilla HTML se usa igual que un campo normal:
    #   {{ producto.margen_porcentual }}     (sin paréntesis, gracias a @property)

    @property
    def margen_unitario(self):
        """Beneficio en euros por cada unidad vendida."""
        return self.precio_venta - self.coste_adquisicion

    @property
    def margen_porcentual(self):
        """
        Margen sobre el precio de venta, en porcentaje.

        Fórmula: (precio_venta - coste) / precio_venta * 100

        Usamos el precio de venta como base (margen comercial) y no el coste
        (que sería el "markup"), porque es el criterio habitual en distribución
        y el que permite comparar productos entre sí.

        Protegemos la división: si el precio de venta es 0, devolvemos 0 en vez
        de provocar un ZeroDivisionError que tumbaría la página.
        """
        if not self.precio_venta:
            return 0.0
        return (self.margen_unitario / self.precio_venta) * 100

    @property
    def valor_stock(self):
        """Dinero inmovilizado en almacén por este producto, valorado a coste."""
        return self.stock_actual * self.coste_adquisicion

    @property
    def necesita_reposicion(self):
        """True si el stock ha caído hasta el mínimo definido."""
        return self.stock_actual <= self.stock_minimo

    @property
    def raciones_por_envase(self):
        """
        Cuántas raciones (cañas, copas...) salen de un envase completo.

        Ejemplo: barril de 30000 ml ÷ caña de 300 ml = 100 cañas.

        Devuelve None si el producto no se vende por ración, o si falta
        algún dato para calcularlo.
        """
        if not self.se_vende_por_racion:
            return None
        if not self.contenido_envase_ml or not self.tamano_racion_ml:
            return None
        return self.contenido_envase_ml / self.tamano_racion_ml

    @property
    def nombre_unidad_venta(self):
        """Texto de la unidad de venta, para las plantillas ("caña", "unidad")."""
        if self.se_vende_por_racion and self.nombre_racion:
            return self.nombre_racion
        return "unidad"

    @property
    def proveedor_preferente(self):
        """
        Devuelve la asociación con el proveedor marcado como preferente.

        Si no hay ninguno marcado, devuelve el de menor precio de coste, que es
        la elección lógica por defecto. Si el producto no tiene proveedores,
        devuelve None.
        """
        asociaciones = self.proveedores_asociados.all()
        if not asociaciones:
            return None
        preferentes = [a for a in asociaciones if a.es_preferente]
        if preferentes:
            return preferentes[0]
        # min() con key: recorre la lista y devuelve el elemento cuyo
        # precio_coste sea el más bajo.
        return min(asociaciones, key=lambda a: a.precio_coste)

    def __repr__(self):
        return f"<Producto {self.referencia} - {self.nombre}>"
