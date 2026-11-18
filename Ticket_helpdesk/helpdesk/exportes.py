"""Generación del reporte de tickets en Excel (.xlsx)."""

from datetime import datetime
from io import BytesIO

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

COLOR_ENCABEZADO = '1D4ED8'
COLOR_BORDE = 'D8DEE9'
FORMATO_FECHA = 'DD/MM/YYYY HH:MM'

COLUMNAS = [
    ('Radicado', 16),
    ('Fecha creación', 20),
    ('Nombre', 18),
    ('Apellido', 20),
    ('Dirección del cliente', 32),
    ('Teléfono', 16),
    ('Producto', 18),
    ('Descripción del problema', 48),
    ('Estado', 24),
    ('Dependencia', 24),
    ('Atendido', 20),
    ('Finalizado', 20),
]


def _valor_para_excel(valor):
    """Excel no admite fechas con zona horaria: se pasan a hora local sin tz."""
    if isinstance(valor, datetime) and timezone.is_aware(valor):
        return timezone.localtime(valor).replace(tzinfo=None)
    return valor


def construir_reporte_excel(tickets):
    libro = Workbook()
    hoja = libro.active
    hoja.title = 'Tickets'

    encabezado = Font(bold=True, color='FFFFFF', size=11)
    relleno = PatternFill('solid', fgColor=COLOR_ENCABEZADO)
    centrado = Alignment(horizontal='center', vertical='center')
    borde = Border(*[Side(style='thin', color=COLOR_BORDE)] * 4)

    for indice, (titulo, ancho) in enumerate(COLUMNAS, start=1):
        celda = hoja.cell(row=1, column=indice, value=titulo)
        celda.font = encabezado
        celda.fill = relleno
        celda.alignment = centrado
        celda.border = borde
        hoja.column_dimensions[get_column_letter(indice)].width = ancho

    fila = 2
    for ticket in tickets:
        valores = [
            ticket.radicado,
            ticket.creado_en,
            ticket.usuario.nombre,
            ticket.usuario.apellido,
            ticket.usuario.direccion,
            ticket.usuario.telefono_formateado,
            ticket.producto_texto,
            ticket.descripcion,
            ticket.get_estado_display(),
            ticket.dependencia,
            ticket.atendido_en,
            ticket.finalizado_en,
        ]
        for indice, valor in enumerate(valores, start=1):
            valor = _valor_para_excel(valor)
            celda = hoja.cell(row=fila, column=indice, value=valor)
            celda.border = borde
            if isinstance(valor, datetime):
                celda.number_format = FORMATO_FECHA
                celda.alignment = Alignment(horizontal='center')
        hoja.cell(row=fila, column=8).alignment = Alignment(wrap_text=True, vertical='top')
        fila += 1

    hoja.freeze_panes = 'A2'
    hoja.auto_filter.ref = f'A1:{get_column_letter(len(COLUMNAS))}{max(fila - 1, 1)}'
    return libro


def reporte_excel_bytes(tickets):
    """Devuelve el archivo .xlsx como bytes."""
    archivo = BytesIO()
    construir_reporte_excel(tickets).save(archivo)
    archivo.seek(0)
    return archivo.getvalue()
