"""
Instancias de las extensiones de Flask.

¿Por qué un fichero aparte? Para evitar las importaciones circulares.

El problema: los modelos (app/models/producto.py) necesitan el objeto `db`,
y la fábrica de la aplicación (app/__init__.py) necesita importar los modelos.
Si `db` viviera dentro de app/__init__.py tendríamos que importar app desde el
modelo y el modelo desde app: Python entraría en un bucle y fallaría.

La solución estándar es crear aquí las extensiones "vacías" (sin aplicación) y
enlazarlas después a la app con .init_app(app) dentro de la fábrica.
"""

from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

# El ORM: nos da db.Model (clase base de los modelos) y db.session (la sesión
# de trabajo con la base de datos: add, commit, rollback...).
db = SQLAlchemy()

# Gestor de sesiones de usuario.
login_manager = LoginManager()

# A qué endpoint redirigir cuando un usuario NO autenticado intenta entrar en
# una página protegida con @login_required. "auth.login" = blueprint.función.
login_manager.login_view = "auth.login"

# Mensaje que se muestra en ese caso (por defecto está en inglés).
login_manager.login_message = "Debes iniciar sesión para acceder a esta página."
login_manager.login_message_category = "warning"

# Protección CSRF para todos los formularios POST de la aplicación.
csrf = CSRFProtect()
