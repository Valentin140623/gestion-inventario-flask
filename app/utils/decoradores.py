"""
Decoradores de control de acceso.

Implementan la parte del requisito 1 que dice: "Cada rol tendrá acceso
únicamente a las funcionalidades que le correspondan. Se debe implementar
control de accesos y restricciones en función del tipo de usuario."

--- ¿Qué es un decorador? -------------------------------------------------

Un decorador es una función que recibe otra función y devuelve una función
nueva que la envuelve. Escribir esto:

    @permiso_requerido("productos.editar")
    def crear_producto():
        ...

es exactamente lo mismo que escribir:

    def crear_producto():
        ...
    crear_producto = permiso_requerido("productos.editar")(crear_producto)

Es decir: la vista original queda "envuelta" por otra función que se ejecuta
ANTES y decide si deja pasar o no.

--- ¿Por qué usarlos aquí? ------------------------------------------------

La alternativa sería repetir en cada una de las decenas de vistas:

    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    if not current_user.tiene_permiso("productos.editar"):
        abort(403)

Con el decorador, esa comprobación se escribe UNA vez y se aplica con una
línea. Si mañana hay que cambiar cómo se deniega el acceso (por ejemplo,
registrar el intento en un log de seguridad), se toca un único sitio.
Y lo más importante: es imposible olvidarse de proteger media vista, porque la
protección está declarada arriba, a la vista de cualquiera que lea el código.
"""

from functools import wraps

from flask import abort
from flask_login import current_user, login_required


def permiso_requerido(permiso):
    """
    Exige que el usuario tenga un permiso concreto para acceder a la vista.

    Uso:
        @bp.route("/productos/nuevo")
        @permiso_requerido("productos.editar")
        def nuevo_producto():
            ...

    Fíjate en que hay TRES funciones anidadas. Es necesario porque el decorador
    recibe un argumento (el nombre del permiso):

      1. permiso_requerido(permiso)  -> recibe el permiso y devuelve...
      2. decorador(f)                -> recibe la vista y devuelve...
      3. funcion_envuelta(...)       -> lo que se ejecuta de verdad en cada petición.

    A este patrón se le llama "fábrica de decoradores".
    """

    def decorador(f):
        # @wraps(f) copia el nombre, la documentación y los metadatos de la
        # función original a la función que la envuelve. Sin esto, TODAS las
        # vistas de la aplicación pasarían a llamarse "funcion_envuelta" y
        # Flask, que identifica los endpoints por el nombre de la función,
        # lanzaría un error al detectar nombres duplicados.
        @wraps(f)
        # @login_required se ejecuta primero: si no hay nadie autenticado,
        # redirige al login antes siquiera de mirar los permisos. Así nunca
        # devolvemos un 403 (prohibido) a quien simplemente no ha entrado
        # todavía, que debe recibir una redirección al formulario de acceso.
        @login_required
        def funcion_envuelta(*args, **kwargs):
            # Llegados aquí sabemos que hay un usuario autenticado.
            if not current_user.tiene_permiso(permiso):
                # abort(403) corta la ejecución y devuelve el error HTTP 403
                # "Forbidden": estás identificado, pero esto no es para ti.
                abort(403)
            # *args y **kwargs reenvían a la vista original los parámetros que
            # venían de la URL (por ejemplo el id en /productos/7/editar).
            return f(*args, **kwargs)

        return funcion_envuelta

    return decorador


def rol_requerido(*roles):
    """
    Exige que el usuario tenga uno de los roles indicados.

    Uso:
        @rol_requerido(RolUsuario.ADMIN)
        def panel_admin():
            ...

    En general es preferible usar permiso_requerido: comprobar permisos es más
    flexible que comprobar roles, porque permite cambiar qué puede hacer cada
    rol sin tocar ni una sola vista. Dejamos este decorador para los casos en
    los que una pantalla entera pertenece a un rol concreto por definición.

    *roles recoge todos los argumentos posicionales en una tupla, de modo que
    se puede escribir rol_requerido(ADMIN) o rol_requerido(ADMIN, FINANCIERO).
    """

    def decorador(f):
        @wraps(f)
        @login_required
        def funcion_envuelta(*args, **kwargs):
            if current_user.rol not in roles:
                abort(403)
            return f(*args, **kwargs)

        return funcion_envuelta

    return decorador
