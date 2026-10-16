"""
Rutas de gestión del catálogo: productos y categorías.

Cubre la parte del requisito 3 que dice: "La plataforma debe permitir crear,
editar y eliminar productos".
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..extensions import db
from ..forms import FormularioCategoria, FormularioProducto
from ..models import Categoria, Producto
from ..services import ErrorInventario, entrada_stock
from ..utils import permiso_requerido

bp = Blueprint("productos", __name__, url_prefix="/productos")

# Número de filas por página en el listado.
POR_PAGINA = 12


# ===========================================================================
# LISTADO
# ===========================================================================


@bp.route("/")
@permiso_requerido("productos.ver")
def listar():
    """
    Listado de productos con búsqueda, filtros, ordenación y paginación.

    Todos los criterios viajan en la URL como parámetros GET
    (/productos/?busqueda=portatil&categoria=2&pagina=3). Es lo correcto para
    una consulta: la URL resultante se puede guardar en marcadores, compartir
    o recargar sin que el navegador avise de reenviar datos, cosa que sí
    pasaría con POST.
    """

    # request.args son los parámetros de la URL. El segundo argumento de get()
    # es el valor por defecto si el parámetro no viene.
    busqueda = request.args.get("busqueda", "", type=str).strip()
    categoria_id = request.args.get("categoria", 0, type=int)
    estado = request.args.get("estado", "activos", type=str)
    alerta = request.args.get("alerta", "", type=str)
    orden = request.args.get("orden", "nombre", type=str)
    pagina = request.args.get("pagina", 1, type=int)

    # ------------------------------------------------------------------
    # Construcción de la consulta por pasos.
    #
    # SQLAlchemy usa evaluación perezosa: cada .filter() NO consulta la base de
    # datos, solo va añadiendo condiciones a un objeto consulta. La consulta
    # real se ejecuta una única vez al final, con .paginate() o .all().
    #
    # Esto permite ir encadenando filtros según lo que haya pedido el usuario,
    # y que la base de datos reciba una sola sentencia SQL optimizada.
    # ------------------------------------------------------------------
    consulta = Producto.query

    if busqueda:
        # ilike es "like" ignorando mayúsculas y minúsculas. Los % son
        # comodines: %portatil% encuentra la palabra en cualquier posición.
        patron = f"%{busqueda}%"
        # db.or_ combina condiciones con OR: buscamos el texto tanto en el
        # nombre como en la referencia.
        consulta = consulta.filter(
            db.or_(Producto.nombre.ilike(patron), Producto.referencia.ilike(patron))
        )

    if categoria_id:
        consulta = consulta.filter(Producto.categoria_id == categoria_id)

    if estado == "activos":
        consulta = consulta.filter(Producto.activo.is_(True))
    elif estado == "inactivos":
        consulta = consulta.filter(Producto.activo.is_(False))
    # estado == "todos": no añadimos filtro.

    if alerta == "stock_bajo":
        # Comparamos dos COLUMNAS entre sí, no una columna con un valor. Esto
        # se traduce a "WHERE stock_actual <= stock_minimo" en SQL, y lo
        # resuelve la base de datos.
        #
        # Alternativa descartada: traer todos los productos a Python y filtrar
        # con la propiedad necesita_reposicion. Funcionaría, pero obligaría a
        # cargar el catálogo entero en memoria en cada consulta. Filtrar en la
        # base de datos es mucho más eficiente y permite paginar de verdad.
        consulta = consulta.filter(Producto.stock_actual <= Producto.stock_minimo)
    elif alerta == "sin_stock":
        consulta = consulta.filter(Producto.stock_actual == 0)

    # Ordenación. Usamos un diccionario en lugar de encadenar if/elif por dos
    # motivos: es más legible, y sobre todo evita construir la ordenación
    # concatenando el texto que llega del usuario, lo que abriría la puerta a
    # una inyección SQL. Aquí solo se admiten las claves previstas.
    ordenaciones = {
        "nombre": Producto.nombre.asc(),
        "referencia": Producto.referencia.asc(),
        "precio_asc": Producto.precio_venta.asc(),
        "precio_desc": Producto.precio_venta.desc(),
        "stock_asc": Producto.stock_actual.asc(),
        "stock_desc": Producto.stock_actual.desc(),
        "recientes": Producto.fecha_alta.desc(),
    }
    consulta = consulta.order_by(ordenaciones.get(orden, Producto.nombre.asc()))

    # paginate() ejecuta la consulta trayendo solo las filas de esta página.
    # error_out=False evita un error 404 si se pide una página que no existe
    # (por ejemplo tras filtrar y reducirse el número de resultados).
    paginacion = consulta.paginate(page=pagina, per_page=POR_PAGINA, error_out=False)

    return render_template(
        "productos/listar.html",
        titulo="Productos",
        paginacion=paginacion,
        productos=paginacion.items,
        categorias=Categoria.query.order_by(Categoria.nombre).all(),
        # Devolvemos los filtros aplicados para que el formulario de búsqueda
        # se repinte con lo que el usuario había seleccionado.
        filtros={
            "busqueda": busqueda,
            "categoria": categoria_id,
            "estado": estado,
            "alerta": alerta,
            "orden": orden,
        },
    )


@bp.route("/<int:producto_id>")
@permiso_requerido("productos.ver")
def detalle(producto_id):
    """
    Ficha completa de un producto.

    <int:producto_id> captura un número de la URL y lo pasa como argumento a
    la función. El convertidor int garantiza que /productos/abc devuelva un 404
    en lugar de llegar a la vista con un valor inesperado.
    """
    # get_or_404 busca por clave primaria y, si no existe, corta con un 404.
    # Ahorra escribir la comprobación manual en cada vista.
    producto = db.get_or_404(Producto, producto_id)

    # Últimos movimientos de inventario de este producto, para la ficha.
    movimientos = (
        producto.movimientos.order_by(db.desc("fecha")).limit(10).all()
    )

    return render_template(
        "productos/detalle.html",
        titulo=producto.nombre,
        producto=producto,
        movimientos=movimientos,
    )


# ===========================================================================
# ALTA Y EDICIÓN
# ===========================================================================


def _ocultar_campos_financieros(formulario):
    """
    Quita del formulario el coste de adquisición si el usuario no puede verlo.

    CONTROL DE ACCESO A NIVEL DE CAMPO. El responsable de almacén puede dar de
    alta y editar productos (necesita hacerlo para gestionar el catálogo), pero
    no debe ver ni modificar la información económica: el coste al que compramos
    es un dato sensible del que se deduce el margen de la empresa.

    "del formulario.campo" retira el campo de esta instancia concreta del
    formulario: deja de pintarse en el HTML, deja de validarse y deja de leerse
    de la petición. Aunque alguien lo enviara a mano, sería ignorado.

    MATIZ IMPORTANTE: WTForms no borra realmente el atributo, lo deja valiendo
    None. Por eso, para saber si un campo sigue presente, hay que comprobar
    "getattr(formulario, 'campo', None) is not None" y NO hasattr(), que
    devolvería True igualmente. En las plantillas, por el mismo motivo, se usa
    "is not none" y no "is defined".

    El guion bajo inicial del nombre indica, por convención, que es una función
    interna de este módulo y no una vista.
    """
    if not current_user.tiene_permiso("analisis.financiero"):
        del formulario.coste_adquisicion
        # precio_envase también revela un dato económico (lo que cuesta el
        # barril o la botella al proveedor): se oculta por el mismo motivo.
        # contenido_envase_ml, tamano_racion_ml y nombre_racion NO se ocultan,
        # porque son datos operativos (cuánto sirve cada copa) que el
        # responsable de almacén sí necesita para gestionar el producto.
        del formulario.precio_envase


def _calcular_coste(formulario, coste_anterior=0.0):
    """
    Calcula el coste de adquisición (por unidad vendida) a partir del formulario.

    Si el producto se vende por ración (barril, botella...), el coste NO es el
    que se ha tecleado a mano: se calcula dividiendo el precio del envase
    entre el número de raciones que salen de él. Así el coste por copa
    siempre refleja el precio real del envase, sin que nadie tenga que hacer
    la cuenta.

        coste por copa = precio del barril / (contenido del barril / tamaño de la copa)

    Ejemplo: un barril de 30 000 ml a 45 € da 100 cañas de 300 ml, así que
    cada caña cuesta 45 / 100 = 0,45 €.

    Si el campo del coste está oculto por permisos (ver
    _ocultar_campos_financieros), se conserva el coste que ya tenía el
    producto en vez de tocarlo.
    """
    # Si coste_adquisicion o precio_envase están ocultos (rol sin permiso
    # financiero), no hay ningún dato económico que tocar: se conserva el
    # coste que ya tenía el producto.
    if getattr(formulario, "coste_adquisicion", None) is None:
        return coste_anterior
    if getattr(formulario, "precio_envase", None) is None:
        return coste_anterior

    if formulario.se_vende_por_racion.data:
        raciones = formulario.contenido_envase_ml.data / formulario.tamano_racion_ml.data
        return formulario.precio_envase.data / raciones

    return formulario.coste_adquisicion.data or 0.0


@bp.route("/nuevo", methods=["GET", "POST"])
@permiso_requerido("productos.editar")
def crear():
    """Alta de un producto nuevo."""

    formulario = FormularioProducto()
    _ocultar_campos_financieros(formulario)

    # Si todavía no hay ninguna categoría no se puede crear un producto,
    # porque la categoría es obligatoria. Guiamos al usuario en vez de
    # dejarle ver un desplegable vacío sin explicación.
    if not formulario.categoria_id.choices:
        flash("Antes de crear productos debes dar de alta al menos una categoría.", "warning")
        return redirect(url_for("productos.crear_categoria"))

    if formulario.validate_on_submit():

        # Si el campo del coste se ocultó por permisos, el producto se crea con
        # coste 0 y un usuario con permisos financieros lo completará después.
        # Si se vende por ración, el coste se calcula solo a partir del envase.
        coste = _calcular_coste(formulario)

        producto = Producto(
            # La referencia se normaliza a mayúsculas: así "por-001" y "POR-001"
            # son la misma, y la restricción de unicidad funciona de verdad.
            referencia=formulario.referencia.data.strip().upper(),
            nombre=formulario.nombre.data.strip(),
            descripcion=formulario.descripcion.data,
            categoria_id=formulario.categoria_id.data,
            precio_venta=formulario.precio_venta.data,
            coste_adquisicion=coste,
            stock_actual=0,  # el stock inicial se aplicará como movimiento
            stock_minimo=formulario.stock_minimo.data,
            ubicacion_almacen=formulario.ubicacion_almacen.data,
            activo=formulario.activo.data,
            se_vende_por_racion=formulario.se_vende_por_racion.data,
            contenido_envase_ml=formulario.contenido_envase_ml.data if formulario.se_vende_por_racion.data else None,
            tamano_racion_ml=formulario.tamano_racion_ml.data if formulario.se_vende_por_racion.data else None,
            nombre_racion=formulario.nombre_racion.data if formulario.se_vende_por_racion.data else None,
        )
        db.session.add(producto)

        # El stock inicial NO se asigna directamente al campo: se registra como
        # una entrada de inventario. Así el historial arranca desde la primera
        # unidad y el stock siempre es la suma de sus movimientos.
        stock_inicial = formulario.stock_inicial.data or 0
        if stock_inicial > 0:
            try:
                entrada_stock(
                    producto,
                    stock_inicial,
                    current_user,
                    motivo="Stock inicial en el alta del producto",
                )
            except ErrorInventario as e:
                db.session.rollback()
                flash(str(e), "danger")
                return render_template(
                    "productos/formulario.html",
                    titulo="Nuevo producto",
                    formulario=formulario,
                    es_edicion=False,
                )

        # Un único commit al final: o se guardan el producto y su movimiento
        # de stock inicial, o no se guarda nada.
        db.session.commit()

        flash(f"Producto «{producto.nombre}» creado correctamente.", "success")
        return redirect(url_for("productos.detalle", producto_id=producto.id))

    return render_template(
        "productos/formulario.html",
        titulo="Nuevo producto",
        formulario=formulario,
        es_edicion=False,
    )


@bp.route("/<int:producto_id>/editar", methods=["GET", "POST"])
@permiso_requerido("productos.editar")
def editar(producto_id):
    """Edición de un producto existente."""

    producto = db.get_or_404(Producto, producto_id)

    # obj=producto rellena automáticamente el formulario con los valores
    # actuales: WTForms busca en el objeto un atributo con el mismo nombre que
    # cada campo. Nos ahorra asignarlos uno a uno.
    formulario = FormularioProducto(obj=producto, producto_id=producto.id)
    _ocultar_campos_financieros(formulario)

    # obj=producto no puede rellenar precio_envase, porque ese campo no
    # existe en el modelo: solo guardamos el coste por ración ya calculado,
    # no el precio del envase que lo originó. Sin este paso, el campo llegaría
    # vacío a la plantilla y, si el usuario guardara sin tocarlo, la próxima
    # línea de _calcular_coste() intentaría dividir "None" entre las raciones.
    #
    # Lo reconstruimos deshaciendo el cálculo: coste_por_racion × raciones.
    if (
        request.method == "GET"
        and producto.se_vende_por_racion
        and producto.raciones_por_envase
        and getattr(formulario, "precio_envase", None) is not None
    ):
        formulario.precio_envase.data = round(
            producto.coste_adquisicion * producto.raciones_por_envase, 2
        )

    # Al editar no se toca el stock: para eso están los movimientos de
    # inventario, que dejan rastro de quién y por qué. Ver la explicación en
    # el formulario.
    del formulario.stock_inicial

    if formulario.validate_on_submit():
        # populate_obj hace lo contrario que obj=: vuelca los datos del
        # formulario sobre el objeto. Como los campos se llaman igual que los
        # atributos del modelo, copia todo de una vez.
        #
        # No lo usamos aquí porque necesitamos normalizar algunos valores
        # (mayúsculas, espacios) y porque populate_obj asignaría también campos
        # que no queremos tocar. Asignar a mano es más largo pero más explícito
        # y más seguro.
        producto.referencia = formulario.referencia.data.strip().upper()
        producto.nombre = formulario.nombre.data.strip()
        producto.descripcion = formulario.descripcion.data
        producto.categoria_id = formulario.categoria_id.data
        producto.precio_venta = formulario.precio_venta.data
        producto.stock_minimo = formulario.stock_minimo.data
        producto.ubicacion_almacen = formulario.ubicacion_almacen.data
        producto.activo = formulario.activo.data
        producto.se_vende_por_racion = formulario.se_vende_por_racion.data
        producto.contenido_envase_ml = formulario.contenido_envase_ml.data if formulario.se_vende_por_racion.data else None
        producto.tamano_racion_ml = formulario.tamano_racion_ml.data if formulario.se_vende_por_racion.data else None
        producto.nombre_racion = formulario.nombre_racion.data if formulario.se_vende_por_racion.data else None

        # El coste solo se actualiza si el usuario tenía permiso para verlo.
        # Si el campo se ocultó, el valor anterior se conserva intacto.
        producto.coste_adquisicion = _calcular_coste(formulario, producto.coste_adquisicion)

        db.session.commit()
        flash(f"Producto «{producto.nombre}» actualizado.", "success")
        return redirect(url_for("productos.detalle", producto_id=producto.id))

    return render_template(
        "productos/formulario.html",
        titulo=f"Editar: {producto.nombre}",
        formulario=formulario,
        producto=producto,
        es_edicion=True,
    )


# ===========================================================================
# BAJA
# ===========================================================================


@bp.route("/<int:producto_id>/cambiar-estado", methods=["POST"])
@permiso_requerido("productos.editar")
def cambiar_estado(producto_id):
    """
    Activa o desactiva un producto (baja lógica).

    Es POST y no GET porque modifica datos. Una acción que cambia el estado del
    sistema nunca debe poder ejecutarse solo con visitar una URL: los
    navegadores y buscadores precargan enlaces, y bastaría con que alguien
    incluyera esa dirección en una imagen para desactivar productos sin querer.
    """
    producto = db.get_or_404(Producto, producto_id)

    # "not" invierte el valor: si estaba activo lo desactiva y al revés.
    producto.activo = not producto.activo
    db.session.commit()

    estado = "reactivado" if producto.activo else "dado de baja"
    flash(f"Producto «{producto.nombre}» {estado}.", "info")

    return redirect(request.referrer or url_for("productos.listar"))


@bp.route("/<int:producto_id>/eliminar", methods=["POST"])
@permiso_requerido("usuarios.gestionar")  # solo el administrador
def eliminar(producto_id):
    """
    Borrado físico de un producto.

    DECISIÓN DE DISEÑO: solo se permite si el producto no tiene histórico.

    Si un producto aparece en ventas o compras pasadas, borrarlo destruiría
    información contable: las ventas de meses anteriores quedarían apuntando a
    un producto inexistente y los informes históricos dejarían de cuadrar. En
    ese caso lo correcto es la baja lógica (activo = False): el producto
    desaparece del catálogo pero el histórico se conserva.

    Por eso el enunciado pide "eliminar productos" y nosotros ofrecemos las dos
    operaciones: baja lógica siempre, borrado real solo cuando es inocuo.
    """
    producto = db.get_or_404(Producto, producto_id)

    # .count() lanza un SELECT COUNT(*) en la base de datos: cuenta sin traer
    # las filas, que es lo que nos interesa aquí.
    num_ventas = producto.lineas_venta.count()
    num_compras = producto.lineas_compra.count()

    if num_ventas or num_compras:
        flash(
            f"No se puede eliminar «{producto.nombre}»: tiene {num_ventas} venta(s) "
            f"y {num_compras} compra(s) asociadas. Puedes darlo de baja para "
            f"retirarlo del catálogo conservando el histórico.",
            "warning",
        )
        return redirect(url_for("productos.detalle", producto_id=producto.id))

    nombre = producto.nombre
    # Los movimientos de inventario y las asociaciones con proveedores se
    # borran solos: lo definimos con cascade="all, delete-orphan" en el modelo.
    db.session.delete(producto)
    db.session.commit()

    flash(f"Producto «{nombre}» eliminado definitivamente.", "success")
    return redirect(url_for("productos.listar"))


# ===========================================================================
# CATEGORÍAS
# ===========================================================================


@bp.route("/categorias")
@permiso_requerido("productos.ver")
def listar_categorias():
    """Listado de categorías."""
    return render_template(
        "productos/categorias.html",
        titulo="Categorías",
        categorias=Categoria.query.order_by(Categoria.nombre).all(),
    )


@bp.route("/categorias/nueva", methods=["GET", "POST"])
@permiso_requerido("productos.editar")
def crear_categoria():
    """Alta de una categoría."""
    formulario = FormularioCategoria()

    if formulario.validate_on_submit():
        categoria = Categoria(
            nombre=formulario.nombre.data.strip(),
            descripcion=formulario.descripcion.data,
        )
        db.session.add(categoria)
        db.session.commit()
        flash(f"Categoría «{categoria.nombre}» creada.", "success")
        return redirect(url_for("productos.listar_categorias"))

    return render_template(
        "productos/formulario_categoria.html",
        titulo="Nueva categoría",
        formulario=formulario,
    )


@bp.route("/categorias/<int:categoria_id>/editar", methods=["GET", "POST"])
@permiso_requerido("productos.editar")
def editar_categoria(categoria_id):
    """Edición de una categoría."""
    categoria = db.get_or_404(Categoria, categoria_id)
    formulario = FormularioCategoria(obj=categoria, categoria_id=categoria.id)

    if formulario.validate_on_submit():
        categoria.nombre = formulario.nombre.data.strip()
        categoria.descripcion = formulario.descripcion.data
        db.session.commit()
        flash(f"Categoría «{categoria.nombre}» actualizada.", "success")
        return redirect(url_for("productos.listar_categorias"))

    return render_template(
        "productos/formulario_categoria.html",
        titulo=f"Editar: {categoria.nombre}",
        formulario=formulario,
        categoria=categoria,
    )


@bp.route("/categorias/<int:categoria_id>/eliminar", methods=["POST"])
@permiso_requerido("productos.editar")
def eliminar_categoria(categoria_id):
    """
    Elimina una categoría, siempre que esté vacía.

    No se puede borrar una categoría con productos dentro: la columna
    categoria_id de productos es NOT NULL, así que esas filas quedarían
    huérfanas y la base de datos rechazaría la operación con un error técnico.
    Lo comprobamos antes para dar un mensaje comprensible.
    """
    categoria = db.get_or_404(Categoria, categoria_id)

    num_productos = categoria.productos.count()
    if num_productos:
        flash(
            f"No se puede eliminar «{categoria.nombre}»: contiene {num_productos} "
            f"producto(s). Reasígnalos a otra categoría primero.",
            "warning",
        )
        return redirect(url_for("productos.listar_categorias"))

    nombre = categoria.nombre
    db.session.delete(categoria)
    db.session.commit()
    flash(f"Categoría «{nombre}» eliminada.", "success")
    return redirect(url_for("productos.listar_categorias"))
