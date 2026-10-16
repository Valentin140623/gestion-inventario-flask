"""
Formulario de gestión de usuarios (uso exclusivo del administrador).
"""

from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    Optional,
    Regexp,
    ValidationError,
)

from ..models import RolUsuario, Usuario


class FormularioUsuario(FlaskForm):
    """
    Alta y edición de usuarios desde el panel de administración.

    Aquí sí hay campo de rol, al contrario que en el registro público: esta
    pantalla solo la puede abrir un administrador, así que no existe riesgo de
    que alguien se conceda permisos a sí mismo.
    """

    nombre = StringField(
        "Nombre y apellidos",
        validators=[DataRequired(message="El nombre es obligatorio."), Length(min=3, max=100)],
    )

    email = StringField(
        "Correo electrónico",
        validators=[DataRequired(message="El correo es obligatorio."),
                    Email(message="El formato del correo no es válido.")],
    )

    # Las opciones se construyen a partir del Enum: si algún día se añade un
    # rol nuevo, aparece solo en el desplegable sin tocar este formulario.
    rol = SelectField(
        "Rol",
        choices=[(r.name, r.value) for r in RolUsuario],
        validators=[DataRequired(message="Selecciona un rol.")],
    )

    password = PasswordField(
        "Contraseña",
        validators=[
            Optional(),
            Length(min=8, message="La contraseña debe tener al menos 8 caracteres."),
            Regexp(r"^(?=.*[A-Za-z])(?=.*\d).+$",
                   message="Debe combinar al menos una letra y un número."),
        ],
    )

    password2 = PasswordField(
        "Repite la contraseña",
        validators=[EqualTo("password", message="Las dos contraseñas no coinciden.")],
    )

    activo = BooleanField("Cuenta activa", default=True)

    submit = SubmitField("Guardar usuario")

    def __init__(self, *args, usuario_id=None, es_edicion=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario_id = usuario_id
        self.es_edicion = es_edicion

    def validate_email(self, campo):
        """El correo no puede estar ya en uso por otro usuario."""
        existente = Usuario.query.filter_by(email=campo.data.lower().strip()).first()
        if existente and existente.id != self.usuario_id:
            raise ValidationError("Ya existe otro usuario con este correo electrónico.")

    def validate_password(self, campo):
        """
        Al CREAR, la contraseña es obligatoria. Al EDITAR es opcional: si se
        deja en blanco se conserva la que ya tenía.
        """
        if not self.es_edicion and not campo.data:
            raise ValidationError("La contraseña es obligatoria al crear un usuario.")
