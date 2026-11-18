import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

from .models import Ticket

logger = logging.getLogger(__name__)


def notificar_cambio_estado(ticket, estado_anterior):
    correo = (ticket.usuario.correo or '').strip()
    if not correo:
        logger.info('Ticket %s sin correo: no se notifica.', ticket.radicado)
        return

    ruta = reverse('helpdesk:seguimiento') + f'?radicado={ticket.radicado}'
    base = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
    enlace = f'{base}{ruta}' if base else ruta

    estado = ticket.get_estado_display()
    estado_previo = dict(Ticket.Estado.choices).get(estado_anterior, estado_anterior)

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
        f'Fecha: {timezone.localtime().strftime("%d/%m/%Y %H:%M")}',
        '',
        f'Consulte el detalle aquí: {enlace}',
        '',
        'Help Desk',
    ]

    try:
        send_mail(
            f'[{ticket.radicado}] Su solicitud ahora está {estado}',
            '\n'.join(lineas),
            settings.DEFAULT_FROM_EMAIL,
            [correo],
            using='default',
        )
    except Exception:
        logger.exception(
            'No se pudo enviar la notificación del ticket %s', ticket.radicado
        )
