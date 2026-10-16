"""
Definición del menú de navegación.

En lugar de escribir el menú directamente en el HTML, lo describimos aquí como
una lista de diccionarios. Ventajas:

  1. El menú se filtra AUTOMÁTICAMENTE según los permisos del usuario: cada
     entrada declara qué permiso necesita, y la plantilla solo pinta las que
     el usuario puede usar. Así el responsable financiero ni siquiera ve el
     enlace de "Movimientos de inventario".
  2. Es un único sitio que consultar para saber qué secciones tiene la
     aplicación.
  3. Mientras construimos el proyecto, las secciones todavía no creadas se
     ocultan solas (ver la comprobación de endpoints más abajo), en vez de
     provocar un error al generar la URL.

OJO, MATIZ DE SEGURIDAD: ocultar un enlace del menú NO es control de acceso.
Un usuario podría escribir la URL a mano en el navegador. La seguridad real la
imponen los decoradores @permiso_requerido de cada vista; esto es solo una
mejora de experiencia de usuario, para no enseñar puertas que están cerradas.
"""

from flask import current_app

# Cada entrada del menú:
#   endpoint : nombre de la vista Flask a la que enlaza ("blueprint.función")
#   etiqueta : texto visible
#   icono    : emoji usado como icono (evita depender de librerías externas
#              y de que haya conexión a internet)
#   permiso  : permiso necesario para verla; None significa "todos"
MENU = [
    {"endpoint": "main.dashboard",       "etiqueta": "Panel de control", "icono": "📊", "permiso": None},
    {"endpoint": "productos.listar",     "etiqueta": "Productos",        "icono": "📦", "permiso": "productos.ver"},
    {"endpoint": "inventario.listar",    "etiqueta": "Inventario",       "icono": "🔄", "permiso": "inventario.ver"},
    {"endpoint": "ventas.listar",        "etiqueta": "Ventas",           "icono": "🧾", "permiso": "ventas.ver"},
    {"endpoint": "compras.listar",       "etiqueta": "Compras",          "icono": "🚚", "permiso": "compras.ver"},
    {"endpoint": "proveedores.listar",   "etiqueta": "Proveedores",      "icono": "🏭", "permiso": "proveedores.ver"},
    {"endpoint": "analisis.panel",       "etiqueta": "Análisis",         "icono": "📈", "permiso": "analisis.ver"},
    {"endpoint": "admin.listar_usuarios","etiqueta": "Usuarios",         "icono": "👥", "permiso": "usuarios.gestionar"},
]


def construir_menu(usuario):
    """
    Devuelve las entradas del menú visibles para este usuario.

    Aplica dos filtros:
      1. Que la vista exista ya. current_app.view_functions es el diccionario
         de todos los endpoints registrados en la aplicación. Comprobarlo evita
         que url_for() lance un error por una sección aún no implementada.
      2. Que el usuario tenga el permiso declarado en la entrada.
    """
    if not usuario or not usuario.is_authenticated:
        return []

    visibles = []
    for entrada in MENU:
        if entrada["endpoint"] not in current_app.view_functions:
            continue  # sección todavía no construida
        if entrada["permiso"] and not usuario.tiene_permiso(entrada["permiso"]):
            continue  # el usuario no tiene acceso: no le mostramos el enlace
        visibles.append(entrada)
    return visibles
