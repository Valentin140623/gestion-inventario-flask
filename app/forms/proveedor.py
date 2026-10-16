"""
Formularios de proveedores.
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
    Email,
    Length,
    NumberRange,
    Optional,
    ValidationError,
)

from ..models import Producto, Proveedor


class FormularioProveedor(FlaskForm):
    """Alta y edición de un proveedor."""

    nombre = StringField(
        "Nombre / Razón social",
        validators=[DataRequired(message="El nombre es obligatorio."), Length(min=2, max=150)],
        render_kw={"placeholder": "Distribuciones Hostelería S.L."},
    )

    cif = StringField(
        "CIF",
        validators=[DataRequired(message="El CIF es obligatorio."), Length(min=8, max=15)],
        render_kw={"placeholder": "B12345678"},
    )

    persona_contacto = StringField(
        "Persona de contacto",
        validators=[Optional(), Length(max=120)],
        render_kw={"placeholder": "Nombre del comercial"},
    )

    email = StringField(
        "Correo electrónico",
        validators=[Optional(), Email(message="El formato del correo no es válido."), Length(max=120)],
        render_kw={"placeholder": "pedidos@proveedor.com"},
    )

    telefono = StringField(
        "Teléfono",
        validators=[Optional(), Length(max=20)],
        render_kw={"placeholder": "600 000 000"},
    )

    direccion = StringField(
        "Dirección",
        validators=[Optional(), Length(max=255)],
        render_kw={"placeholder": "Calle, número, población"},
    )

    condiciones_pago = StringField(
        "Condiciones de pago",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "60 días fecha factura"},
    )

    plazo_entrega_dias = IntegerField(
        "Plazo de entrega (días)",
        validators=[DataRequired(message="Indica el plazo de entrega."),
                    NumberRange(min=0, message="El plazo no puede ser negativo.")],
        default=7,
    )

    observaciones = TextAreaField("Observaciones", validators=[Optional(), Length(max=1000)])

    activo = BooleanField("Proveedor activo", default=True)

    submit = SubmitField("Guardar proveedor")

    def __init__(self, *args, proveedor_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.proveedor_id = proveedor_id

    def validate_cif(self, campo):
        """El CIF identifica de forma única a la empresa: no puede repetirse."""
        cif = campo.data.strip().upper()
        existente = Proveedor.query.filter_by(cif=cif).first()
        if existente and existente.id != self.proveedor_id:
            raise ValidationError(f"El CIF {cif} ya está registrado en «{existente.nombre}».")


class FormularioAsociarProducto(FlaskForm):
    """
    Asocia un producto a un proveedor con su precio y condiciones.

    Es el formulario que alimenta la tabla producto_proveedor, la que permite
    después comparar precios entre proveedores.
    """

    producto_id = SelectField("Producto", coerce=int, validators=[DataRequired()])

    precio_coste = FloatField(
        "Precio de coste (€)",
        validators=[DataRequired(message="Indica el precio."),
                    NumberRange(min=0, message="El precio no puede ser negativo.")],
        render_kw={"step": "0.01"},
    )

    referencia_proveedor = StringField(
        "Referencia del proveedor",
        validators=[Optional(), Length(max=50)],
        render_kw={"placeholder": "Código en su catálogo"},
    )

    plazo_entrega_dias = IntegerField(
        "Plazo de entrega (días)",
        validators=[DataRequired(), NumberRange(min=0)],
        default=7,
    )

    cantidad_minima_pedido = IntegerField(
        "Cantidad mínima de pedido",
        validators=[DataRequired(), NumberRange(min=1)],
        default=1,
    )

    es_preferente = BooleanField("Marcar como proveedor preferente de este producto")

    submit = SubmitField("Asociar producto")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.producto_id.choices = [
            (p.id, f"{p.referencia} · {p.nombre}")
            for p in Producto.query.filter_by(activo=True).order_by(Producto.nombre).all()
        ]
