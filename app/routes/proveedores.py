"""
Rutas de proveedores: gestión, asociación de productos y comparativa.
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..forms.proveedor import FormularioAsociarProducto, FormularioProveedor
from ..models import Producto, ProductoProveedor, Proveedor
from ..services.proveedores import (
    comparar_proveedores_de,
    metricas_proveedor,
    ranking_proveedores,
)
from ..utils import permiso_requerido

bp = Blueprint("proveedores", __name__, url_prefix="/proveedores")


@bp.route("/")
@permiso_requerido("proveedores.ver")
def listar():
    """Listado de proveedores con sus métricas."""
    busqueda = request.args.get("busqueda", "", type=str).strip()

    consulta = Proveedor.query
    if busqueda:
        patron = f"%{busqueda}%"
        consulta = consulta.filter(
            db.or_(Proveedor.nombre.ilike(patron), Proveedor.cif.ilike(patron))
        )

    proveedores = consulta.order_by(Proveedor.nombre).all()

    # Métricas de cada uno, para mostrarlas en la tabla.
    datos = [(p, metricas_proveedor(p)) for p in proveedores]

    return render_template(
        "proveedores/listar.html",
        titulo="Proveedores",
        datos=datos,
        busqueda=busqueda,
    )


@bp.route("/<int:proveedor_id>")
@permiso_requerido("proveedores.ver")
def detalle(proveedor_id):
    """Ficha del proveedor: datos, productos que suministra e histórico de compras."""
    proveedor = db.get_or_404(Proveedor, proveedor_id)

    return render_template(
        "proveedores/detalle.html",
        titulo=proveedor.nombre,
        proveedor=proveedor,
        metricas=metricas_proveedor(proveedor),
        asociaciones=proveedor.productos_asociados.all(),
        compras=proveedor.compras.order_by(db.desc("fecha")).limit(20).all(),
    )


@bp.route("/nuevo", methods=["GET", "POST"])
@permiso_requerido("proveedores.editar")
def crear():
    """Alta de proveedor."""
    formulario = FormularioProveedor()

    if formulario.validate_on_submit():
        proveedor = Proveedor(
            nombre=formulario.nombre.data.strip(),
            cif=formulario.cif.data.strip().upper(),
            persona_contacto=formulario.persona_contacto.data,
            email=formulario.email.data,
            telefono=formulario.telefono.data,
            direccion=formulario.direccion.data,
            condiciones_pago=formulario.condiciones_pago.data,
            plazo_entrega_dias=formulario.plazo_entrega_dias.data,
            observaciones=formulario.observaciones.data,
            activo=formulario.activo.data,
        )
        db.session.add(proveedor)
        db.session.commit()
        flash(f"Proveedor «{proveedor.nombre}» creado.", "success")
        return redirect(url_for("proveedores.detalle", proveedor_id=proveedor.id))

    return render_template(
        "proveedores/formulario.html", titulo="Nuevo proveedor", formulario=formulario
    )


@bp.route("/<int:proveedor_id>/editar", methods=["GET", "POST"])
@permiso_requerido("proveedores.editar")
def editar(proveedor_id):
    """Edición de proveedor."""
    proveedor = db.get_or_404(Proveedor, proveedor_id)
    formulario = FormularioProveedor(obj=proveedor, proveedor_id=proveedor.id)

    if formulario.validate_on_submit():
        proveedor.nombre = formulario.nombre.data.strip()
        proveedor.cif = formulario.cif.data.strip().upper()
        proveedor.persona_contacto = formulario.persona_contacto.data
        proveedor.email = formulario.email.data
        proveedor.telefono = formulario.telefono.data
        proveedor.direccion = formulario.direccion.data
        proveedor.condiciones_pago = formulario.condiciones_pago.data
        proveedor.plazo_entrega_dias = formulario.plazo_entrega_dias.data
        proveedor.observaciones = formulario.observaciones.data
        proveedor.activo = formulario.activo.data
        db.session.commit()
        flash(f"Proveedor «{proveedor.nombre}» actualizado.", "success")
        return redirect(url_for("proveedores.detalle", proveedor_id=proveedor.id))

    return render_template(
        "proveedores/formulario.html",
        titulo=f"Editar: {proveedor.nombre}",
        formulario=formulario,
        proveedor=proveedor,
    )


@bp.route("/<int:proveedor_id>/asociar", methods=["GET", "POST"])
@permiso_requerido("proveedores.editar")
def asociar_producto(proveedor_id):
    """Asocia un producto al proveedor con su precio y condiciones."""
    proveedor = db.get_or_404(Proveedor, proveedor_id)
    formulario = FormularioAsociarProducto()

    if formulario.validate_on_submit():
        # No permitimos duplicar la pareja producto-proveedor: la base de datos
        # lo impediría con la restricción UNIQUE, pero así damos mejor mensaje.
        ya_existe = ProductoProveedor.query.filter_by(
            proveedor_id=proveedor.id, producto_id=formulario.producto_id.data
        ).first()

        if ya_existe:
            flash("Ese producto ya está asociado a este proveedor. Edita el precio existente.", "warning")
            return redirect(url_for("proveedores.detalle", proveedor_id=proveedor.id))

        asociacion = ProductoProveedor(
            proveedor_id=proveedor.id,
            producto_id=formulario.producto_id.data,
            precio_coste=formulario.precio_coste.data,
            referencia_proveedor=formulario.referencia_proveedor.data,
            plazo_entrega_dias=formulario.plazo_entrega_dias.data,
            cantidad_minima_pedido=formulario.cantidad_minima_pedido.data,
            es_preferente=formulario.es_preferente.data,
        )

        # Solo puede haber un proveedor preferente por producto: si se marca
        # este, se desmarcan los demás.
        if asociacion.es_preferente:
            ProductoProveedor.query.filter_by(
                producto_id=formulario.producto_id.data
            ).update({"es_preferente": False})

        db.session.add(asociacion)
        db.session.commit()
        flash("Producto asociado al proveedor.", "success")
        return redirect(url_for("proveedores.detalle", proveedor_id=proveedor.id))

    return render_template(
        "proveedores/asociar.html",
        titulo=f"Asociar producto a {proveedor.nombre}",
        formulario=formulario,
        proveedor=proveedor,
    )


@bp.route("/asociacion/<int:asociacion_id>/eliminar", methods=["POST"])
@permiso_requerido("proveedores.editar")
def eliminar_asociacion(asociacion_id):
    """Quita la asociación entre un producto y un proveedor."""
    asociacion = db.get_or_404(ProductoProveedor, asociacion_id)
    proveedor_id = asociacion.proveedor_id
    db.session.delete(asociacion)
    db.session.commit()
    flash("Asociación eliminada.", "info")
    return redirect(url_for("proveedores.detalle", proveedor_id=proveedor_id))


@bp.route("/comparativa")
@permiso_requerido("proveedores.ver")
def comparativa():
    """
    Comparativa de precios entre proveedores para un producto.

    Es la pantalla que responde directamente al requisito 4: "comparar precios
    y condiciones entre ellos".
    """
    producto_id = request.args.get("producto", 0, type=int)

    producto = db.session.get(Producto, producto_id) if producto_id else None
    comparacion = comparar_proveedores_de(producto) if producto else []

    # Solo ofrecemos en el desplegable los productos que tienen más de un
    # proveedor: comparar uno solo no aporta nada.
    productos_comparables = [
        p for p in Producto.query.order_by(Producto.nombre).all()
        if p.proveedores_asociados.count() > 1
    ]

    return render_template(
        "proveedores/comparativa.html",
        titulo="Comparativa de proveedores",
        producto=producto,
        comparacion=comparacion,
        productos=productos_comparables,
        ranking=ranking_proveedores(),
    )
