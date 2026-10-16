"""
Comandos de consola personalizados.

Flask permite añadir subcomandos propios a su herramienta de línea de órdenes.
Se ejecutan así:

    flask init-db
    flask crear-admin

¿Por qué comandos y no un script suelto?
Porque Flask los ejecuta dentro del CONTEXTO DE APLICACIÓN: la configuración
está cargada y la conexión a la base de datos disponible, sin tener que
montarlo a mano en cada script. Además quedan documentados y se listan solos
con "flask --help", lo que facilita el manual de instalación del proyecto.
"""

import click
from flask.cli import with_appcontext

from .extensions import db
from .models import RolUsuario, Usuario


@click.command("init-db")
@with_appcontext
def init_db():
    """Crea las tablas de la base de datos si no existen."""
    # create_all() solo crea las tablas que faltan: no borra ni modifica las
    # existentes, así que es seguro ejecutarlo varias veces.
    db.create_all()
    click.echo("Base de datos inicializada correctamente.")


@click.command("crear-admin")
# @click.option define parámetros del comando. prompt=True hace que, si no se
# indican al llamar, Click los pregunte de forma interactiva.
@click.option("--nombre", prompt="Nombre y apellidos")
@click.option("--email", prompt="Correo electrónico")
# hide_input oculta lo que se escribe; confirmation_prompt la pide dos veces.
@click.option("--password", prompt="Contraseña", hide_input=True, confirmation_prompt=True)
@with_appcontext
def crear_admin(nombre, email, password):
    """
    Crea un usuario administrador.

    Es imprescindible: el formulario de registro web solo crea usuarios con rol
    de almacén (para impedir la escalada de privilegios), así que el primer
    administrador tiene que crearse desde fuera de la aplicación. Es el mismo
    planteamiento que usan Django o WordPress en su instalación inicial.
    """
    email = email.lower().strip()

    if Usuario.query.filter_by(email=email).first():
        # err=True escribe en la salida de error, y devolvemos sin crear nada.
        click.echo(f"Ya existe un usuario con el correo {email}.", err=True)
        return

    admin = Usuario(nombre=nombre.strip(), email=email, rol=RolUsuario.ADMIN, activo=True)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()

    click.echo(f"Administrador '{nombre}' creado correctamente ({email}).")


@click.command("cargar-demo")
@with_appcontext
def cargar_demo():
    """Carga categorías, productos y usuarios de ejemplo para probar la aplicación."""
    from .datos_demo import cargar_datos_demo

    # Los movimientos de inventario necesitan un usuario responsable. Usamos el
    # primer administrador que exista: si no hay ninguno, no tiene sentido
    # continuar, porque la aplicación aún no está inicializada.
    admin = Usuario.query.filter_by(rol=RolUsuario.ADMIN).first()
    if not admin:
        click.echo("No hay ningún administrador. Ejecuta antes: flask crear-admin", err=True)
        return

    resumen = cargar_datos_demo(admin)
    click.echo(
        f"Datos de demostración cargados: "
        f"{resumen['categorias']} categorías, "
        f"{resumen['productos']} productos, "
        f"{resumen['usuarios']} usuarios."
    )

    # Ventas históricas: solo si no hay ninguna, para no duplicarlas.
    from .models import Venta

    if Venta.query.count() == 0:
        from .datos_demo import cargar_ventas_demo

        usuarios = Usuario.query.filter(Usuario.rol != RolUsuario.FINANCIERO).all()
        creadas = cargar_ventas_demo(usuarios)
        click.echo(f"Generadas {creadas} ventas de los últimos 4 meses.")
    else:
        click.echo("Ya existen ventas registradas: no se generan más.")

    # Proveedores, asociaciones y compras.
    from .datos_demo import cargar_proveedores_demo

    prov = cargar_proveedores_demo(admin)
    click.echo(
        f"Proveedores: {prov['proveedores']} creados, "
        f"{prov['asociaciones']} asociaciones producto-proveedor, "
        f"{prov['compras']} compras."
    )


def registrar_comandos(app):
    """Registra los comandos en la aplicación. Se llama desde create_app()."""
    app.cli.add_command(init_db)
    app.cli.add_command(crear_admin)
    app.cli.add_command(cargar_demo)
