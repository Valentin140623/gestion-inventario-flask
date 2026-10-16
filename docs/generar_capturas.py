"""
Genera automáticamente las capturas de pantalla de la aplicación.

Hace todo el proceso de una vez, sin tocar tu base de datos real:
  1. Crea una base de datos temporal con un administrador y los datos de
     demostración (la misma carta que `flask cargar-demo`).
  2. Arranca la aplicación en segundo plano en http://127.0.0.1:5050.
  3. Entra con cada rol y guarda las capturas en docs/capturas/.
  4. Para el servidor y borra la base de datos temporal.

USO (desde la raíz del proyecto, con el entorno virtual activado):
    python docs/generar_capturas.py

Requiere Playwright:  pip install playwright  y después  playwright install chromium
"""

import os
import sys
import threading
import time

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DESTINO = os.path.join(RAIZ, "docs", "capturas")
BD_TEMPORAL = os.path.join(RAIZ, "instance", "capturas_temporal.db")

# La configuración lee DATABASE_URL al importarse, así que hay que fijarla
# ANTES de importar la aplicación.
os.environ["DATABASE_URL"] = "sqlite:///" + BD_TEMPORAL
sys.path.insert(0, RAIZ)

from playwright.sync_api import sync_playwright  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import RolUsuario, Usuario, Venta  # noqa: E402

PUERTO = 5050
BASE = f"http://127.0.0.1:{PUERTO}"

# Cuentas de los tres roles. El administrador lo crea este script; los otros
# dos son los usuarios de ejemplo de app/datos_demo.py.
ADMIN = ("Valentin Piano", "admin@labuenamesa.com", "Admin1234")
CUENTAS = {
    "admin": (ADMIN[1], ADMIN[2]),
    "almacen": ("sala@labuenamesa.com", "Sala12345"),
    "financiero": ("financiero@labuenamesa.com", "Finanzas1234"),
}

# (nombre del fichero, ruta, cuenta con la que entrar, página completa o no)
CAPTURAS = [
    ("01-login",                "/auth/login",                          None,         False),
    ("02-panel-admin",          "/",                                    "admin",      True),
    ("03-panel-almacen",        "/",                                    "almacen",    True),
    ("04-panel-financiero",     "/",                                    "financiero", True),
    ("05-gestion-usuarios",     "/admin/usuarios",                      "admin",      True),
    ("06-acceso-denegado",      "/admin/usuarios",                      "almacen",    False),
    ("07-listado-productos",    "/productos/",                          "admin",      True),
    ("08-productos-almacen",    "/productos/",                          "almacen",    True),
    ("09-ficha-producto",       "/productos/1",                         "admin",      True),
    ("10-nuevo-producto",       "/productos/nuevo",                     "admin",      True),
    ("11-filtro-stock-bajo",    "/productos/?alerta=stock_bajo",        "admin",      True),
    ("12-movimientos",          "/inventario/",                         "admin",      True),
    ("13-listado-ventas",       "/ventas/",                             "admin",      True),
    ("14-nueva-venta",          "/ventas/nueva",                        "admin",      False),
    ("15-detalle-venta",        "/ventas/1",                            "admin",      True),
    ("16-listado-proveedores",  "/proveedores/",                        "admin",      True),
    ("17-ficha-proveedor",      "/proveedores/1",                       "admin",      True),
    ("18-comparativa",          "/proveedores/comparativa?producto=1",  "admin",      True),
    ("19-compras",              "/compras/",                            "admin",      True),
    ("20-detalle-compra",       "/compras/1",                           "admin",      True),
    ("21-analisis",             "/analisis/",                           "admin",      True),
    ("22-analisis-mensual",     "/analisis/?agrupacion=mes",            "admin",      True),
    ("23-analisis-almacen",     "/analisis/",                           "almacen",    True),
]


def preparar_base_de_datos(app):
    """Crea la BD temporal con un administrador y los datos de demostración."""
    from app.datos_demo import cargar_datos_demo, cargar_proveedores_demo, cargar_ventas_demo

    if os.path.exists(BD_TEMPORAL):
        os.remove(BD_TEMPORAL)
    os.makedirs(os.path.dirname(BD_TEMPORAL), exist_ok=True)

    with app.app_context():
        db.create_all()

        admin = Usuario(nombre=ADMIN[0], email=ADMIN[1], rol=RolUsuario.ADMIN, activo=True)
        admin.set_password(ADMIN[2])
        db.session.add(admin)
        db.session.commit()

        cargar_datos_demo(admin)
        if Venta.query.count() == 0:
            usuarios = Usuario.query.filter(Usuario.rol != RolUsuario.FINANCIERO).all()
            cargar_ventas_demo(usuarios)
        cargar_proveedores_demo(admin)
        db.session.commit()


def iniciar_sesion(pagina, cuenta):
    """Entra en la aplicación con la cuenta indicada."""
    email, password = CUENTAS[cuenta]
    pagina.goto(f"{BASE}/auth/logout")
    pagina.goto(f"{BASE}/auth/login")
    pagina.fill("#email", email)
    pagina.fill("#password", password)
    pagina.click("#submit")
    pagina.wait_for_load_state("networkidle")


def tomar_capturas():
    os.makedirs(DESTINO, exist_ok=True)

    with sync_playwright() as p:
        # Usamos el Google Chrome instalado en el equipo; si no lo hay,
        # recurrimos al Chromium de Playwright (playwright install chromium).
        chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        try:
            if os.path.exists(chrome):
                navegador = p.chromium.launch(executable_path=chrome, headless=True)
            else:
                navegador = p.chromium.launch(channel="chrome")
        except Exception as error:
            print(f"No se pudo usar Google Chrome ({error}); probando con Chromium de Playwright.")
            navegador = p.chromium.launch()
        contexto = navegador.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1.5,
            locale="es-ES",
        )
        pagina = contexto.new_page()

        sesion_actual = "sin-sesion"
        for numero, (nombre, ruta, cuenta, completa) in enumerate(CAPTURAS, start=1):
            if cuenta != sesion_actual:
                if cuenta is None:
                    pagina.goto(f"{BASE}/auth/logout")
                else:
                    iniciar_sesion(pagina, cuenta)
                sesion_actual = cuenta

            pagina.goto(f"{BASE}{ruta}")
            pagina.wait_for_load_state("networkidle")
            time.sleep(0.4)  # deja terminar las animaciones de los avisos

            pagina.screenshot(path=os.path.join(DESTINO, f"{nombre}.png"), full_page=completa)
            print(f"  [{numero:>2}/{len(CAPTURAS)}] {nombre}.png")

        navegador.close()


def main():
    app = create_app()
    print("Preparando base de datos temporal con datos de demostración...")
    preparar_base_de_datos(app)

    servidor = make_server("127.0.0.1", PUERTO, app, threaded=True)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    print(f"Aplicación arrancada en {BASE}")

    try:
        tomar_capturas()
    finally:
        servidor.shutdown()
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
        try:
            os.remove(BD_TEMPORAL)
        except OSError:
            pass

    print(f"\nListo: {len(CAPTURAS)} capturas guardadas en docs/capturas/")


if __name__ == "__main__":
    main()
