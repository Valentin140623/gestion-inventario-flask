"""
Punto de entrada de la aplicación.

Se ejecuta con:  python run.py
"""

from app import create_app

# Creamos la aplicación llamando a la fábrica.
app = create_app()


if __name__ == "__main__":
    # debug=True activa el recargado automático al guardar un fichero y la
    # página de errores detallada. NUNCA debe usarse en producción.
    app.run(debug=True, host="127.0.0.1", port=5000)
