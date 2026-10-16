"""
Servicio de ventas: registrar y anular ventas.
"""

from datetime import datetime

from ..extensions import db
from ..models import Compra, LineaCompra, LineaVenta, TipoMovimiento, Venta
from .inventario import ErrorInventario, entrada_stock, salida_stock


def generar_numero(modelo, prefijo):
    """
    Genera el siguiente número de documento: V-2026-0001, C-2026-0007...

    Cuenta los documentos del año en curso y suma uno.
    """
    anio = datetime.now().year
    patron = f"{prefijo}-{anio}-%"
    contador = modelo.query.filter(modelo.numero.like(patron)).count()
    return f"{prefijo}-{anio}-{contador + 1:04d}"


def crear_venta(usuario, lineas, cliente=None, observaciones=None):
    """
    Registra una venta completa.

    lineas: lista de diccionarios {"producto": Producto, "cantidad": int}

    Descuenta el stock de cada producto y guarda el precio y el coste del
    momento, para que el beneficio histórico no cambie si mañana cambian las
    tarifas.

    Lanza ErrorInventario si algún producto no tiene stock suficiente.
    """
    if not lineas:
        raise ErrorInventario("La venta debe incluir al menos un producto.")

    venta = Venta(
        numero=generar_numero(Venta, "V"),
        fecha=datetime.now(),
        cliente=cliente,
        usuario=usuario,
        observaciones=observaciones,
    )
    db.session.add(venta)

    for item in lineas:
        producto = item["producto"]
        cantidad = item["cantidad"]

        if cantidad <= 0:
            raise ErrorInventario(f"La cantidad de «{producto.nombre}» debe ser mayor que cero.")

        # Copiamos precio y coste actuales: son datos históricos.
        db.session.add(
            LineaVenta(
                venta=venta,
                producto=producto,
                cantidad=cantidad,
                precio_unitario=producto.precio_venta,
                coste_unitario=producto.coste_adquisicion,
            )
        )

        # Descuenta el stock y anota el movimiento. Si no hay suficiente,
        # lanza ErrorInventario y la vista hará rollback de todo.
        salida_stock(producto, cantidad, usuario, motivo="Venta", documento=venta.numero)

    return venta


def anular_venta(venta, usuario):
    """
    Anula una venta: devuelve el stock al almacén y la borra.

    Se registra una entrada por cada línea, de modo que el historial refleja
    la devolución en lugar de hacer desaparecer el movimiento original.
    """
    for linea in venta.lineas:
        entrada_stock(
            linea.producto,
            linea.cantidad,
            usuario,
            motivo=f"Anulación de la venta {venta.numero}",
            documento=venta.numero,
        )

    db.session.delete(venta)


def crear_compra(usuario, proveedor, lineas, observaciones=None, fecha_recepcion=None):
    """
    Registra una compra a un proveedor y da entrada al stock.

    lineas: lista de {"producto": Producto, "cantidad": int, "precio": float}
    """
    if not lineas:
        raise ErrorInventario("La compra debe incluir al menos un producto.")

    compra = Compra(
        numero=generar_numero(Compra, "C"),
        fecha=datetime.now(),
        proveedor=proveedor,
        usuario=usuario,
        observaciones=observaciones,
        fecha_recepcion=fecha_recepcion,
    )
    db.session.add(compra)

    for item in lineas:
        producto = item["producto"]
        cantidad = item["cantidad"]
        precio = item["precio"]

        if cantidad <= 0:
            raise ErrorInventario(f"La cantidad de «{producto.nombre}» debe ser mayor que cero.")

        # La línea de compra siempre se guarda en la unidad en la que se
        # COMPRA el producto: "cantidad" barriles a "precio" euros el
        # barril. Es lo que aparecería en la factura del proveedor.
        db.session.add(
            LineaCompra(
                compra=compra,
                producto=producto,
                cantidad=cantidad,
                precio_unitario=precio,
            )
        )

        if producto.se_vende_por_racion:
            # -----------------------------------------------------------
            # Producto que se compra en envase grande y se vende por
            # raciones (un barril de cerveza que se sirve por cañas).
            #
            # "cantidad" y "precio" que ha tecleado el usuario están en la
            # unidad de COMPRA (barriles), pero el stock y el coste del
            # producto se guardan siempre en la unidad de VENTA (cañas):
            # así el resto de la aplicación no necesita saber nada de
            # barriles. Por eso hay que convertir aquí, y solo aquí.
            # -----------------------------------------------------------
            raciones_por_envase = producto.raciones_por_envase
            if not raciones_por_envase:
                raise ErrorInventario(
                    f"«{producto.nombre}» está marcado como venta por ración, pero le "
                    f"faltan datos (contenido del envase o tamaño de la ración). "
                    f"Complétalos en la ficha del producto antes de comprarlo."
                )

            unidades_stock = round(cantidad * raciones_por_envase)
            coste_por_racion = precio / raciones_por_envase

            entrada_stock(
                producto, unidades_stock, usuario,
                motivo=(
                    f"Compra a {proveedor.nombre}: {cantidad} envase(s) "
                    f"de {producto.nombre_racion} × {raciones_por_envase:.0f} raciones"
                ),
                documento=compra.numero,
            )
            producto.coste_adquisicion = coste_por_racion

        else:
            # Producto normal: la unidad de compra es la misma que la de venta.
            entrada_stock(
                producto, cantidad, usuario,
                motivo=f"Compra a {proveedor.nombre}", documento=compra.numero,
            )
            # Actualizamos el coste de referencia con el último precio pagado,
            # para que los márgenes reflejen la realidad actual.
            producto.coste_adquisicion = precio

    return compra
