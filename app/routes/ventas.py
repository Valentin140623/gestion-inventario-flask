"""
Rutas de ventas: listado, registro, detalle y anulación.
"""

from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..extensions import db
from ..models import Producto, Venta
from ..services import ErrorInventario, anular_venta, crear_venta
from ..utils import permiso_requerido

bp = Blueprint("ventas", __name__, url_prefix="/ventas")

POR_PAGINA = 15


@bp.route("/")
@permiso_requerido("ventas.ver")
def listar():
    """Listado de ventas con filtro por fechas y por cliente."""
    desde = request.args.get("desde", "", type=str)
    hasta = request.args.get("hasta", "", type=str)
    cliente = request.args.get("cliente", "", type=str).strip()
    pagina = request.args.get("pagina", 1, type=int)

    consulta = Venta.query

    if desde:
        consulta = consulta.filter(Venta.fecha >= datetime.strptime(desde, "%Y-%m-%d"))
    if hasta:
        # Sumamos un día para incluir las ventas de la propia fecha "hasta",
        # que llevan hora distinta de 00:00.
        fin = datetime.strptime(hasta, "%Y-%m-%d") + timedelta(days=1)
        consulta = consulta.filter(Venta.fecha < fin)
    if cliente:
        consulta = consulta.filter(Venta.cliente.ilike(f"%{cliente}%"))

    paginacion = consulta.order_by(Venta.fecha.desc()).paginate(
        page=pagina, per_page=POR_PAGINA, error_out=False
    )

    # Totales del conjunto filtrado (no solo de la página actual).
    ventas_filtradas = consulta.all()
    total_facturado = sum(v.total for v in ventas_filtradas)
    total_beneficio = sum(v.beneficio for v in ventas_filtradas)

    return render_template(
        "ventas/listar.html",
        titulo="Ventas",
        paginacion=paginacion,
        ventas=paginacion.items,
        total_facturado=total_facturado,
        total_beneficio=total_beneficio,
        filtros={"desde": desde, "hasta": hasta, "cliente": cliente},
    )


@bp.route("/nueva", methods=["GET", "POST"])
@permiso_requerido("ventas.registrar")
def crear():
    """
    Registro de una venta.

    Las líneas llegan como listas paralelas desde el formulario:
    producto_id[] y cantidad[]. getlist() devuelve todos los valores enviados
    con ese nombre, y zip() los empareja fila a fila.
    """
    productos = (
        Producto.query.filter(Producto.activo.is_(True), Producto.stock_actual > 0)
        .order_by(Producto.nombre)
        .all()
    )

    if request.method == "POST":
        cliente = request.form.get("cliente", "").strip()
        observaciones = request.form.get("observaciones", "").strip()

        ids = request.form.getlist("producto_id")
        cantidades = request.form.getlist("cantidad")

        lineas = []
        for producto_id, cantidad in zip(ids, cantidades):
            # Las filas vacías (el usuario añadió una y no la rellenó) se ignoran.
            if not producto_id or not cantidad:
                continue
            producto = db.session.get(Producto, int(producto_id))
            if producto:
                lineas.append({"producto": producto, "cantidad": int(cantidad)})

        try:
            venta = crear_venta(current_user, lineas, cliente or None, observaciones or None)
            db.session.commit()
            flash(f"Venta {venta.numero} registrada por {venta.total:.2f} €.", "success")
            return redirect(url_for("ventas.detalle", venta_id=venta.id))

        except ErrorInventario as e:
            # Deshacemos todo: la venta, las líneas y los descuentos de stock
            # que hubieran llegado a aplicarse antes del fallo.
            db.session.rollback()
            flash(str(e), "danger")

    return render_template(
        "ventas/formulario.html",
        titulo="Nueva venta",
        productos=productos,
    )


@bp.route("/<int:venta_id>")
@permiso_requerido("ventas.ver")
def detalle(venta_id):
    """Detalle de una venta."""
    venta = db.get_or_404(Venta, venta_id)
    return render_template("ventas/detalle.html", titulo=f"Venta {venta.numero}", venta=venta)


@bp.route("/<int:venta_id>/anular", methods=["POST"])
@permiso_requerido("ventas.registrar")
def anular(venta_id):
    """Anula una venta y devuelve el stock."""
    venta = db.get_or_404(Venta, venta_id)
    numero = venta.numero

    anular_venta(venta, current_user)
    db.session.commit()

    flash(f"Venta {numero} anulada. El stock se ha devuelto al almacén.", "info")
    return redirect(url_for("ventas.listar"))
