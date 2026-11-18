import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .models import Ticket

logger = logging.getLogger(__name__)

_COLORES_ESTADO = {
    Ticket.Estado.EN_PROCESO: ('#9A4F00', '#FDEBD7'),
    Ticket.Estado.ATENDIDO: ('#4E7400', '#EFF7DA'),
    Ticket.Estado.ESCALADO: ('#0B6B5A', '#DFFFF5'),
    Ticket.Estado.FINALIZADO: ('#166079', '#DDF1F5'),
}
_COLOR_POR_DEFECTO = ('#9A4F00', '#FDEBD7')


def _enlace_seguimiento(ticket):
    ruta = reverse('helpdesk:seguimiento') + f'?radicado={ticket.radicado}'
    base = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
    return f'{base}{ruta}' if base else ruta


def _contexto_comun(ticket):
    return {
        'nombre': ticket.usuario.nombre,
        'radicado': ticket.radicado,
        'producto': ticket.producto_texto,
        'dependencia': ticket.dependencia_texto if ticket.dependencia else '',
        'fecha': timezone.localtime().strftime('%d/%m/%Y %H:%M'),
        'enlace': _enlace_seguimiento(ticket),
    }


def _color_estado(estado):
    return _COLORES_ESTADO.get(estado, _COLOR_POR_DEFECTO)


def _enviar(ticket, asunto, lineas, plantilla, contexto):
    correo = (ticket.usuario.correo or '').strip()
    if not correo:
        logger.info('Ticket %s sin correo: no se notifica.', ticket.radicado)
        return

    try:
        html = render_to_string(plantilla, contexto)
        mensaje = EmailMultiAlternatives(
            asunto,
            '\n'.join(lineas),
            settings.DEFAULT_FROM_EMAIL,
            [correo],
        )
        mensaje.attach_alternative(html, 'text/html')
        mensaje.send(using='default')
    except Exception:
        logger.exception(
            'No se pudo enviar la notificación del ticket %s', ticket.radicado
        )


def notificar_ticket_creado(ticket):
    estado = ticket.get_estado_display()
    color, fondo = _color_estado(ticket.estado)
    contexto = {
        **_contexto_comun(ticket),
        'estado': estado,
        'estado_color': color,
        'estado_fondo': fondo,
    }
    lineas = [
        f'Hola {ticket.usuario.nombre},',
        '',
        f'Su solicitud {ticket.radicado} ({ticket.producto_texto}) fue registrada correctamente.',
        f'Estado actual: {estado}',
        f'Fecha: {contexto["fecha"]}',
        '',
        f'Puede consultar el detalle aquí: {contexto["enlace"]}',
        '',
        'Help Desk',
    ]
    _enviar(
        ticket,
        f'[{ticket.radicado}] Su solicitud fue registrada',
        lineas,
        'helpdesk/emails/ticket_creado.html',
        contexto,
    )


def notificar_cambio_estado(ticket, estado_anterior):
    estado = ticket.get_estado_display()
    estado_previo = dict(Ticket.Estado.choices).get(estado_anterior, estado_anterior)
    color, fondo = _color_estado(ticket.estado)
    contexto = {
        **_contexto_comun(ticket),
        'estado': estado,
        'estado_previo': estado_previo,
        'estado_color': color,
        'estado_fondo': fondo,
    }

    lineas = [
        f'Hola {ticket.usuario.nombre},',
        '',
        f'Su solicitud {ticket.radicado} ({ticket.producto_texto}) cambió de estado.',
        f'Estado anterior: {estado_previo}',
        f'Nuevo estado: {estado}',
    ]
    if ticket.dependencia:
        lineas.append(f'Dependencia: {ticket.dependencia_texto}')
    lineas += [
        f'Fecha: {contexto["fecha"]}',
        '',
        f'Consulte el detalle aquí: {contexto["enlace"]}',
        '',
        'Help Desk',
    ]

    _enviar(
        ticket,
        f'[{ticket.radicado}] Su solicitud ahora está {estado}',
        lineas,
        'helpdesk/emails/cambio_estado.html',
        contexto,
    )
