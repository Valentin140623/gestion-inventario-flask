"""
Rutas del apartado de análisis (requisito 5).
"""

from datetime import datetime, timedelta

from flask import Blueprint, render_template, request

from ..services.analisis import (
    evolucion_ventas,
    productos_bajo_margen,
    productos_en_riesgo,
    productos_mas_rentables,
    productos_mas_vendidos,
    productos_menor_rotacion,
    resumen_periodo,
    valor_inventario,
    ventas_por_categoria,
)
from ..utils import permiso_requerido

bp = Blueprint("analisis", __name__, url_prefix="/analisis")


def _leer_rango():
    """
    Lee el rango de fechas de la URL, o usa los últimos 90 días por defecto.

    Devuelve (desde, hasta, texto_desde, texto_hasta) para poder repintar el
    formulario con lo que el usuario había elegido.
    """
    texto_desde = request.args.get("desde", "")
    texto_hasta = request.args.get("hasta", "")

    if texto_desde:
        desde = datetime.strptime(texto_desde, "%Y-%m-%d")
    else:
        desde = datetime.now() - timedelta(days=90)

    if texto_hasta:
        # Hasta el final del día indicado.
        hasta = datetime.strptime(texto_hasta, "%Y-%m-%d") + timedelta(days=1)
    else:
        hasta = datetime.now()

    return desde, hasta, texto_desde or desde.strftime("%Y-%m-%d"), texto_hasta or hasta.strftime("%Y-%m-%d")


def _puntos_grafica(serie, clave, ancho=760, alto=180):
    """
    Convierte una serie de valores en coordenadas para dibujar un SVG.

    Lo calculamos en Python y no en la plantilla porque es aritmética, no
    presentación. La plantilla solo recibe la cadena de puntos ya lista.

    El eje Y va invertido: en SVG el 0 está arriba, así que restamos.
    """
    if not serie:
        return "", 0

    valores = [f[clave] for f in serie]
    maximo = max(valores) or 1

    # Si solo hay un punto, lo colocamos en el centro para que se vea.
    if len(serie) == 1:
        return f"{ancho / 2},{alto - (valores[0] / maximo) * alto}", maximo

    paso = ancho / (len(serie) - 1)
    puntos = []
    for indice, valor in enumerate(valores):
        x = indice * paso
        y = alto - (valor / maximo) * alto
        puntos.append(f"{x:.1f},{y:.1f}")

    return " ".join(puntos), maximo


@bp.route("/")
@permiso_requerido("analisis.ver")
def panel():
    """Panel de análisis con todos los indicadores del requisito 5."""
    desde, hasta, texto_desde, texto_hasta = _leer_rango()
    agrupacion = request.args.get("agrupacion", "semana")

    resumen = resumen_periodo(desde, hasta)
    evolucion = evolucion_ventas(desde, hasta, agrupacion)
    categorias = ventas_por_categoria(desde, hasta)

    # Coordenadas de las dos líneas de la gráfica de evolución.
    puntos_facturado, maximo = _puntos_grafica(evolucion, "facturado")
    puntos_beneficio, _ = _puntos_grafica(evolucion, "beneficio")
    # La línea de beneficio se dibuja a la misma escala que la de facturación
    # para que la comparación sea visual y honesta: usamos el mismo máximo.
    if evolucion and maximo:
        puntos_beneficio = " ".join(
            f"{i * (760 / max(1, len(evolucion) - 1)):.1f},{180 - (f['beneficio'] / maximo) * 180:.1f}"
            for i, f in enumerate(evolucion)
        )

    return render_template(
        "analisis/panel.html",
        titulo="Análisis",
        resumen=resumen,
        evolucion=evolucion,
        puntos_facturado=puntos_facturado,
        puntos_beneficio=puntos_beneficio,
        maximo_grafica=maximo,
        categorias=categorias,
        mas_vendidos=productos_mas_vendidos(desde, hasta, 8),
        mas_rentables=productos_mas_rentables(desde, hasta, 8),
        menor_rotacion=productos_menor_rotacion(desde, hasta, 8),
        bajo_margen=productos_bajo_margen(),
        en_riesgo=productos_en_riesgo(desde, hasta),
        valor_stock=valor_inventario(),
        filtros={"desde": texto_desde, "hasta": texto_hasta, "agrupacion": agrupacion},
    )
