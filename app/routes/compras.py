"""
Rutas de compras a proveedores.
"""

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..extensions import db
from ..models import Compra, Producto, ProductoProveedor, Proveedor
from ..services import ErrorInventario, crear_compra
from ..utils import permiso_requerido

bp = Blueprint("compras", __name__, url_prefix="/compras")

POR_PAGINA = 15


@bp.route("/")
@permiso_requerido("compras.ver")
def listar():
    """Listado de compras."""
    proveedor_id = request.args.get("proveedor", 0, type=int)
    pagina = request.args.get("pagina", 1, type=int)

    consulta = Compra.query
    if proveedor_id:
        consulta = consulta.filter(Compra.proveedor_id == proveedor_id)

    paginacion = consulta.order_by(Compra.fecha.desc()).paginate(
        page=pagina, per_page=POR_PAGINA, error_out=False
    )

    total_comprado = sum(c.total for c in consulta.all())

    return render_template(
        "compras/listar.html",
        titulo="Compras",
        paginacion=paginacion,
        compras=paginacion.items,
        proveedores=Proveedor.query.order_by(Proveedor.nombre).all(),
        total_comprado=total_comprado,
        filtros={"proveedor": proveedor_id},
    )


@bp.route("/<int:compra_id>")
@permiso_requerido("compras.ver")
def detalle(compra_id):
    """Detalle de una compra."""
    compra = db.get_or_404(Compra, compra_id)
    return render_template("compras/detalle.html", titulo=f"Compra {compra.numero}", compra=compra)


@bp.route("/nueva", methods=["GET", "POST"])
@permiso_requerido("compras.registrar")
def crear():
    """
    Registro de un pedido a un proveedor.

    Al guardar, la mercancía entra en el almacén y se actualiza el coste de
    referencia de cada producto con el precio pagado.
    """
    proveedores = Proveedor.query.filter_by(activo=True).order_by(Proveedor.nombre).all()

    if request.method == "POST":
        proveedor_id = request.form.get("proveedor_id", type=int)
        observaciones = request.form.get("observaciones", "").strip()
        recibido = request.form.get("recibido") == "si"

        proveedor = db.session.get(Proveedor, proveedor_id) if proveedor_id else None

        if not proveedor:
            flash("Selecciona un proveedor.", "danger")
            return redirect(url_for("compras.crear"))

        ids = request.form.getlist("producto_id")
        cantidades = request.form.getlist("cantidad")
        precios = request.form.getlist("precio")

        lineas = []
        for producto_id, cantidad, precio in zip(ids, cantidades, precios):
            if not producto_id or not cantidad or not precio:
                continue
            producto = db.session.get(Producto, int(producto_id))
            if producto:
                lineas.append({
                    "producto": producto,
                    "cantidad": int(cantidad),
                    "precio": float(precio),
                })

        try:
            compra = crear_compra(
                current_user, proveedor, lineas,
                observaciones or None,
                # Si la mercancía ya ha llegado, anotamos la recepción ahora.
                fecha_recepcion=datetime.now() if recibido else None,
            )
            db.session.commit()
            flash(f"Compra {compra.numero} registrada por {compra.total:.2f} €.", "success")
            return redirect(url_for("compras.detalle", compra_id=compra.id))

        except ErrorInventario as e:
            db.session.rollback()
            flash(str(e), "danger")

    # Precios que cada proveedor tiene para cada producto: lo usa el
    # JavaScript para rellenar el precio automáticamente al elegir producto.
    tarifas = {}
    for asociacion in ProductoProveedor.query.all():
        tarifas.setdefault(asociacion.proveedor_id, {})[asociacion.producto_id] = asociacion.precio_coste

    return render_template(
        "compras/formulario.html",
        titulo="Nueva compra",
        proveedores=proveedores,
        productos=Producto.query.filter_by(activo=True).order_by(Producto.nombre).all(),
        tarifas=tarifas,
    )


@bp.route("/<int:compra_id>/recibir", methods=["POST"])
@permiso_requerido("compras.registrar")
def recibir(compra_id):
    """Marca una compra como recibida, lo que fija su plazo de entrega real."""
    compra = db.get_or_404(Compra, compra_id)

    if compra.fecha_recepcion:
        flash("Esta compra ya estaba marcada como recibida.", "info")
    else:
        compra.fecha_recepcion = datetime.now()
        db.session.commit()
        flash(
            f"Compra {compra.numero} recibida en {compra.dias_entrega_real} días "
            f"(plazo comprometido: {compra.proveedor.plazo_entrega_dias}).",
            "success",
        )

    return redirect(url_for("compras.detalle", compra_id=compra.id))
