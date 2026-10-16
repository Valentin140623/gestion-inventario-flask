"""
Rutas principales: panel de inicio.
"""

from datetime import datetime, timedelta

from flask import Blueprint, render_template
from flask_login import current_user, login_required

from ..models import Producto, Proveedor, Venta
from ..services.analisis import (
    productos_bajo_margen,
    productos_en_riesgo,
    productos_mas_vendidos,
    resumen_periodo,
    valor_inventario,
)

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def dashboard():
    """
    Panel de inicio: resumen de la actividad al entrar en la aplicación.

    Muestra las cifras del último mes y las alertas que requieren atención,
    adaptado a lo que puede ver el rol del usuario.
    """
    hasta = datetime.now()
    desde = hasta - timedelta(days=30)

    resumen = resumen_periodo(desde, hasta)
    en_riesgo = productos_en_riesgo(desde, hasta)

    # Las alertas de margen solo tienen sentido para quien puede ver datos
    # financieros: al resto ni se las calculamos.
    bajo_margen = productos_bajo_margen() if current_user.tiene_permiso("analisis.financiero") else []

    return render_template(
        "dashboard.html",
        titulo="Panel de control",
        usuario=current_user,
        resumen=resumen,
        en_riesgo=en_riesgo,
        bajo_margen=bajo_margen,
        mas_vendidos=productos_mas_vendidos(desde, hasta, 5),
        ultimas_ventas=Venta.query.order_by(Venta.fecha.desc()).limit(5).all(),
        valor_stock=valor_inventario(),
        total_productos=Producto.query.filter_by(activo=True).count(),
        total_proveedores=Proveedor.query.filter_by(activo=True).count(),
        desde=desde,
        hasta=hasta,
    )
