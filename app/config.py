"""
Configuración de la aplicación.

Centralizamos aquí todos los parámetros configurables para no tenerlos
esparcidos por el código. Flask lee esta clase con app.config.from_object().
"""

import os

# Ruta absoluta a la carpeta raíz del proyecto (dos niveles por encima de este
# fichero: app/config.py -> app/ -> raíz). Usamos rutas absolutas para que la
# aplicación funcione igual sin importar desde qué carpeta se ejecute.
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Config:
    """Configuración base de la aplicación."""

    # Nombre del negocio. Se usa en la cabecera, el título de las páginas y
    # el informe en PDF. Cambiar aquí basta para renombrar toda la aplicación.
    NOMBRE_APP = os.environ.get("NOMBRE_APP", "La Buena Mesa")

    # Clave secreta: Flask la usa para firmar la cookie de sesión y los tokens
    # CSRF de los formularios. En producción debe venir de una variable de
    # entorno; el valor por defecto es solo para desarrollo.
    SECRET_KEY = os.environ.get("SECRET_KEY", "clave-de-desarrollo-cambiar-en-produccion")

    # Cadena de conexión a la base de datos. "sqlite:///" + ruta absoluta al
    # fichero. El fichero se creará solo la primera vez que inicialicemos la BD.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "instance", "suministros.db"),
    )

    # Desactivamos el sistema de eventos de SQLAlchemy: consume memoria y no
    # lo usamos. Si no lo ponemos, Flask-SQLAlchemy muestra un aviso al arrancar.
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Parámetros de negocio -------------------------------------------
    # Los sacamos a configuración para poder ajustar los umbrales sin tocar
    # la lógica. Son los valores que usan las alertas y los indicadores.

    # Un producto se considera de "bajo margen" si su margen porcentual está
    # por debajo de este umbral (en %).
    UMBRAL_MARGEN_BAJO = 15.0

    # Un producto está en "riesgo de rotura de stock" si se prevé que se agote
    # en menos de estos días según su ritmo medio de ventas.
    DIAS_RIESGO_ROTURA = 15

    # Número de días hacia atrás que analizamos para calcular el ritmo medio
    # de ventas (velocidad de venta diaria) y la rotación.
    VENTANA_ANALISIS_DIAS = 90


class ConfigPruebas(Config):
    """
    Configuración usada al ejecutar las pruebas automáticas.

    Hereda de Config y solo cambia lo necesario (herencia de clases: otro uso
    práctico de la POO en el proyecto).
    """

    TESTING = True

    # Base de datos en memoria: se crea al empezar la prueba y desaparece al
    # terminar. Cada prueba parte de una base de datos limpia y nunca se toca
    # la de verdad.
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

    # Desactivamos la protección CSRF SOLO en las pruebas.
    #
    # No es un agujero de seguridad: en producción sigue activa. El motivo es
    # que un cliente de pruebas no carga la página HTML previa, así que no
    # dispone del token que el formulario incluiría. Sin esta línea, todas las
    # peticiones POST de las pruebas serían rechazadas con un error 400... que
    # es justo lo que debe pasarle a un atacante.
    WTF_CSRF_ENABLED = False
