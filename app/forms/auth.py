"""
Formularios de autenticación (registro e inicio de sesión).

Usamos Flask-WTF en lugar de leer los datos a mano con request.form porque nos
da tres cosas de golpe:

  1. VALIDACIÓN declarativa: se describe qué debe cumplir cada campo y la
     librería se encarga de comprobarlo y de generar los mensajes de error.
  2. Protección CSRF automática: cada formulario incluye un token secreto. Sin
     él, una web maliciosa podría enviar peticiones en nombre de un usuario que
     tenga la sesión abierta en nuestra aplicación.
  3. Repintado del formulario: si la validación falla, los campos se vuelven a
     mostrar con lo que el usuario había escrito, sin perder los datos.

REGLA DE SEGURIDAD IMPORTANTE: nunca hay que fiarse de la validación del
navegador (los atributos required, type="email" de HTML5). Cualquiera puede
saltársela enviando la petición con otra herramienta. La validación que cuenta
es siempre la del servidor, que es esta.
"""

from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    Regexp,
    ValidationError,
)

from ..models import Usuario


class FormularioLogin(FlaskForm):
    """Formulario de inicio de sesión."""

    # Cada atributo de clase se convierte en un campo del formulario.
    # El primer argumento es la etiqueta visible; validators es la lista de
    # comprobaciones que debe superar.
    email = StringField(
        "Correo electrónico",
        validators=[
            DataRequired(message="Introduce tu correo electrónico."),
            Email(message="El formato del correo no es válido."),
        ],
        # render_kw añade atributos HTML al campo. Aquí lo usamos para las
        # clases CSS y el texto de ayuda dentro de la caja.
        render_kw={"placeholder": "usuario@empresa.com", "autofocus": True},
    )

    password = PasswordField(
        "Contraseña",
        validators=[DataRequired(message="Introduce tu contraseña.")],
        render_kw={"placeholder": "••••••••"},
    )

    # Casilla "recordarme": hace que la sesión sobreviva al cierre del
    # navegador (Flask-Login guarda una cookie de larga duración).
    recordarme = BooleanField("Mantener la sesión iniciada")

    submit = SubmitField("Entrar")


class FormularioRegistro(FlaskForm):
    """
    Formulario de alta de un nuevo usuario.

    DECISIÓN DE SEGURIDAD: este formulario NO tiene campo "rol".

    Si lo tuviera, cualquier persona podría registrarse eligiendo el rol de
    administrador y tendría control total de la aplicación. Es un fallo de
    seguridad clásico llamado ESCALADA DE PRIVILEGIOS. Por eso todos los
    usuarios que se registran por su cuenta reciben el rol de responsable de
    almacén, y solo un administrador puede cambiarlo después desde el panel de
    gestión de usuarios.
    """

    nombre = StringField(
        "Nombre y apellidos",
        validators=[
            DataRequired(message="El nombre es obligatorio."),
            Length(min=3, max=100, message="El nombre debe tener entre 3 y 100 caracteres."),
        ],
        render_kw={"placeholder": "Ana Ruiz Fernández"},
    )

    email = StringField(
        "Correo electrónico",
        validators=[
            DataRequired(message="El correo es obligatorio."),
            Email(message="El formato del correo no es válido."),
            Length(max=120),
        ],
        render_kw={"placeholder": "usuario@empresa.com"},
    )

    password = PasswordField(
        "Contraseña",
        validators=[
            DataRequired(message="La contraseña es obligatoria."),
            Length(min=8, message="La contraseña debe tener al menos 8 caracteres."),
            # Regexp comprueba el texto contra una expresión regular.
            # (?=.*[A-Za-z]) significa "en algún punto por delante hay una letra"
            # (?=.*\d)       significa "en algún punto por delante hay un dígito"
            # Son "lookaheads": miran sin consumir caracteres, así que exigimos
            # las dos condiciones a la vez sin importar el orden.
            Regexp(
                r"^(?=.*[A-Za-z])(?=.*\d).+$",
                message="La contraseña debe combinar al menos una letra y un número.",
            ),
        ],
    )

    password2 = PasswordField(
        "Repite la contraseña",
        validators=[
            DataRequired(message="Repite la contraseña."),
            # EqualTo compara este campo con otro por su nombre.
            EqualTo("password", message="Las dos contraseñas no coinciden."),
        ],
    )

    submit = SubmitField("Crear cuenta")

    # -- Validador personalizado -------------------------------------------
    #
    # WTForms busca automáticamente métodos llamados validate_<nombre_del_campo>
    # y los ejecuta como una validación más. No hace falta registrarlos: basta
    # con respetar el nombre.

    def validate_email(self, campo):
        """
        Comprueba que el correo no esté ya registrado.

        Esto es una validación de negocio: requiere consultar la base de datos,
        así que no puede expresarse con un validador estándar.

        La columna email ya es unique en la base de datos, que es la garantía
        definitiva. Pero si confiásemos solo en ella, el usuario recibiría un
        error 500 con un mensaje incomprensible de SQLAlchemy. Comprobándolo
        aquí obtiene un mensaje claro junto al campo.
        """
        usuario = Usuario.query.filter_by(email=campo.data.lower().strip()).first()
        if usuario is not None:
            # Lanzar ValidationError marca el campo como inválido y muestra
            # este mensaje debajo de él.
            raise ValidationError("Ya existe una cuenta con este correo electrónico.")
