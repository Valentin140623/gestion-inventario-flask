"""
Gestión de usuarios. Solo para administradores.

Cubre la parte del requisito 1: "El administrador podrá crear, editar y
eliminar usuarios, productos y proveedores".
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..extensions import db
from ..forms.usuario import FormularioUsuario
from ..models import RolUsuario, Usuario
from ..utils import permiso_requerido

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/usuarios")
@permiso_requerido("usuarios.gestionar")
def listar_usuarios():
    """Listado de usuarios."""
    return render_template(
        "admin/usuarios.html",
        titulo="Usuarios",
        usuarios=Usuario.query.order_by(Usuario.nombre).all(),
    )


@bp.route("/usuarios/nuevo", methods=["GET", "POST"])
@permiso_requerido("usuarios.gestionar")
def crear_usuario():
    """
    Alta de usuario por parte del administrador.

    A diferencia del registro público, aquí SÍ se puede elegir el rol: quien
    usa esta pantalla ya es administrador, así que no hay escalada de
    privilegios posible.
    """
    formulario = FormularioUsuario()

    if formulario.validate_on_submit():
        usuario = Usuario(
            nombre=formulario.nombre.data.strip(),
            email=formulario.email.data.lower().strip(),
            rol=RolUsuario[formulario.rol.data],
            activo=formulario.activo.data,
        )
        usuario.set_password(formulario.password.data)
        db.session.add(usuario)
        db.session.commit()
        flash(f"Usuario «{usuario.nombre}» creado con el rol {usuario.rol.value}.", "success")
        return redirect(url_for("admin.listar_usuarios"))

    return render_template(
        "admin/formulario_usuario.html", titulo="Nuevo usuario", formulario=formulario
    )


@bp.route("/usuarios/<int:usuario_id>/editar", methods=["GET", "POST"])
@permiso_requerido("usuarios.gestionar")
def editar_usuario(usuario_id):
    """
    Edición de un usuario.

    La contraseña es opcional: si se deja en blanco, se conserva la actual.
    """
    usuario = db.get_or_404(Usuario, usuario_id)

    formulario = FormularioUsuario(usuario_id=usuario.id, es_edicion=True)

    if request.method == "GET":
        # Rellenamos el formulario a mano porque el rol es un Enum y el campo
        # del formulario espera el nombre en texto ("ADMIN", "ALMACEN"...).
        formulario.nombre.data = usuario.nombre
        formulario.email.data = usuario.email
        formulario.rol.data = usuario.rol.name
        formulario.activo.data = usuario.activo

    if formulario.validate_on_submit():
        # ------------------------------------------------------------------
        # Protección: un administrador no puede quitarse a sí mismo el rol de
        # administrador ni desactivarse.
        #
        # Sin esta comprobación, el único administrador del sistema podría
        # dejarse sin permisos por error y nadie podría volver a entrar a
        # gestionar usuarios: habría que arreglarlo desde la consola.
        # ------------------------------------------------------------------
        es_uno_mismo = usuario.id == current_user.id
        pierde_admin = formulario.rol.data != RolUsuario.ADMIN.name or not formulario.activo.data

        if es_uno_mismo and pierde_admin:
            flash(
                "No puedes quitarte a ti mismo el rol de administrador ni desactivar "
                "tu propia cuenta. Pídeselo a otro administrador.",
                "danger",
            )
            return redirect(url_for("admin.editar_usuario", usuario_id=usuario.id))

        usuario.nombre = formulario.nombre.data.strip()
        usuario.email = formulario.email.data.lower().strip()
        usuario.rol = RolUsuario[formulario.rol.data]
        usuario.activo = formulario.activo.data

        # Solo cambiamos la contraseña si han escrito una nueva.
        if formulario.password.data:
            usuario.set_password(formulario.password.data)

        db.session.commit()
        flash(f"Usuario «{usuario.nombre}» actualizado.", "success")
        return redirect(url_for("admin.listar_usuarios"))

    return render_template(
        "admin/formulario_usuario.html",
        titulo=f"Editar: {usuario.nombre}",
        formulario=formulario,
        usuario=usuario,
    )


@bp.route("/usuarios/<int:usuario_id>/cambiar-estado", methods=["POST"])
@permiso_requerido("usuarios.gestionar")
def cambiar_estado(usuario_id):
    """Activa o desactiva un usuario."""
    usuario = db.get_or_404(Usuario, usuario_id)

    if usuario.id == current_user.id:
        flash("No puedes desactivar tu propia cuenta.", "danger")
        return redirect(url_for("admin.listar_usuarios"))

    usuario.activo = not usuario.activo
    db.session.commit()

    estado = "activado" if usuario.activo else "desactivado"
    flash(f"Usuario «{usuario.nombre}» {estado}.", "info")
    return redirect(url_for("admin.listar_usuarios"))


@bp.route("/usuarios/<int:usuario_id>/eliminar", methods=["POST"])
@permiso_requerido("usuarios.gestionar")
def eliminar_usuario(usuario_id):
    """
    Elimina un usuario, siempre que no tenga actividad registrada.

    Igual que con los productos: si ha registrado ventas, compras o
    movimientos, borrarlo dejaría esos documentos sin responsable y se perdería
    la trazabilidad. En ese caso hay que desactivarlo.
    """
    usuario = db.get_or_404(Usuario, usuario_id)

    if usuario.id == current_user.id:
        flash("No puedes eliminar tu propia cuenta.", "danger")
        return redirect(url_for("admin.listar_usuarios"))

    num_ventas = len(usuario.ventas)
    num_compras = len(usuario.compras)
    num_movimientos = len(usuario.movimientos)

    if num_ventas or num_compras or num_movimientos:
        flash(
            f"No se puede eliminar «{usuario.nombre}»: tiene {num_ventas} venta(s), "
            f"{num_compras} compra(s) y {num_movimientos} movimiento(s) registrados. "
            f"Desactívalo para retirarle el acceso conservando el histórico.",
            "warning",
        )
        return redirect(url_for("admin.listar_usuarios"))

    nombre = usuario.nombre
    db.session.delete(usuario)
    db.session.commit()
    flash(f"Usuario «{nombre}» eliminado.", "success")
    return redirect(url_for("admin.listar_usuarios"))
