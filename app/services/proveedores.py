"""
Métricas de proveedores.

Responde a la parte del requisito 4 que pide "métricas que permitan analizar
qué proveedor resulta más rentable o eficiente".
"""

from ..models import Compra, ProductoProveedor


def metricas_proveedor(proveedor):
    """
    Calcula los indicadores de un proveedor.

    Devuelve un diccionario con:
      - num_productos      : referencias que nos suministra
      - num_compras        : pedidos realizados
      - total_comprado     : importe acumulado
      - plazo_medio_real   : días que tarda de verdad en servir
      - puntualidad        : % de pedidos servidos dentro del plazo prometido
      - margen_medio       : margen medio de los productos que nos vende
    """
    compras = proveedor.compras.all()
    recibidas = [c for c in compras if c.fecha_recepcion]

    total_comprado = sum(c.total for c in compras)

    # Plazo medio real de entrega.
    plazo_medio = None
    if recibidas:
        plazo_medio = sum(c.dias_entrega_real for c in recibidas) / len(recibidas)

    # Puntualidad: pedidos servidos dentro del plazo comprometido.
    puntualidad = None
    if recibidas:
        a_tiempo = sum(1 for c in recibidas if c.dias_entrega_real <= proveedor.plazo_entrega_dias)
        puntualidad = a_tiempo / len(recibidas) * 100

    # Margen medio que obtenemos con sus productos.
    asociaciones = proveedor.productos_asociados.all()
    margen_medio = None
    if asociaciones:
        margenes = [a.margen_resultante for a in asociaciones]
        margen_medio = sum(margenes) / len(margenes)

    return {
        "num_productos": len(asociaciones),
        "num_compras": len(compras),
        "total_comprado": total_comprado,
        "plazo_medio_real": plazo_medio,
        "puntualidad": puntualidad,
        "margen_medio": margen_medio,
    }


def comparar_proveedores_de(producto):
    """
    Compara todos los proveedores que suministran un producto.

    Devuelve la lista de asociaciones ordenada de más barato a más caro, con
    el sobrecoste de cada uno respecto al mejor precio. Es la herramienta que
    pide el enunciado para "comparar precios y condiciones entre proveedores".
    """
    asociaciones = producto.proveedores_asociados.all()
    if not asociaciones:
        return []

    asociaciones.sort(key=lambda a: a.precio_coste)
    mejor_precio = asociaciones[0].precio_coste

    comparativa = []
    for asociacion in asociaciones:
        diferencia = asociacion.precio_coste - mejor_precio
        comparativa.append({
            "asociacion": asociacion,
            "proveedor": asociacion.proveedor,
            # "precio" es siempre lo que cobra el proveedor por la unidad que
            # se COMPRA: el envase completo si el producto se vende por
            # ración, o la unidad normal en el resto de casos.
            "precio": asociacion.precio_coste,
            # "coste_unidad" es lo que cuesta de verdad cada unidad que se
            # VENDE (cada caña, cada copa). Coincide con "precio" salvo en
            # los productos por ración, donde hay que dividir entre las
            # raciones que salen del envase.
            "coste_unidad": asociacion.coste_por_unidad_vendida,
            "diferencia": diferencia,
            "porcentaje_extra": (diferencia / mejor_precio * 100) if mejor_precio else 0,
            "es_mejor_precio": diferencia == 0,
            "margen": asociacion.margen_resultante,
        })
    return comparativa


def ranking_proveedores():
    """Todos los proveedores con sus métricas, ordenados por importe comprado."""
    from ..models import Proveedor

    resultado = []
    for proveedor in Proveedor.query.filter_by(activo=True).all():
        datos = metricas_proveedor(proveedor)
        datos["proveedor"] = proveedor
        resultado.append(datos)

    resultado.sort(key=lambda d: d["total_comprado"], reverse=True)
    return resultado
