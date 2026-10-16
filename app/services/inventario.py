"""
Servicio de inventario: la única puerta de entrada para modificar el stock.

--- ¿Por qué una capa de servicios? ---------------------------------------

Podríamos cambiar el stock directamente desde cada vista:

    producto.stock_actual -= 3          # ¡MAL!

El problema es que ese código estaría repetido en la vista de ventas, en la de
compras, en la de ajustes... y cada copia tendría que acordarse además de
crear el movimiento en el historial y de comprobar que el stock no queda
negativo. En cuanto una sola de esas copias se olvide de algo, el stock y el
historial dejan de cuadrar y el requisito 3 queda incumplido.

Con esta capa, TODO cambio de stock pasa por una única función que:
  1. Comprueba que la operación es válida.
  2. Actualiza el stock del producto.
  3. Anota el movimiento en el historial.

Las tres cosas juntas, siempre. Es imposible hacer una y olvidar otra.

--- Sobre el commit --------------------------------------------------------

Estas funciones NO hacen db.session.commit(). Es deliberado.

Una venta de tres productos distintos son tres movimientos de stock más la
venta en sí: o se guardan las cuatro cosas, o no se guarda ninguna. Si cada
función confirmase por su cuenta y fallara la tercera, quedaría media venta
grabada en la base de datos, con el stock ya descontado de dos productos.

Dejando el commit en manos de quien llama, todo el conjunto forma una única
TRANSACCIÓN: si algo falla, un rollback lo deshace entero.
"""

from ..extensions import db
from ..models import MovimientoInventario, TipoMovimiento


class ErrorInventario(Exception):
    """
    Error de negocio del inventario (por ejemplo, stock insuficiente).

    Creamos una excepción propia, en vez de usar ValueError, para poder
    distinguir en las vistas un problema previsto de negocio (que se muestra al
    usuario como un aviso) de un fallo inesperado del programa (que debe
    provocar un error 500 y quedar registrado).
    """


def registrar_movimiento(producto, tipo, cantidad, usuario, motivo=None, documento=None):
    """
    Aplica un movimiento de stock y lo anota en el historial.

    Parámetros:
        producto  : objeto Producto afectado
        tipo      : miembro de TipoMovimiento (ENTRADA, SALIDA o AJUSTE)
        cantidad  : entero CON SIGNO. Positivo suma stock, negativo lo resta.
        usuario   : objeto Usuario que realiza la operación (trazabilidad)
        motivo    : texto explicativo
        documento : número del documento que lo origina ("V-2026-0001")

    Devuelve el MovimientoInventario creado.
    Lanza ErrorInventario si la operación dejaría el stock en negativo.

    Recuerda: NO hace commit. Quien llama debe confirmarlo.
    """

    if cantidad == 0:
        raise ErrorInventario("La cantidad de un movimiento no puede ser cero.")

    # Si el producto es nuevo y aún no se ha guardado, stock_actual puede ser
    # None (el default de la columna no se aplica hasta el INSERT). "or 0"
    # cubre ese caso.
    stock_previo = producto.stock_actual or 0
    stock_nuevo = stock_previo + cantidad

    # ------------------------------------------------------------------
    # REGLA DE NEGOCIO: el stock nunca puede ser negativo.
    #
    # Es una imposibilidad física: no se pueden tener -3 botellas en una
    # estantería. Si lo permitiéramos, todas las métricas basadas en stock
    # (valor de inventario, días hasta agotarse, rotación) darían resultados
    # sin sentido.
    #
    # La comprobación va aquí, en el servicio, y no en cada formulario: así
    # protege también a las ventas, las compras y cualquier código futuro.
    # ------------------------------------------------------------------
    if stock_nuevo < 0:
        raise ErrorInventario(
            f"Stock insuficiente de «{producto.nombre}». "
            f"Disponible: {stock_previo} unidades, se intentan retirar {abs(cantidad)}."
        )

    # 1. Actualizamos el stock del producto.
    producto.stock_actual = stock_nuevo

    # 2. Anotamos el movimiento en el historial.
    movimiento = MovimientoInventario(
        producto=producto,
        tipo=tipo,
        cantidad=cantidad,
        stock_resultante=stock_nuevo,
        motivo=motivo,
        documento_referencia=documento,
        usuario=usuario,
    )
    db.session.add(movimiento)

    return movimiento


# ---------------------------------------------------------------------------
# Funciones de conveniencia
#
# Envuelven a registrar_movimiento para los tres casos habituales. Hacen el
# código de las vistas mucho más legible:
#
#     entrada_stock(producto, 10, usuario, "Compra a proveedor")
#
# se entiende de un vistazo, mientras que:
#
#     registrar_movimiento(producto, TipoMovimiento.ENTRADA, 10, usuario, "...")
#
# obliga a fijarse en el tipo y en el signo. Además evitan el error de pasar
# una cantidad positiva en una salida (o al revés), porque el signo lo pone la
# función, no quien la llama.
# ---------------------------------------------------------------------------


def entrada_stock(producto, unidades, usuario, motivo=None, documento=None):
    """Registra una entrada de mercancía. unidades debe ser positivo."""
    if unidades <= 0:
        raise ErrorInventario("Las unidades de una entrada deben ser mayores que cero.")
    return registrar_movimiento(
        producto, TipoMovimiento.ENTRADA, abs(unidades), usuario, motivo, documento
    )


def salida_stock(producto, unidades, usuario, motivo=None, documento=None):
    """Registra una salida de mercancía. unidades debe ser positivo."""
    if unidades <= 0:
        raise ErrorInventario("Las unidades de una salida deben ser mayores que cero.")
    # El signo negativo lo aplicamos aquí: quien llama solo indica cuántas
    # unidades salen, en positivo.
    return registrar_movimiento(
        producto, TipoMovimiento.SALIDA, -abs(unidades), usuario, motivo, documento
    )


def ajustar_stock(producto, stock_real, usuario, motivo=None):
    """
    Ajusta el stock al valor contado en un inventario físico.

    Quien llama indica cuántas unidades hay REALMENTE en la estantería, y la
    función calcula sola la diferencia. Es más natural que pedirle al usuario
    que calcule "me sobran 3" o "me faltan 2", y evita errores de signo.

    Devuelve None si no hay diferencia: no tiene sentido anotar en el historial
    un movimiento de cero unidades.
    """
    if stock_real < 0:
        raise ErrorInventario("El stock real no puede ser negativo.")

    diferencia = stock_real - (producto.stock_actual or 0)
    if diferencia == 0:
        return None

    return registrar_movimiento(
        producto,
        TipoMovimiento.AJUSTE,
        diferencia,
        usuario,
        motivo or "Ajuste por inventario físico",
    )
