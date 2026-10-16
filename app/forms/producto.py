"""
Formularios de productos y categorías.
"""

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    FloatField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    Length,
    NumberRange,
    Optional,
    ValidationError,
)

from ..models import Categoria, Producto


class FormularioProducto(FlaskForm):
    """
    Alta y edición de un producto.

    El mismo formulario sirve para las dos cosas. La diferencia la marca el
    parámetro producto_id del constructor:
      - Al crear:  producto_id = None
      - Al editar: producto_id = id del producto que se está editando

    Lo necesitamos para validar la referencia única: al editar, la referencia
    actual del propio producto no debe contar como "repetida".
    """

    referencia = StringField(
        "Referencia interna",
        validators=[
            DataRequired(message="La referencia es obligatoria."),
            Length(max=30),
        ],
        render_kw={"placeholder": "POR-001"},
    )

    nombre = StringField(
        "Nombre del producto",
        validators=[
            DataRequired(message="El nombre es obligatorio."),
            Length(min=2, max=150),
        ],
        render_kw={"placeholder": "Portátil Pro 15\" 16GB"},
    )

    descripcion = TextAreaField(
        "Descripción",
        validators=[Optional(), Length(max=1000)],
        render_kw={"placeholder": "Características, especificaciones..."},
    )

    # SelectField muestra un desplegable. coerce=int convierte el valor
    # recibido (que siempre llega como texto desde el navegador) a entero,
    # para que coincida con el tipo de la clave foránea.
    categoria_id = SelectField(
        "Categoría",
        coerce=int,
        validators=[DataRequired(message="Selecciona una categoría.")],
    )

    precio_venta = FloatField(
        "Precio de venta (€)",
        validators=[
            DataRequired(message="El precio de venta es obligatorio."),
            # NumberRange con min=0 impide precios negativos. Es una validación
            # de negocio: un precio negativo no significa nada y falsearía
            # todas las métricas de beneficio.
            NumberRange(min=0, message="El precio no puede ser negativo."),
        ],
        render_kw={"step": "0.01", "placeholder": "0.00"},
    )

    coste_adquisicion = FloatField(
        "Coste de adquisición (€)",
        validators=[
            Optional(),
            NumberRange(min=0, message="El coste no puede ser negativo."),
        ],
        render_kw={"step": "0.01", "placeholder": "0.00"},
    )

    # -- Venta por ración (barriles, botellas de licor, garrafas...) --------
    #
    # Estos cuatro campos solo se usan cuando se_vende_por_racion está
    # marcado. En ese caso, coste_adquisicion NO se rellena a mano: se
    # calcula en la ruta a partir de precio_envase, contenido_envase_ml y
    # tamano_racion_ml (ver routes/productos.py). El campo coste_adquisicion
    # de arriba sigue existiendo porque el resto de productos lo necesitan.
    se_vende_por_racion = BooleanField(
        "Este producto se compra en un envase grande y se vende por raciones "
        "(barril de cerveza, botella de licor...)",
        default=False,
    )

    precio_envase = FloatField(
        "Precio del envase completo (€)",
        validators=[Optional(), NumberRange(min=0, message="El precio no puede ser negativo.")],
        render_kw={"step": "0.01", "placeholder": "45.00"},
    )

    contenido_envase_ml = FloatField(
        "Contenido del envase (ml)",
        validators=[Optional(), NumberRange(min=1, message="Debe ser mayor que 0.")],
        render_kw={"placeholder": "30000  (barril de 30 L)"},
    )

    tamano_racion_ml = FloatField(
        "Tamaño de la ración (ml)",
        validators=[Optional(), NumberRange(min=1, message="Debe ser mayor que 0.")],
        render_kw={"placeholder": "300  (caña de 0,3 L)"},
    )

    nombre_racion = StringField(
        "Cómo se llama la ración",
        validators=[Optional(), Length(max=30)],
        render_kw={"placeholder": "caña, copa, chupito..."},
    )

    # Stock inicial: solo aparece al CREAR un producto.
    #
    # DECISIÓN IMPORTANTE: al editar no se puede tocar el stock a mano. Si se
    # pudiera, el campo stock_actual dejaría de cuadrar con el historial de
    # movimientos y perderíamos la trazabilidad que exige el requisito 3.
    # Para cambiar el stock hay que registrar un movimiento de inventario, que
    # deja constancia de quién, cuándo y por qué.
    stock_inicial = IntegerField(
        "Stock inicial (unidades)",
        validators=[Optional(), NumberRange(min=0, message="El stock no puede ser negativo.")],
        default=0,
    )

    stock_minimo = IntegerField(
        "Stock mínimo",
        validators=[
            DataRequired(message="Indica el stock mínimo."),
            NumberRange(min=0, message="El stock mínimo no puede ser negativo."),
        ],
        default=5,
    )

    ubicacion_almacen = StringField(
        "Ubicación en almacén",
        validators=[Optional(), Length(max=50)],
        render_kw={"placeholder": "Pasillo A · Estante 3"},
    )

    activo = BooleanField("Producto activo (visible en el catálogo)", default=True)

    submit = SubmitField("Guardar producto")

    def __init__(self, *args, producto_id=None, **kwargs):
        """
        Constructor personalizado.

        Hace dos cosas que no se pueden hacer de forma declarativa:

        1. Rellenar las opciones del desplegable de categorías. No pueden
           definirse arriba junto al campo, porque las opciones se leen de la
           base de datos y cambian: si se fijaran al importar el módulo, las
           categorías creadas después no aparecerían nunca.

        2. Guardar el id del producto que se edita, para el validador de
           referencia única.
        """
        # super() llama al constructor de FlaskForm, que es quien monta los
        # campos y lee los datos de la petición.
        super().__init__(*args, **kwargs)

        self.producto_id = producto_id

        # choices espera una lista de tuplas (valor, texto_visible).
        self.categoria_id.choices = [
            (c.id, c.nombre)
            for c in Categoria.query.order_by(Categoria.nombre).all()
        ]

    def validate_referencia(self, campo):
        """La referencia interna no puede repetirse entre productos."""
        referencia = campo.data.strip().upper()
        existente = Producto.query.filter_by(referencia=referencia).first()

        # Si existe otro producto con esa referencia Y no es el que estamos
        # editando, es un duplicado. Sin la segunda condición, editar un
        # producto sin cambiarle la referencia daría un falso error.
        if existente and existente.id != self.producto_id:
            raise ValidationError(
                f"La referencia {referencia} ya está asignada a «{existente.nombre}»."
            )

    def validate_precio_venta(self, campo):
        """
        Aviso si el producto se vendería por debajo de coste.

        No lo bloqueamos: hay motivos legítimos para vender a pérdida (liquidar
        stock obsoleto, una oferta de captación). Pero el margen quedaría
        negativo, así que lo advertimos para evitar errores de tecleo.
        """
        # Si el campo del coste se ocultó por permisos, no hay nada que comparar.
        #
        # OJO CON ESTA COMPROBACIÓN: "del formulario.campo" en WTForms NO borra
        # el atributo, lo deja valiendo None. Por eso hasattr() seguiría
        # devolviendo True y acceder a .data provocaría un AttributeError.
        # La comprobación válida es contra None.
        if getattr(self, "coste_adquisicion", None) is None:
            return

        coste = self.coste_adquisicion.data
        if coste and campo.data is not None and campo.data < coste:
            # Formateamos con coma decimal, como corresponde en español.
            # El mismo criterio que aplica el filtro |euros de las plantillas.
            precio_txt = f"{campo.data:.2f}".replace(".", ",")
            coste_txt = f"{coste:.2f}".replace(".", ",")
            raise ValidationError(
                f"El precio de venta ({precio_txt} €) es inferior al coste "
                f"({coste_txt} €): el producto se vendería con pérdidas."
            )

    def validate(self, extra_validators=None):
        """
        Validación adicional a nivel de formulario completo.

        Se usa cuando una regla depende de VARIOS campos a la vez (aquí, de
        se_vende_por_racion y de los tres campos del envase), algo que los
        validate_<campo> de arriba no pueden expresar por sí solos.
        """
        # Primero se ejecutan las validaciones normales, campo a campo.
        if not super().validate(extra_validators=extra_validators):
            return False

        if self.se_vende_por_racion.data:
            faltan = []
            # precio_envase puede no existir si la ruta lo ha ocultado por
            # falta de permiso financiero (ver _ocultar_campos_financieros
            # en routes/productos.py). En ese caso no se exige: el coste se
            # calculará más adelante, cuando lo complete alguien con permiso.
            precio_envase_visible = getattr(self, "precio_envase", None) is not None
            if precio_envase_visible and not self.precio_envase.data:
                faltan.append("precio del envase")
            if not self.contenido_envase_ml.data:
                faltan.append("contenido del envase")
            if not self.tamano_racion_ml.data:
                faltan.append("tamaño de la ración")
            if not self.nombre_racion.data:
                faltan.append("nombre de la ración")

            if faltan:
                mensaje = "Faltan datos para vender por ración: " + ", ".join(faltan) + "."
                # contenido_envase_ml siempre existe (a diferencia de
                # precio_envase, que puede estar oculto por permisos), así
                # que es un sitio seguro donde mostrar el error.
                self.contenido_envase_ml.errors.append(mensaje)
                return False

            # El tamaño de la ración no puede ser mayor que el envase entero:
            # no tendría sentido servir una copa más grande que la botella.
            if self.tamano_racion_ml.data > self.contenido_envase_ml.data:
                self.tamano_racion_ml.errors.append(
                    "La ración no puede ser mayor que el envase completo."
                )
                return False

        return True


class FormularioCategoria(FlaskForm):
    """Alta y edición de una categoría de producto."""

    nombre = StringField(
        "Nombre de la categoría",
        validators=[DataRequired(message="El nombre es obligatorio."), Length(min=2, max=80)],
        render_kw={"placeholder": "Portátiles"},
    )

    descripcion = StringField(
        "Descripción",
        validators=[Optional(), Length(max=255)],
        render_kw={"placeholder": "Equipos portátiles y ultrabooks"},
    )

    submit = SubmitField("Guardar categoría")

    def __init__(self, *args, categoria_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.categoria_id = categoria_id

    def validate_nombre(self, campo):
        """El nombre de la categoría no puede repetirse."""
        existente = Categoria.query.filter_by(nombre=campo.data.strip()).first()
        if existente and existente.id != self.categoria_id:
            raise ValidationError("Ya existe una categoría con ese nombre.")
