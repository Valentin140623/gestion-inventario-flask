"""
Análisis y métricas de negocio.

Reúne los cálculos que pide el enunciado:

  Del requisito 3 (lógica de negocio):
    - Detectar productos con bajo margen de beneficio.
    - Detectar riesgo de ruptura de stock.
    - Calcular la rotación de productos.
    - Estimar los días restantes hasta agotarse según el ritmo de ventas.

  Del requisito 5 (análisis y métricas):
    - Productos más vendidos.
    - Productos más rentables.
    - Productos con menor rotación.
    - Beneficio total en un rango de fechas.
    - Evolución de ventas por periodo y por categoría.

Todas las funciones devuelven datos ya calculados (números y listas), nunca
HTML: así los mismos resultados sirven para la web, para el PDF y para las
exportaciones.
"""

from datetime import datetime, timedelta

from flask import current_app
from sqlalchemy import func

from ..extensions import db
from ..models import Categoria, LineaVenta, Producto, Venta


# ---------------------------------------------------------------------------
# Utilidades de fechas
# ---------------------------------------------------------------------------


def rango_por_defecto(dias=None):
    """Devuelve (desde, hasta) para los últimos N días."""
    if dias is None:
        dias = current_app.config["VENTANA_ANALISIS_DIAS"]
    hasta = datetime.now()
    desde = hasta - timedelta(days=dias)
    return desde, hasta


# ---------------------------------------------------------------------------
# Métricas por producto (requisito 3)
# ---------------------------------------------------------------------------


def unidades_vendidas(producto, desde, hasta):
    """Unidades de un producto vendidas entre dos fechas."""
    total = (
        db.session.query(func.sum(LineaVenta.cantidad))
        .join(Venta)
        .filter(
            LineaVenta.producto_id == producto.id,
            Venta.fecha >= desde,
            Venta.fecha <= hasta,
        )
        .scalar()
    )
    # scalar() devuelve None si no hay ninguna fila; lo convertimos a 0.
    return total or 0


def velocidad_venta(producto, desde=None, hasta=None):
    """
    Media de unidades vendidas al día.

    Es la base de las dos métricas siguientes: si vendemos 2 unidades al día
    y quedan 10 en almacén, se agotarán en 5 días.
    """
    if desde is None or hasta is None:
        desde, hasta = rango_por_defecto()

    dias = max(1, (hasta - desde).days)
    return unidades_vendidas(producto, desde, hasta) / dias


def dias_hasta_agotarse(producto, desde=None, hasta=None):
    """
    Días que tardará en agotarse el stock al ritmo de venta actual.

    Devuelve None si el producto no se vende (no se agotará nunca por ventas)
    y 0 si ya está sin stock.
    """
    if producto.stock_actual == 0:
        return 0

    velocidad = velocidad_venta(producto, desde, hasta)
    if velocidad <= 0:
        return None

    return producto.stock_actual / velocidad


def rotacion(producto, desde=None, hasta=None):
    """
    Índice de rotación: cuántas veces se ha renovado el stock en el periodo.

    Fórmula: unidades vendidas / stock actual

    Un valor alto significa que el producto se mueve mucho respecto a lo que
    tenemos almacenado. Un valor cercano a cero es un producto parado, que
    ocupa sitio y tiene dinero inmovilizado: justo el problema 2 que describe
    el enunciado ("acumulación de productos con baja rotación").

    Usamos el stock actual como referencia por simplicidad. Lo más exacto sería
    el stock medio del periodo, pero para tomar decisiones de compra el stock
    actual es más útil, porque es el que hay que gestionar hoy.
    """
    if desde is None or hasta is None:
        desde, hasta = rango_por_defecto()

    vendidas = unidades_vendidas(producto, desde, hasta)
    if producto.stock_actual == 0:
        # Sin stock: si se vendió algo, la rotación es total.
        return float(vendidas) if vendidas else 0.0

    return vendidas / producto.stock_actual


def riesgo_rotura(producto, desde=None, hasta=None):
    """
    Evalúa el riesgo de quedarse sin stock.

    Devuelve uno de: "sin_stock", "critico", "bajo", "correcto".
    """
    if producto.stock_actual == 0:
        return "sin_stock"

    dias = dias_hasta_agotarse(producto, desde, hasta)
    umbral = current_app.config["DIAS_RIESGO_ROTURA"]

    if dias is not None and dias <= umbral:
        return "critico"
    if producto.necesita_reposicion:
        return "bajo"
    return "correcto"


# ---------------------------------------------------------------------------
# Alertas (requisito 3 y ampliación 6)
# ---------------------------------------------------------------------------


def productos_bajo_margen():
    """Productos activos cuyo margen está por debajo del umbral configurado."""
    umbral = current_app.config["UMBRAL_MARGEN_BAJO"]

    # El margen es una propiedad de Python, no una columna, así que este filtro
    # no puede hacerlo la base de datos. Traemos solo los productos activos y
    # filtramos en memoria; con un catálogo de este tamaño es inmediato.
    productos = Producto.query.filter_by(activo=True).all()
    bajos = [p for p in productos if p.margen_porcentual < umbral]
    bajos.sort(key=lambda p: p.margen_porcentual)
    return bajos


def productos_en_riesgo(desde=None, hasta=None):
    """
    Productos con riesgo de rotura de stock, ordenados por urgencia.

    Devuelve una lista de diccionarios con el producto, su nivel de riesgo y
    los días que le quedan.
    """
    if desde is None or hasta is None:
        desde, hasta = rango_por_defecto()

    resultado = []
    for producto in Producto.query.filter_by(activo=True).all():
        nivel = riesgo_rotura(producto, desde, hasta)
        if nivel == "correcto":
            continue

        resultado.append({
            "producto": producto,
            "nivel": nivel,
            "dias_restantes": dias_hasta_agotarse(producto, desde, hasta),
            "velocidad": velocidad_venta(producto, desde, hasta),
        })

    # Ordenamos por urgencia: primero los que no tienen stock, después los que
    # menos días aguantan. Usamos -1 para que los sin stock queden arriba y un
    # número muy grande para los que no se agotan nunca.
    def clave(fila):
        if fila["nivel"] == "sin_stock":
            return -1
        return fila["dias_restantes"] if fila["dias_restantes"] is not None else 99999

    resultado.sort(key=clave)
    return resultado


# ---------------------------------------------------------------------------
# Rankings (requisito 5)
# ---------------------------------------------------------------------------


def productos_mas_vendidos(desde, hasta, limite=10):
    """
    Productos con más unidades vendidas en el periodo.

    La consulta agrupa y suma en la base de datos (GROUP BY + SUM) en lugar de
    recorrer las ventas en Python: es mucho más rápido y es la forma correcta
    de resolverlo en SQL.
    """
    filas = (
        db.session.query(
            Producto,
            func.sum(LineaVenta.cantidad).label("unidades"),
            func.sum(LineaVenta.cantidad * LineaVenta.precio_unitario).label("facturado"),
        )
        .join(LineaVenta, LineaVenta.producto_id == Producto.id)
        .join(Venta, Venta.id == LineaVenta.venta_id)
        .filter(Venta.fecha >= desde, Venta.fecha <= hasta)
        .group_by(Producto.id)
        .order_by(func.sum(LineaVenta.cantidad).desc())
        .limit(limite)
        .all()
    )

    return [
        {"producto": p, "unidades": int(u), "facturado": float(f)}
        for p, u, f in filas
    ]


def productos_mas_rentables(desde, hasta, limite=10):
    """
    Productos que más beneficio han generado en el periodo.

    Ojo con la diferencia: el más vendido no siempre es el más rentable. Un
    producto barato puede venderse mucho y aportar poco beneficio, mientras
    que uno caro con pocas ventas aporta más. Por eso el enunciado pide las
    dos listas por separado.
    """
    beneficio = func.sum(
        (LineaVenta.precio_unitario - LineaVenta.coste_unitario) * LineaVenta.cantidad
    )

    filas = (
        db.session.query(
            Producto,
            beneficio.label("beneficio"),
            func.sum(LineaVenta.cantidad).label("unidades"),
        )
        .join(LineaVenta, LineaVenta.producto_id == Producto.id)
        .join(Venta, Venta.id == LineaVenta.venta_id)
        .filter(Venta.fecha >= desde, Venta.fecha <= hasta)
        .group_by(Producto.id)
        .order_by(beneficio.desc())
        .limit(limite)
        .all()
    )

    return [
        {"producto": p, "beneficio": float(b), "unidades": int(u)}
        for p, b, u in filas
    ]


def productos_menor_rotacion(desde, hasta, limite=10):
    """
    Productos con menor rotación: los que más tiempo llevan parados.

    Incluye los que no se han vendido nada, que son los casos más graves de
    inmovilizado.
    """
    resultado = []
    for producto in Producto.query.filter_by(activo=True).all():
        if producto.stock_actual == 0:
            continue  # sin stock no hay inmovilizado que analizar

        vendidas = unidades_vendidas(producto, desde, hasta)
        resultado.append({
            "producto": producto,
            "unidades": vendidas,
            "rotacion": vendidas / producto.stock_actual,
            "inmovilizado": producto.valor_stock,
        })

    # Menor rotación primero; a igual rotación, primero el que más dinero tiene
    # inmovilizado, que es el más urgente de liquidar.
    resultado.sort(key=lambda f: (f["rotacion"], -f["inmovilizado"]))
    return resultado[:limite]


# ---------------------------------------------------------------------------
# Resultados económicos (requisito 5)
# ---------------------------------------------------------------------------


def resumen_periodo(desde, hasta):
    """
    Cifras globales del periodo: facturación, coste, beneficio y margen.

    Es el "beneficio total en un rango de fechas" que pide el enunciado.
    """
    fila = (
        db.session.query(
            func.sum(LineaVenta.cantidad * LineaVenta.precio_unitario),
            func.sum(LineaVenta.cantidad * LineaVenta.coste_unitario),
            func.sum(LineaVenta.cantidad),
            func.count(func.distinct(Venta.id)),
        )
        .join(Venta, Venta.id == LineaVenta.venta_id)
        .filter(Venta.fecha >= desde, Venta.fecha <= hasta)
        .first()
    )

    facturado = float(fila[0] or 0)
    coste = float(fila[1] or 0)
    unidades = int(fila[2] or 0)
    num_ventas = int(fila[3] or 0)
    beneficio = facturado - coste

    return {
        "facturado": facturado,
        "coste": coste,
        "beneficio": beneficio,
        "margen": (beneficio / facturado * 100) if facturado else 0,
        "unidades": unidades,
        "num_ventas": num_ventas,
        "ticket_medio": (facturado / num_ventas) if num_ventas else 0,
    }


def evolucion_ventas(desde, hasta, agrupacion="dia"):
    """
    Serie temporal de ventas para dibujar la gráfica de evolución.

    agrupacion: "dia", "semana" o "mes".

    strftime de SQLite permite agrupar por el formato de fecha que queramos:
      %Y-%m-%d -> día      %Y-%W -> semana del año      %Y-%m -> mes
    """
    formatos = {"dia": "%Y-%m-%d", "semana": "%Y-%W", "mes": "%Y-%m"}
    formato = formatos.get(agrupacion, "%Y-%m-%d")

    periodo = func.strftime(formato, Venta.fecha)

    filas = (
        db.session.query(
            periodo.label("periodo"),
            func.sum(LineaVenta.cantidad * LineaVenta.precio_unitario),
            func.sum(
                (LineaVenta.precio_unitario - LineaVenta.coste_unitario) * LineaVenta.cantidad
            ),
        )
        .join(LineaVenta, LineaVenta.venta_id == Venta.id)
        .filter(Venta.fecha >= desde, Venta.fecha <= hasta)
        .group_by(periodo)
        .order_by(periodo)
        .all()
    )

    return [
        {"periodo": p, "facturado": float(f or 0), "beneficio": float(b or 0)}
        for p, f, b in filas
    ]


def ventas_por_categoria(desde, hasta):
    """Reparto de las ventas entre las categorías de producto."""
    filas = (
        db.session.query(
            Categoria.nombre,
            func.sum(LineaVenta.cantidad * LineaVenta.precio_unitario),
            func.sum(
                (LineaVenta.precio_unitario - LineaVenta.coste_unitario) * LineaVenta.cantidad
            ),
            func.sum(LineaVenta.cantidad),
        )
        .join(Producto, Producto.categoria_id == Categoria.id)
        .join(LineaVenta, LineaVenta.producto_id == Producto.id)
        .join(Venta, Venta.id == LineaVenta.venta_id)
        .filter(Venta.fecha >= desde, Venta.fecha <= hasta)
        .group_by(Categoria.id)
        .order_by(func.sum(LineaVenta.cantidad * LineaVenta.precio_unitario).desc())
        .all()
    )

    return [
        {"categoria": c, "facturado": float(f or 0), "beneficio": float(b or 0), "unidades": int(u or 0)}
        for c, f, b, u in filas
    ]


def valor_inventario():
    """Dinero inmovilizado en almacén, valorado a precio de coste."""
    total = (
        db.session.query(func.sum(Producto.stock_actual * Producto.coste_adquisicion))
        .filter(Producto.activo.is_(True))
        .scalar()
    )
    return float(total or 0)
