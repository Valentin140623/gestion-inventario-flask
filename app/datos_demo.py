"""
Generador de datos de demostración para un restaurante.

Sirve para probar la aplicación con una carta y unos proveedores realistas
sin tener que teclearlos a mano. El propio dueño del restaurante sustituirá
después estos datos por los suyos reales desde la propia aplicación.

Se ejecuta con:  flask cargar-demo

Los datos son inventados pero coherentes entre sí, y hay casos límite a
propósito: un plato con margen bajo, una bebida sin stock, y un proveedor
que solo suministra productos pero del que todavía no se ha registrado
ninguna compra (para comprobar que las métricas no fallan si faltan datos).
"""

from .extensions import db
from .models import Categoria, Producto, RolUsuario, Usuario
from .services import entrada_stock

# ---------------------------------------------------------------------------
# Definición de los datos
# ---------------------------------------------------------------------------

CATEGORIAS = [
    ("Entrantes", "Raciones y aperitivos para compartir"),
    ("Platos principales", "Carnes, pescados y arroces"),
    ("Postres", "Postres caseros"),
    ("Bebidas", "Refrescos, cervezas y otras bebidas"),
    ("Vinos", "Vinos por copa y por botella"),
    ("Café e infusiones", "Cafés, tés e infusiones"),
]

# (referencia, nombre, categoría, precio_venta, coste, stock, stock_mínimo, ubicación,
#  se_vende_por_racion, contenido_envase_ml, tamano_racion_ml, nombre_racion)
#
# En los productos que NO se venden por ración, "coste" es directamente el
# coste de adquisición de la unidad. En los que SÍ se venden por ración
# (cerveza de barril, vino de la casa...), "coste" ya viene calculado como
# precio del envase ÷ raciones que salen de él, para que estos datos de
# ejemplo queden coherentes con lo que haría la aplicación de verdad.
PRODUCTOS = [
    # --- Entrantes -----------------------------------------------------
    ("ENT-001", "Croquetas de jamón (6 uds.)", "Entrantes", 8.50, 2.90, 40, 10, "Cocina",
     False, None, None, None),
    ("ENT-002", "Ensalada César", "Entrantes", 9.90, 3.20, 30, 8, "Cocina",
     False, None, None, None),
    ("ENT-003", "Pan con tomate y jamón", "Entrantes", 7.50, 2.40, 35, 10, "Cocina",
     False, None, None, None),
    ("ENT-004", "Patatas bravas", "Entrantes", 6.50, 1.80, 45, 10, "Cocina",
     False, None, None, None),

    # --- Platos principales ---------------------------------------------
    ("PRI-001", "Entrecot de ternera con patatas", "Platos principales", 19.50, 8.20, 20, 6, "Cocina",
     False, None, None, None),
    ("PRI-002", "Merluza a la romana", "Platos principales", 16.90, 6.10, 18, 5, "Cocina",
     False, None, None, None),
    ("PRI-003", "Arroz de marisco (para 2)", "Platos principales", 28.00, 11.50, 12, 4, "Cocina",
     False, None, None, None),
    # Margen ajustado a propósito: debe saltar la alerta de bajo margen.
    ("PRI-004", "Menú del día completo", "Platos principales", 13.90, 12.10, 60, 15, "Cocina",
     False, None, None, None),
    # Sin stock a propósito: debe aparecer en las alertas de rotura.
    ("PRI-005", "Rabo de toro estofado", "Platos principales", 21.50, 8.90, 0, 5, "Cocina",
     False, None, None, None),

    # --- Postres ----------------------------------------------------------
    ("POS-001", "Tarta de queso casera", "Postres", 6.50, 1.90, 25, 8, "Cocina",
     False, None, None, None),
    ("POS-002", "Flan de huevo", "Postres", 4.90, 1.10, 30, 8, "Cocina",
     False, None, None, None),
    ("POS-003", "Helado artesano (2 bolas)", "Postres", 5.50, 1.60, 40, 10, "Congelador",
     False, None, None, None),

    # --- Bebidas: aquí están los productos que se venden por ración ------
    #
    # Cerveza de barril: barril de 30 L (30000 ml) a 55 € el barril, servida
    # en cañas de 300 ml. 30000 / 300 = 100 cañas por barril.
    # Coste por caña = 55 / 100 = 0,55 €.
    ("BEB-001", "Cerveza (caña)", "Bebidas", 2.30, 0.55, 140, 40, "Barra",
     True, 30000, 300, "caña"),

    # Refresco de cola: se compra y se vende por lata, sin conversión.
    ("BEB-002", "Refresco de cola (lata)", "Bebidas", 2.50, 0.65, 96, 24, "Barra",
     False, None, None, None),
    ("BEB-003", "Agua mineral 50cl", "Bebidas", 1.80, 0.35, 120, 30, "Barra",
     False, None, None, None),
    ("BEB-004", "Zumo natural de naranja", "Bebidas", 3.50, 1.20, 20, 8, "Barra",
     False, None, None, None),

    # --- Vinos: otro caso de venta por ración -----------------------------
    #
    # Vino de la casa: botella de 750 ml a 7 € la botella, servido en copas
    # de 150 ml. 750 / 150 = 5 copas por botella. Coste por copa = 7 / 5 = 1,40 €.
    ("VIN-001", "Vino de la casa (copa)", "Vinos", 3.50, 1.40, 45, 15, "Bodega",
     True, 750, 150, "copa"),

    # Vino reserva: se vende por botella entera, sin conversión.
    ("VIN-002", "Vino Rioja Reserva (botella)", "Vinos", 22.00, 11.50, 18, 6, "Bodega",
     False, None, None, None),

    # --- Café e infusiones --------------------------------------------------
    ("CAF-001", "Café solo/cortado", "Café e infusiones", 1.60, 0.30, 500, 50, "Barra",
     False, None, None, None),
    ("CAF-002", "Té e infusiones", "Café e infusiones", 1.90, 0.35, 80, 20, "Barra",
     False, None, None, None),
]

# (nombre, email, rol, contraseña)
USUARIOS = [
    ("Ana López García",   "sala@labuenamesa.com",       RolUsuario.ALMACEN,    "Sala12345"),
    ("Javier Ruiz Ortega", "financiero@labuenamesa.com",  RolUsuario.FINANCIERO, "Finanzas1234"),
]


def cargar_datos_demo(usuario_responsable):
    """
    Inserta las categorías, los productos de la carta y los usuarios de ejemplo.

    Recibe el usuario al que se atribuirán los movimientos de stock iniciales:
    todo movimiento de inventario necesita un usuario responsable, porque la
    trazabilidad es un requisito del sistema.

    La función es IDEMPOTENTE: comprueba antes de crear cada elemento, así que
    ejecutarla dos veces no duplica nada.

    Devuelve un diccionario con el recuento de lo creado.
    """
    resumen = {"categorias": 0, "productos": 0, "usuarios": 0}

    # --- Categorías --------------------------------------------------------
    categorias = {}
    for nombre, descripcion in CATEGORIAS:
        categoria = Categoria.query.filter_by(nombre=nombre).first()
        if not categoria:
            categoria = Categoria(nombre=nombre, descripcion=descripcion)
            db.session.add(categoria)
            resumen["categorias"] += 1
        categorias[nombre] = categoria

    # flush() envía los INSERT y asigna los id, sin confirmar todavía la
    # transacción. Los productos necesitan el id de su categoría.
    db.session.flush()

    # --- Productos de la carta ----------------------------------------------
    for (ref, nombre, cat, precio, coste, stock, minimo, ubicacion,
         por_racion, contenido_ml, tamano_ml, nombre_racion) in PRODUCTOS:

        if Producto.query.filter_by(referencia=ref).first():
            continue

        producto = Producto(
            referencia=ref,
            nombre=nombre,
            categoria=categorias[cat],
            precio_venta=precio,
            coste_adquisicion=coste,
            stock_actual=0,  # lo pondrá el movimiento de entrada
            stock_minimo=minimo,
            ubicacion_almacen=ubicacion,
            activo=True,
            se_vende_por_racion=por_racion,
            contenido_envase_ml=contenido_ml,
            tamano_racion_ml=tamano_ml,
            nombre_racion=nombre_racion,
        )
        db.session.add(producto)

        # El stock inicial entra por el servicio de inventario, igual que en
        # la aplicación real: así estos productos también tienen su historial.
        if stock > 0:
            motivo = "Carga inicial de inventario"
            if por_racion:
                motivo += f" ({round(stock / (contenido_ml / tamano_ml), 1)} envases equivalentes)"
            entrada_stock(producto, stock, usuario_responsable, motivo=motivo)

        resumen["productos"] += 1

    # --- Usuarios de ejemplo ----------------------------------------------
    for nombre, email, rol, password in USUARIOS:
        if Usuario.query.filter_by(email=email).first():
            continue
        usuario = Usuario(nombre=nombre, email=email, rol=rol, activo=True)
        usuario.set_password(password)
        db.session.add(usuario)
        resumen["usuarios"] += 1

    db.session.commit()
    return resumen


# ---------------------------------------------------------------------------
# Ventas históricas
# ---------------------------------------------------------------------------

CLIENTES = [
    "Mesa 1", "Mesa 2", "Mesa 3", "Mesa 4", "Mesa 5", "Mesa 6", "Mesa 7",
    "Mesa 8", "Terraza 1", "Terraza 2", "Terraza 3", "Barra", "Para llevar",
]


def cargar_ventas_demo(usuarios, dias=90, semilla=42):
    """
    Genera tickets de venta repartidos por los últimos meses, con
    reposiciones de stock cuando hace falta.

    Sin estos datos, las métricas de análisis (rotación, productos más
    vendidos, evolución de ventas) no tendrían nada que mostrar.

    La semilla fija hace que el resultado sea siempre el mismo, para que las
    capturas de la memoria coincidan con lo que se ve al ejecutar el proyecto.
    """
    import random
    from datetime import datetime, timedelta

    from .models import LineaVenta, MovimientoInventario, TipoMovimiento, Venta

    aleatorio = random.Random(semilla)
    productos = Producto.query.filter_by(activo=True).all()
    if not productos:
        return 0

    # Peso de cada producto: cuanto más alto, más se pide. Las bebidas y los
    # entrantes se piden mucho más que los platos principales, como en
    # cualquier restaurante real.
    pesos = {}
    for p in productos:
        if p.categoria.nombre in ("Bebidas", "Vinos", "Café e infusiones"):
            pesos[p.id] = aleatorio.randint(6, 12)
        elif p.categoria.nombre == "Entrantes":
            pesos[p.id] = aleatorio.randint(4, 9)
        else:
            pesos[p.id] = aleatorio.randint(2, 6)

    contador = 0
    creadas = 0

    for dia in range(dias, 0, -1):
        fecha_dia = datetime.now() - timedelta(days=dia)

        # Los fines de semana hay más comensales que entre semana.
        num_ventas = aleatorio.randint(6, 12) if fecha_dia.weekday() >= 5 else aleatorio.randint(3, 8)

        for _ in range(num_ventas):
            contador += 1
            # Comidas al mediodía, cenas por la noche.
            hora = aleatorio.choice(list(range(13, 16)) + list(range(20, 23)))
            fecha = fecha_dia.replace(hour=hora, minute=aleatorio.randint(0, 59))

            venta = Venta(
                numero=f"V-{fecha.year}-{contador:04d}",
                fecha=fecha,
                cliente=aleatorio.choice(CLIENTES),
                usuario=aleatorio.choice(usuarios),
            )
            db.session.add(venta)

            # Un ticket de restaurante suele tener bastantes líneas: bebida,
            # entrante, plato, postre...
            for producto in aleatorio.sample(productos, min(len(productos), aleatorio.randint(2, 5))):
                cantidad = aleatorio.randint(1, 3)

                # Si no hay stock suficiente, simulamos una reposición previa
                # (una nueva remesa del proveedor, o un barril nuevo).
                if producto.stock_actual < cantidad:
                    reposicion = max(cantidad, pesos[producto.id] * 8)
                    producto.stock_actual += reposicion
                    db.session.add(
                        MovimientoInventario(
                            producto=producto,
                            tipo=TipoMovimiento.ENTRADA,
                            cantidad=reposicion,
                            stock_resultante=producto.stock_actual,
                            motivo="Reposición de stock",
                            usuario=venta.usuario,
                            fecha=fecha - timedelta(hours=2),
                        )
                    )

                db.session.add(
                    LineaVenta(
                        venta=venta,
                        producto=producto,
                        cantidad=cantidad,
                        precio_unitario=producto.precio_venta,
                        coste_unitario=producto.coste_adquisicion,
                    )
                )

                producto.stock_actual -= cantidad
                db.session.add(
                    MovimientoInventario(
                        producto=producto,
                        tipo=TipoMovimiento.SALIDA,
                        cantidad=-cantidad,
                        stock_resultante=producto.stock_actual,
                        motivo="Venta",
                        documento_referencia=venta.numero,
                        usuario=venta.usuario,
                        fecha=fecha,
                    )
                )

            creadas += 1

    db.session.commit()
    return creadas


# ---------------------------------------------------------------------------
# Proveedores y compras
# ---------------------------------------------------------------------------

# (nombre, CIF, contacto, email, teléfono, condiciones de pago, plazo, factor precio)
#
# El "factor precio" multiplica el coste de referencia del producto: 1.00 es
# el precio base, 1.10 significa un 10 % más caro. Sirve para que la
# comparativa de proveedores muestre diferencias reales.
PROVEEDORES = [
    ("Distribuciones Hostelería Sur S.L.", "B41234567", "Rocío Campos",
     "pedidos.hosteleriasur@example.com", "600 000 001", "30 días fecha factura", 2, 1.00),
    ("Mercado Central de Abastos", "B45671234", "Manuel Ortiz",
     "ventas.mercadoabastos@example.com", "600 000 002", "Contado", 1, 0.95),
    ("Carnicería y Charcutería Prieto", "B48765432", "Isabel Prieto",
     "pedidos.carniceriaprieto@example.com", "600 000 003", "15 días fecha factura", 1, 1.05),
    ("Cervezas y Bebidas del Sur", "B49988776", "Fernando Ruiz",
     "comercial.bebidasdelsur@example.com", "600 000 004", "30 días fecha factura", 3, 1.00),
    # Este proveedor solo suministra vinos, y todavía no se le ha hecho
    # ningún pedido: sirve para comprobar que las métricas del proveedor
    # (plazo real, puntualidad, importe comprado) no fallan cuando no hay
    # ninguna compra registrada.
    ("Bodega Familiar Los Álamos", "B47712398", "Cristina Álamo",
     "cristina.bodegalosalamos@example.com", "600 000 005", "Pago al recibir", 4, 1.10),
]


def cargar_proveedores_demo(usuario_responsable, semilla=42):
    """
    Crea los proveedores, los asocia a productos con precios propios y genera
    un histórico de compras (salvo el último proveedor, a propósito: ver la
    nota en PROVEEDORES).
    """
    import random
    from datetime import datetime, timedelta

    from .models import Compra, LineaCompra, MovimientoInventario, Proveedor, ProductoProveedor, TipoMovimiento

    aleatorio = random.Random(semilla)

    # --- Proveedores ---------------------------------------------------------
    proveedores = []
    for nombre, cif, contacto, email, tel, pago, plazo, factor in PROVEEDORES:
        proveedor = Proveedor.query.filter_by(cif=cif).first()
        if not proveedor:
            proveedor = Proveedor(
                nombre=nombre, cif=cif, persona_contacto=contacto, email=email,
                telefono=tel, condiciones_pago=pago, plazo_entrega_dias=plazo,
                direccion="Polígono de proveedores, nave 4", activo=True,
            )
            db.session.add(proveedor)
        proveedores.append((proveedor, factor))

    db.session.flush()

    # Repartimos qué proveedor sirve qué tipo de producto, como en un
    # restaurante real: la carnicería no vende vino, ni la bodega vende carne.
    reparto_por_categoria = {
        "Entrantes": [0, 1, 2],
        "Platos principales": [1, 2],
        "Postres": [1],
        "Bebidas": [3],
        "Vinos": [4],
        "Café e infusiones": [3],
    }

    # --- Asociaciones producto-proveedor -------------------------------------
    productos = Producto.query.filter_by(activo=True).all()
    asociaciones_creadas = 0

    for producto in productos:
        if ProductoProveedor.query.filter_by(producto_id=producto.id).count():
            continue

        indices = reparto_por_categoria.get(producto.categoria.nombre, [0])
        elegidos = [proveedores[i] for i in indices]

        for indice, (proveedor, factor) in enumerate(elegidos):
            variacion = aleatorio.uniform(0.97, 1.03)

            # ProductoProveedor.precio_coste es siempre el precio de la
            # unidad que se COMPRA. Para un producto normal es la misma
            # unidad que se vende, así que basta con el coste actual. Para
            # un producto por ración (barril, botella), el proveedor cobra
            # el ENVASE completo, así que hay que multiplicar el coste por
            # ración por las raciones que salen de él para llegar al precio
            # real del barril o la botella.
            coste_base = producto.coste_adquisicion
            if producto.se_vende_por_racion and producto.raciones_por_envase:
                coste_base *= producto.raciones_por_envase

            precio = round(coste_base * factor * variacion, 2)

            db.session.add(
                ProductoProveedor(
                    producto_id=producto.id,
                    proveedor_id=proveedor.id,
                    precio_coste=precio,
                    referencia_proveedor=f"{proveedor.cif[:3]}-{producto.referencia}",
                    plazo_entrega_dias=proveedor.plazo_entrega_dias + aleatorio.randint(-1, 2),
                    cantidad_minima_pedido=aleatorio.choice([1, 1, 6, 12]),
                    es_preferente=(indice == 0),
                )
            )
            asociaciones_creadas += 1

    db.session.flush()

    # --- Compras históricas --------------------------------------------------
    #
    # A propósito NO generamos ninguna compra para "Bodega Familiar Los
    # Álamos" (el último proveedor de la lista): así queda un proveedor real
    # con productos asociados pero sin historial de pedidos.
    compras_creadas = 0
    if Compra.query.count() == 0:
        contador = 0
        proveedores_con_compras = proveedores[:-1]

        for semana in range(12, 0, -1):
            fecha = datetime.now() - timedelta(weeks=semana)

            for proveedor, factor in aleatorio.sample(
                proveedores_con_compras, aleatorio.randint(1, len(proveedores_con_compras))
            ):
                contador += 1

                retraso = aleatorio.randint(-1, 1) if factor >= 1.0 else aleatorio.randint(0, 4)
                dias_reales = max(0, proveedor.plazo_entrega_dias + retraso)

                compra = Compra(
                    numero=f"C-{fecha.year}-{contador:04d}",
                    fecha=fecha,
                    proveedor=proveedor,
                    usuario=usuario_responsable,
                    fecha_recepcion=fecha + timedelta(days=dias_reales),
                )
                db.session.add(compra)

                suyos = ProductoProveedor.query.filter_by(proveedor_id=proveedor.id).all()
                if not suyos:
                    continue

                for asociacion in aleatorio.sample(suyos, min(len(suyos), aleatorio.randint(1, 4))):
                    producto = asociacion.producto

                    if producto.se_vende_por_racion:
                        # Aquí "cantidad" son ENVASES (barriles, botellas), y
                        # el stock se convierte a raciones, igual que hace la
                        # aplicación real en services/ventas.py.
                        envases = aleatorio.randint(1, 3)
                        raciones = round(envases * producto.raciones_por_envase)

                        db.session.add(
                            LineaCompra(
                                compra=compra, producto=producto,
                                cantidad=envases, precio_unitario=asociacion.precio_coste,
                            )
                        )
                        producto.stock_actual += raciones
                        producto.coste_adquisicion = asociacion.precio_coste / producto.raciones_por_envase
                        cantidad_stock = raciones
                    else:
                        cantidad_stock = aleatorio.randint(10, 40)
                        db.session.add(
                            LineaCompra(
                                compra=compra, producto=producto,
                                cantidad=cantidad_stock, precio_unitario=asociacion.precio_coste,
                            )
                        )
                        producto.stock_actual += cantidad_stock

                    db.session.add(
                        MovimientoInventario(
                            producto=producto,
                            tipo=TipoMovimiento.ENTRADA,
                            cantidad=cantidad_stock,
                            stock_resultante=producto.stock_actual,
                            motivo=f"Compra a {proveedor.nombre}",
                            documento_referencia=compra.numero,
                            usuario=usuario_responsable,
                            fecha=compra.fecha_recepcion,
                        )
                    )

                compras_creadas += 1

    db.session.commit()
    return {"proveedores": len(proveedores), "asociaciones": asociaciones_creadas, "compras": compras_creadas}
