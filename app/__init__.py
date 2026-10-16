"""
Fábrica de la aplicación (application factory).

En lugar de crear el objeto Flask como una variable global, lo creamos dentro
de una función. Ventajas:
  - Podemos crear varias instancias con configuraciones distintas (por ejemplo
    una para desarrollo y otra para tests) sin duplicar código.
  - Evitamos importaciones circulares: los blueprints se importan DENTRO de la
    función, cuando las extensiones ya existen.
"""

from flask import Flask, render_template
from flask_login import current_user

from .config import Config
from .extensions import csrf, db, login_manager


def create_app(config_class=Config):
    """Crea y configura la instancia de la aplicación Flask."""

    # __name__ le dice a Flask dónde está el paquete, para localizar las
    # carpetas templates/ y static/ automáticamente.
    app = Flask(__name__)

    # Cargamos toda la configuración desde la clase Config.
    app.config.from_object(config_class)

    # Enlazamos las extensiones con esta aplicación concreta.
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Importamos los modelos DENTRO de la función, después de init_app.
    # Este import parece no hacer nada (no usamos el nombre "models"), pero es
    # imprescindible: al importarse, cada clase se registra en los metadatos de
    # SQLAlchemy. Sin él, db.create_all() no encontraría ninguna tabla que crear.
    from . import models  # noqa: F401

    registrar_blueprints(app)
    registrar_manejadores_error(app)
    registrar_context_processors(app)
    registrar_filtros_plantilla(app)

    # Comandos de consola (flask init-db, flask crear-admin...).
    from .cli import registrar_comandos

    registrar_comandos(app)

    return app


def registrar_blueprints(app):
    """
    Registra todos los blueprints de la aplicación.

    Se importan aquí dentro, y no arriba del fichero, porque los blueprints
    importan modelos y formularios que a su vez importan las extensiones: si lo
    hiciéramos en la cabecera del módulo, Python entraría en un ciclo de
    importaciones.
    """
    from .routes import (
        admin,
        analisis,
        auth,
        compras,
        informes,
        inventario,
        main,
        productos,
        proveedores,
        ventas,
    )

    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(productos.bp)
    app.register_blueprint(ventas.bp)
    app.register_blueprint(proveedores.bp)
    app.register_blueprint(inventario.bp)
    app.register_blueprint(compras.bp)
    app.register_blueprint(analisis.bp)
    app.register_blueprint(informes.bp)
    app.register_blueprint(admin.bp)


def registrar_manejadores_error(app):
    """
    Páginas de error personalizadas.

    Sin esto, Flask muestra páginas blancas con texto en inglés. Con errorhandler
    devolvemos una página con el diseño de la aplicación y un mensaje en español.

    Cada manejador devuelve una TUPLA (html, código). Si devolviéramos solo el
    html, Flask respondería con un 200 "todo correcto", y tanto los navegadores
    como los buscadores interpretarían que la página existe.
    """

    @app.errorhandler(403)
    def prohibido(error):
        return (
            render_template(
                "errores/error.html",
                codigo=403,
                titulo_error="Acceso denegado",
                mensaje="Tu rol no tiene permiso para acceder a esta sección. "
                        "Si crees que es un error, contacta con un administrador.",
                titulo="Acceso denegado",
            ),
            403,
        )

    @app.errorhandler(404)
    def no_encontrado(error):
        return (
            render_template(
                "errores/error.html",
                codigo=404,
                titulo_error="Página no encontrada",
                mensaje="La dirección que has solicitado no existe o el elemento "
                        "ha sido eliminado.",
                titulo="No encontrado",
            ),
            404,
        )

    @app.errorhandler(500)
    def error_interno(error):
        # Si se ha producido un error a mitad de una operación con la base de
        # datos, la sesión queda en un estado inconsistente. rollback() deshace
        # los cambios pendientes para que las siguientes peticiones funcionen.
        db.session.rollback()
        return (
            render_template(
                "errores/error.html",
                codigo=500,
                titulo_error="Error interno",
                mensaje="Se ha producido un error inesperado. La operación no se "
                        "ha completado.",
                titulo="Error",
            ),
            500,
        )


def registrar_context_processors(app):
    """
    Variables disponibles automáticamente en TODAS las plantillas.

    Un context processor es una función que devuelve un diccionario; sus claves
    se inyectan en el contexto de cada render_template. Así no hay que pasar el
    menú desde cada una de las vistas del proyecto.
    """
    from .utils.navegacion import construir_menu

    @app.context_processor
    def inyectar_menu():
        return {"menu_navegacion": construir_menu(current_user)}


def registrar_filtros_plantilla(app):
    """
    Filtros propios de Jinja2.

    En una plantilla se usan con el carácter |, encadenándolos al valor:
        {{ producto.precio_venta|euros }}     ->  1.200,00 €

    Centralizar aquí el formato garantiza que todos los importes de la
    aplicación se muestren igual, y que si mañana cambia el criterio se toque
    un solo sitio.
    """

    @app.template_filter("euros")
    def formato_euros(valor):
        """Formatea un número como importe en euros, al estilo español."""
        if valor is None:
            return "—"
        # Explicación del truco de formato:
        #   f"{valor:,.2f}" da el estilo inglés: 1,200.00
        #   Necesitamos el español:               1.200,00
        # Intercambiamos los separadores en tres pasos, usando "X" como marca
        # temporal para no pisar un carácter con el otro a medio camino.
        texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{texto} €"

    @app.template_filter("porcentaje")
    def formato_porcentaje(valor, decimales=1):
        """Formatea un número como porcentaje."""
        if valor is None:
            return "—"
        return f"{valor:.{decimales}f} %".replace(".", ",")

    @app.template_filter("fecha")
    def formato_fecha(valor, con_hora=False):
        """Formatea una fecha al estilo español (dd/mm/aaaa)."""
        if valor is None:
            return "—"
        return valor.strftime("%d/%m/%Y %H:%M" if con_hora else "%d/%m/%Y")
