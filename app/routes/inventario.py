"""
Rutas de inventario: historial de movimientos y registro manual de
entradas, salidas y ajustes.
"""

from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..extensions import db
from ..models import MovimientoInventario, Producto, TipoMovimiento
from ..services import ErrorInventario, ajustar_stock, entrada_stock, salida_stock
from ..utils import permiso_requerido

bp = Blueprint("inventario", __name__, url_prefix="/inventario")

POR_PAGINA = 25


@bp.route("/")
@permiso_requerido("inventario.ver")
def listar():
    """Historial completo de movimientos, con filtros."""
    producto_id = request.args.get("producto", 0, type=int)
    tipo = request.args.get("tipo", "", type=str)
    desde = request.args.get("desde", "", type=str)
    hasta = request.args.get("hasta", "", type=str)
    pagina = request.args.get("pagina", 1, type=int)

    consulta = MovimientoInventario.query

    if producto_id:
        consulta = consulta.filter(MovimientoInventario.producto_id == producto_id)
    if tipo:
        consulta = consulta.filter(MovimientoInventario.tipo == TipoMovimiento[tipo])
    if desde:
        consulta = consulta.filter(
            MovimientoInventario.fecha >= datetime.strptime(desde, "%Y-%m-%d")
        )
    if hasta:
        fin = datetime.strptime(hasta, "%Y-%m-%d") + timedelta(days=1)
        consulta = consulta.filter(MovimientoInventario.fecha < fin)

    paginacion = consulta.order_by(MovimientoInventario.fecha.desc()).paginate(
        page=pagina, per_page=POR_PAGINA, error_out=False
    )

    return render_template(
        "inventario/listar.html",
        titulo="Movimientos de inventario",
        paginacion=paginacion,
        movimientos=paginacion.items,
        productos=Producto.query.order_by(Producto.nombre).all(),
        filtros={"producto": producto_id, "tipo": tipo, "desde": desde, "hasta": hasta},
    )


@bp.route("/movimiento", methods=["GET", "POST"])
@permiso_requerido("inventario.editar")
def nuevo_movimiento():
    """
    Registro manual de un movimiento de stock.

    Cubre los casos que no vienen de una venta o una compra: roturas,
    devoluciones y ajustes tras un inventario físico.
    """
    productos = Producto.query.filter_by(activo=True).order_by(Producto.nombre).all()

    if request.method == "POST":
        producto_id = request.form.get("producto_id", type=int)
        operacion = request.form.get("operacion", "")
        cantidad = request.form.get("cantidad", type=int)
        motivo = request.form.get("motivo", "").strip()

        producto = db.session.get(Producto, producto_id) if producto_id else None

        if not producto:
            flash("Selecciona un producto.", "danger")
        elif cantidad is None:
            flash("Indica una cantidad.", "danger")
        else:
            try:
                if operacion == "entrada":
                    entrada_stock(producto, cantidad, current_user, motivo or "Entrada manual")
                elif operacion == "salida":
                    salida_stock(producto, cantidad, current_user, motivo or "Salida manual")
                elif operacion == "ajuste":
                    # En el ajuste, "cantidad" es el stock real contado.
                    resultado = ajustar_stock(producto, cantidad, current_user, motivo)
                    if resultado is None:
                        flash("El stock contado coincide con el registrado: no hay nada que ajustar.", "info")
                        return redirect(url_for("inventario.listar"))
                else:
                    flash("Operación no válida.", "danger")
                    return redirect(url_for("inventario.nuevo_movimiento"))

                db.session.commit()
                flash(
                    f"Movimiento registrado. «{producto.nombre}» tiene ahora "
                    f"{producto.stock_actual} unidades.",
                    "success",
                )
                return redirect(url_for("inventario.listar", producto=producto.id))

            except ErrorInventario as e:
                db.session.rollback()
                flash(str(e), "danger")

    return render_template(
        "inventario/movimiento.html",
        titulo="Nuevo movimiento de inventario",
        productos=productos,
    )
