"""
Rutas de autenticación: registro, inicio y cierre de sesión.

--- ¿Qué es un Blueprint? -------------------------------------------------

Un blueprint es un grupo de rutas relacionadas que se registra en la
aplicación como un bloque. En vez de tener las cincuenta rutas del proyecto
apiladas en un solo fichero gigante, cada área funcional (auth, productos,
ventas...) vive en su propio módulo.

Ventajas:
  - El código queda organizado por funcionalidad.
  - Se les puede poner un prefijo común de URL (aquí, /auth).
  - Los endpoints quedan con nombre propio: url_for("auth.login") es
    inequívoco aunque exista otra vista llamada "login" en otro blueprint.
"""

from datetime import datetime
from urllib.parse import urlparse

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..forms import FormularioLogin, FormularioRegistro
from ..models import RolUsuario, Usuario

# Creamos el blueprint. url_prefix hace que todas las rutas de este fichero
# cuelguen de /auth: la ruta "/login" será en realidad "/auth/login".
bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/login", methods=["GET", "POST"])
def login():
    """
    Inicio de sesión.

    methods=["GET", "POST"] porque esta misma URL hace dos cosas:
      - GET  : el navegador pide la página y le mostramos el formulario vacío.
      - POST : el usuario envía el formulario y comprobamos las credenciales.
    """

    # Si ya hay sesión abierta no tiene sentido mostrar el login otra vez.
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    formulario = FormularioLogin()

    # validate_on_submit() devuelve True solo si (a) la petición es POST y
    # (b) todos los validadores han pasado, incluido el token CSRF.
    # Es la forma idiomática de escribir "si han enviado el formulario y es
    # correcto" en una sola condición.
    if formulario.validate_on_submit():

        # Normalizamos el correo: en minúsculas y sin espacios sobrantes.
        # Así "Ana@Empresa.com " y "ana@empresa.com" son el mismo usuario.
        email = formulario.email.data.lower().strip()
        usuario = Usuario.query.filter_by(email=email).first()

        # ------------------------------------------------------------------
        # DECISIÓN DE SEGURIDAD: un único mensaje de error para los dos fallos.
        #
        # Sería más "amable" decir "ese correo no existe" o "la contraseña es
        # incorrecta" según el caso. Sería también un fallo de seguridad: un
        # atacante podría probar miles de correos y averiguar cuáles están
        # registrados en la empresa (se llama enumeración de usuarios), y
        # centrar después el ataque solo en esos.
        #
        # Comprobamos las dos cosas juntas y respondemos siempre lo mismo.
        # ------------------------------------------------------------------
        if usuario is None or not usuario.check_password(formulario.password.data):
            flash("Correo electrónico o contraseña incorrectos.", "danger")
            return redirect(url_for("auth.login"))

        # Usuario dado de baja: aquí sí conviene un mensaje específico, porque
        # sus credenciales son correctas y necesita saber a qué atenerse.
        if not usuario.activo:
            flash(
                "Tu cuenta está desactivada. Contacta con un administrador.",
                "warning",
            )
            return redirect(url_for("auth.login"))

        # login_user() guarda el id del usuario en la cookie de sesión (firmada
        # con SECRET_KEY, para que nadie pueda falsificarla). A partir de aquí,
        # current_user apunta a este usuario en todas las peticiones.
        login_user(usuario, remember=formulario.recordarme.data)

        # Dejamos constancia del acceso: útil para auditoría.
        usuario.ultimo_acceso = datetime.now()
        db.session.commit()

        # ------------------------------------------------------------------
        # Parámetro "next": cuando un usuario sin sesión intenta abrir una
        # página protegida, Flask-Login lo manda al login añadiendo a la URL
        # ?next=/la/pagina/que/queria. Al terminar el login lo devolvemos allí.
        #
        # PERO hay que validarlo. Si aceptásemos cualquier valor, un atacante
        # podría enviar un enlace con ?next=https://web-falsa.com y llevarse al
        # usuario a una web fraudulenta justo después de iniciar sesión, con
        # toda la apariencia de legitimidad. Es la vulnerabilidad conocida como
        # "open redirect".
        #
        # urlparse(...).netloc devuelve el dominio de una URL. Si está vacío,
        # la ruta es relativa (interna a nuestra aplicación) y es segura.
        # ------------------------------------------------------------------
        destino = request.args.get("next")
        if not destino or urlparse(destino).netloc != "":
            destino = url_for("main.dashboard")

        flash(f"Bienvenido/a, {usuario.nombre}.", "success")
        return redirect(destino)

    # Si es GET, o si la validación ha fallado, mostramos el formulario.
    # En el segundo caso llega ya con los mensajes de error incorporados.
    return render_template("auth/login.html", formulario=formulario, titulo="Iniciar sesión")


@bp.route("/registro", methods=["GET", "POST"])
def registro():
    """Alta de un nuevo usuario."""

    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    formulario = FormularioRegistro()

    if formulario.validate_on_submit():
        usuario = Usuario(
            nombre=formulario.nombre.data.strip(),
            email=formulario.email.data.lower().strip(),
            # El rol NO se lee del formulario (no existe ese campo): se asigna
            # aquí, en el servidor. Ver la explicación en FormularioRegistro.
            rol=RolUsuario.ALMACEN,
            activo=True,
        )
        # Nunca asignamos la contraseña directamente: pasa por set_password,
        # que es quien la cifra.
        usuario.set_password(formulario.password.data)

        # add() prepara la inserción; commit() la confirma de verdad en la BD.
        # Hasta el commit, todo vive solo en memoria y podría deshacerse.
        db.session.add(usuario)
        db.session.commit()

        flash("Cuenta creada correctamente. Ya puedes iniciar sesión.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/registro.html", formulario=formulario, titulo="Crear cuenta")


@bp.route("/logout")
@login_required  # No tiene sentido cerrar la sesión de quien no la ha abierto.
def logout():
    """Cierre de sesión."""
    # logout_user() borra el id del usuario de la cookie de sesión.
    logout_user()
    flash("Has cerrado la sesión correctamente.", "info")
    return redirect(url_for("auth.login"))
