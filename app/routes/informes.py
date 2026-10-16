"""
Informes en PDF y exportaciones a CSV.

Corresponde a las ampliaciones del requisito 6 del enunciado:
"Generación de informes en PDF" y "Exportación de datos".
"""

import csv
import io
from datetime import datetime, timedelta

from flask import Blueprint, Response, request
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..models import Producto
from ..services.analisis import (
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

bp = Blueprint("informes", __name__, url_prefix="/informes")


def euros(valor):
    """Formatea un importe al estilo español. Igual que el filtro de plantillas."""
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{texto} €"


# ===========================================================================
# EXPORTACIÓN A CSV
# ===========================================================================


@bp.route("/exportar/productos")
@permiso_requerido("informes.generar")
def exportar_productos():
    """
    Exporta el catálogo a CSV para abrirlo en Excel.

    Detalles importantes para que Excel lo abra bien en español:
      - delimiter=";" porque Excel en configuración española espera el punto
        y coma, no la coma.
      - El BOM ﻿ al principio le indica a Excel que el fichero está en
        UTF-8; sin él, los acentos aparecen como símbolos raros.
    """
    salida = io.StringIO()
    escritor = csv.writer(salida, delimiter=";")

    escritor.writerow([
        "Referencia", "Nombre", "Categoría", "Precio venta", "Coste",
        "Margen unitario", "Margen %", "Stock", "Stock mínimo",
        "Valor stock", "Ubicación", "Estado",
    ])

    for p in Producto.query.order_by(Producto.referencia).all():
        escritor.writerow([
            p.referencia,
            p.nombre,
            p.categoria.nombre,
            # Cambiamos el punto decimal por coma para que Excel lo lea como
            # número y no como texto.
            f"{p.precio_venta:.2f}".replace(".", ","),
            f"{p.coste_adquisicion:.2f}".replace(".", ","),
            f"{p.margen_unitario:.2f}".replace(".", ","),
            f"{p.margen_porcentual:.2f}".replace(".", ","),
            p.stock_actual,
            p.stock_minimo,
            f"{p.valor_stock:.2f}".replace(".", ","),
            p.ubicacion_almacen or "",
            "Activo" if p.activo else "De baja",
        ])

    nombre = f"catalogo_{datetime.now().strftime('%Y%m%d')}.csv"

    return Response(
        "﻿" + salida.getvalue(),
        mimetype="text/csv",
        # Content-Disposition "attachment" hace que el navegador lo descargue
        # en lugar de mostrarlo en pantalla.
        headers={"Content-Disposition": f"attachment; filename={nombre}"},
    )


@bp.route("/exportar/ventas")
@permiso_requerido("informes.generar")
def exportar_ventas():
    """Exporta las ventas del periodo a CSV."""
    from ..models import LineaVenta, Venta

    desde, hasta = _leer_rango()

    salida = io.StringIO()
    escritor = csv.writer(salida, delimiter=";")
    escritor.writerow([
        "Número", "Fecha", "Cliente", "Referencia", "Producto",
        "Cantidad", "Precio unitario", "Coste unitario", "Subtotal",
        "Beneficio", "Registrada por",
    ])

    ventas = Venta.query.filter(Venta.fecha >= desde, Venta.fecha <= hasta).order_by(Venta.fecha).all()

    for venta in ventas:
        for linea in venta.lineas:
            escritor.writerow([
                venta.numero,
                venta.fecha.strftime("%d/%m/%Y %H:%M"),
                venta.cliente or "",
                linea.producto.referencia,
                linea.producto.nombre,
                linea.cantidad,
                f"{linea.precio_unitario:.2f}".replace(".", ","),
                f"{linea.coste_unitario:.2f}".replace(".", ","),
                f"{linea.subtotal:.2f}".replace(".", ","),
                f"{linea.beneficio:.2f}".replace(".", ","),
                venta.usuario.nombre,
            ])

    nombre = f"ventas_{datetime.now().strftime('%Y%m%d')}.csv"
    return Response(
        "﻿" + salida.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={nombre}"},
    )


# ===========================================================================
# INFORME EN PDF
# ===========================================================================


def _leer_rango():
    """Lee el rango de fechas de la URL, o usa los últimos 90 días."""
    texto_desde = request.args.get("desde", "")
    texto_hasta = request.args.get("hasta", "")

    desde = datetime.strptime(texto_desde, "%Y-%m-%d") if texto_desde else datetime.now() - timedelta(days=90)
    hasta = (datetime.strptime(texto_hasta, "%Y-%m-%d") + timedelta(days=1)) if texto_hasta else datetime.now()
    return desde, hasta


def _tabla(datos, anchos, alineaciones=None):
    """Crea una tabla con el estilo común de los informes."""
    tabla = Table(datos, colWidths=anchos, repeatRows=1)

    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        # Filas alternas en gris claro, para que se lean mejor.
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]

    if alineaciones:
        for columna in alineaciones:
            estilo.append(("ALIGN", (columna, 0), (columna, -1), "RIGHT"))

    tabla.setStyle(TableStyle(estilo))
    return tabla


@bp.route("/pdf")
@permiso_requerido("informes.generar")
def informe_pdf():
    """
    Genera el informe de gestión en PDF.

    Se construye en memoria (io.BytesIO) y se devuelve directamente al
    navegador, sin escribir ningún fichero en el servidor.
    """
    from flask import current_app

    nombre_app = current_app.config["NOMBRE_APP"]

    desde, hasta = _leer_rango()
    resumen = resumen_periodo(desde, hasta)

    buffer = io.BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=1.8 * cm, bottomMargin=1.8 * cm,
        title=f"Informe de gestión · {nombre_app}",
    )

    estilos = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        "TituloPropio", parent=estilos["Title"],
        fontSize=18, textColor=colors.HexColor("#1e293b"), spaceAfter=4,
    )
    estilo_sub = ParagraphStyle(
        "SubPropio", parent=estilos["Normal"],
        fontSize=9, textColor=colors.HexColor("#64748b"), spaceAfter=14,
    )
    estilo_seccion = ParagraphStyle(
        "SeccionPropia", parent=estilos["Heading2"],
        fontSize=12, textColor=colors.HexColor("#2563eb"), spaceBefore=14, spaceAfter=6,
    )
    estilo_nota = ParagraphStyle(
        "NotaPropia", parent=estilos["Normal"],
        fontSize=8, textColor=colors.HexColor("#64748b"), spaceBefore=4,
    )

    # "story" es la lista de elementos que ReportLab va colocando uno tras
    # otro, saltando de página automáticamente cuando hace falta.
    story = []

    story.append(Paragraph("Informe de gestión", estilo_titulo))
    story.append(Paragraph(
        f"{nombre_app} · Periodo del {desde.strftime('%d/%m/%Y')} "
        f"al {hasta.strftime('%d/%m/%Y')} · "
        f"Generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')}",
        estilo_sub,
    ))

    # --- Resumen económico -------------------------------------------------
    story.append(Paragraph("1. Resumen económico del periodo", estilo_seccion))
    story.append(_tabla(
        [
            ["Indicador", "Valor"],
            ["Ventas registradas", str(resumen["num_ventas"])],
            ["Unidades vendidas", str(resumen["unidades"])],
            ["Facturación total", euros(resumen["facturado"])],
            ["Coste de la mercancía vendida", euros(resumen["coste"])],
            ["Beneficio bruto", euros(resumen["beneficio"])],
            ["Margen medio", f"{resumen['margen']:.1f} %".replace(".", ",")],
            ["Ticket medio por venta", euros(resumen["ticket_medio"])],
            ["Valor del inventario (a coste)", euros(valor_inventario())],
        ],
        anchos=[10 * cm, 6.4 * cm],
        alineaciones=[1],
    ))

    # --- Productos más vendidos -------------------------------------------
    story.append(Paragraph("2. Productos más vendidos", estilo_seccion))
    filas = [["Referencia", "Producto", "Unidades", "Facturado"]]
    for f in productos_mas_vendidos(desde, hasta, 10):
        filas.append([
            f["producto"].referencia,
            f["producto"].nombre[:38],
            str(f["unidades"]),
            euros(f["facturado"]),
        ])
    story.append(_tabla(filas, [2.6 * cm, 7.8 * cm, 2.2 * cm, 3.8 * cm], [2, 3]))

    # --- Productos más rentables ------------------------------------------
    story.append(Paragraph("3. Productos más rentables", estilo_seccion))
    filas = [["Referencia", "Producto", "Unidades", "Beneficio"]]
    for f in productos_mas_rentables(desde, hasta, 10):
        filas.append([
            f["producto"].referencia,
            f["producto"].nombre[:38],
            str(f["unidades"]),
            euros(f["beneficio"]),
        ])
    story.append(_tabla(filas, [2.6 * cm, 7.8 * cm, 2.2 * cm, 3.8 * cm], [2, 3]))
    story.append(Paragraph(
        "Nota: los productos más vendidos no coinciden necesariamente con los más "
        "rentables. Un artículo barato puede venderse mucho y aportar poco beneficio.",
        estilo_nota,
    ))

    # --- Menor rotación ----------------------------------------------------
    story.append(Paragraph("4. Productos con menor rotación", estilo_seccion))
    filas = [["Referencia", "Producto", "Ud. vendidas", "Rotación", "Inmovilizado"]]
    for f in productos_menor_rotacion(desde, hasta, 10):
        filas.append([
            f["producto"].referencia,
            f["producto"].nombre[:32],
            str(f["unidades"]),
            f"{f['rotacion']:.2f}".replace(".", ","),
            euros(f["inmovilizado"]),
        ])
    story.append(_tabla(filas, [2.4 * cm, 6.2 * cm, 2.4 * cm, 2.2 * cm, 3.2 * cm], [2, 3, 4]))

    # --- Ventas por categoría ---------------------------------------------
    story.append(Paragraph("5. Ventas por categoría", estilo_seccion))
    filas = [["Categoría", "Unidades", "Facturación", "Beneficio"]]
    for f in ventas_por_categoria(desde, hasta):
        filas.append([
            f["categoria"], str(f["unidades"]), euros(f["facturado"]), euros(f["beneficio"]),
        ])
    story.append(_tabla(filas, [5.4 * cm, 2.4 * cm, 4.3 * cm, 4.3 * cm], [1, 2, 3]))

    # --- Alertas -----------------------------------------------------------
    story.append(Paragraph("6. Alertas: riesgo de rotura de stock", estilo_seccion))
    en_riesgo = productos_en_riesgo(desde, hasta)
    if en_riesgo:
        filas = [["Referencia", "Producto", "Stock", "Venta/día", "Días", "Situación"]]
        nombres = {"sin_stock": "Sin stock", "critico": "Crítico", "bajo": "Bajo mínimo"}
        for f in en_riesgo[:15]:
            dias = "—" if f["dias_restantes"] is None else f"{f['dias_restantes']:.0f}"
            filas.append([
                f["producto"].referencia,
                f["producto"].nombre[:30],
                str(f["producto"].stock_actual),
                f"{f['velocidad']:.2f}".replace(".", ","),
                dias,
                nombres.get(f["nivel"], f["nivel"]),
            ])
        story.append(_tabla(filas, [2.3 * cm, 5.6 * cm, 1.7 * cm, 2 * cm, 1.6 * cm, 3.2 * cm], [2, 3, 4]))
    else:
        story.append(Paragraph("No hay productos en riesgo de rotura de stock.", estilos["Normal"]))

    story.append(Paragraph("7. Alertas: productos con bajo margen", estilo_seccion))
    bajos = productos_bajo_margen()
    if bajos:
        filas = [["Referencia", "Producto", "Coste", "PVP", "Margen"]]
        for p in bajos:
            filas.append([
                p.referencia, p.nombre[:32],
                euros(p.coste_adquisicion), euros(p.precio_venta),
                f"{p.margen_porcentual:.1f} %".replace(".", ","),
            ])
        story.append(_tabla(filas, [2.4 * cm, 6.2 * cm, 2.8 * cm, 2.8 * cm, 2.2 * cm], [2, 3, 4]))
    else:
        story.append(Paragraph("Todos los productos superan el margen mínimo establecido.", estilos["Normal"]))

    story.append(Spacer(1, 0.8 * cm))
    story.append(Paragraph(
        f"Documento generado automáticamente por el sistema de gestión de {nombre_app}.",
        estilo_nota,
    ))

    documento.build(story)

    # Volvemos al principio del buffer para que Flask lea desde el byte 0.
    buffer.seek(0)
    nombre = f"informe_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

    return Response(
        buffer.getvalue(),
        mimetype="application/pdf",
        headers={"Content-Disposition": f"inline; filename={nombre}"},
    )
