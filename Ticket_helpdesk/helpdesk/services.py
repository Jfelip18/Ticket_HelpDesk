from django.contrib.auth.models import User
from django.db import connection, transaction
from django.utils import timezone

from .models import Ticket, Usuario
from .notificaciones import notificar_cambio_estado


class TransicionInvalida(Exception):
    pass


def _codigo_de_estado(estado):
    """'En proceso' -> 'EN_PROCESO' (para guardar el código en el historial)."""
    for codigo, etiqueta in Ticket.Estado.choices:
        if etiqueta.lower() == str(estado).strip().lower():
            return codigo
    return ''


def _registrar(ticket, estado, nota=''):
    momento = timezone.localtime()
    historial = list(ticket.historial or [])
    historial.append(
        {
            'estado': estado,
            'codigo': _codigo_de_estado(estado),
            'fecha': momento.isoformat(),
            'fecha_texto': momento.strftime('%d/%m/%Y %H:%M'),
            'nota': nota,
        }
    )
    ticket.historial = historial


def _obtener_ticket(ticket_id):
    queryset = Ticket.objects.all()
    if connection.features.has_select_for_update:
        queryset = queryset.select_for_update()
    return queryset.get(pk=ticket_id)


def obtener_perfil(cuenta):
    perfil = Usuario.objects.filter(cuenta=cuenta).first()
    if perfil is None:
        perfil = Usuario.objects.create(
            cuenta=cuenta,
            nombre=cuenta.first_name or cuenta.username,
            apellido=cuenta.last_name or '',
            direccion='',
            telefono=cuenta.username,
            tipo=Usuario.Tipo.CLIENTE,
        )
    return perfil


def es_administrador(cuenta):
    """El acceso al panel se decide únicamente por el rol del usuario."""
    if not cuenta or not cuenta.is_authenticated:
        return False
    return Usuario.objects.filter(cuenta=cuenta, tipo=Usuario.Tipo.ADMIN).exists()


@transaction.atomic
def registrar_cliente(nombre, apellido, direccion, telefono, usuario, contrasena, correo=''):
    cuenta = User.objects.create_user(
        username=usuario,
        password=contrasena,
        first_name=(nombre or '').strip(),
        last_name=(apellido or '').strip(),
        email=(correo or '').strip(),
        is_active=True,
        is_staff=False,
        is_superuser=False,
    )
    perfil = Usuario.objects.create(
        cuenta=cuenta,
        nombre=(nombre or '').strip(),
        apellido=(apellido or '').strip(),
        direccion=(direccion or '').strip(),
        telefono=(telefono or '').strip(),
        correo=(correo or '').strip(),
        tipo=Usuario.Tipo.CLIENTE,
    )
    return cuenta, perfil


@transaction.atomic
def crear_ticket(usuario, producto, descripcion, producto_otro=''):
    producto_otro = (producto_otro or '').strip()
    if producto != Ticket.Producto.OTRO:
        producto_otro = ''

    ticket = Ticket.objects.create(
        usuario=usuario,
        producto=producto,
        producto_otro=producto_otro,
        descripcion=(descripcion or '').strip(),
        estado=Ticket.Estado.EN_PROCESO,
    )
    ticket.radicado = f'HD-{timezone.localtime().year}-{ticket.pk:06d}'
    _registrar(ticket, Ticket.Estado.EN_PROCESO.label, 'Ticket creado por el cliente')
    ticket.save(update_fields=['radicado', 'historial'])
    return ticket


@transaction.atomic
def tomar_ticket(ticket_id):
    ticket = _obtener_ticket(ticket_id)
    if ticket.estado != Ticket.Estado.EN_PROCESO:
        raise TransicionInvalida(
            f'El ticket {ticket.radicado} no está en proceso, ya fue tomado por otro administrador.'
        )
    estado_anterior = ticket.estado
    ticket.estado = Ticket.Estado.ATENDIDO
    ticket.atendido_en = timezone.now()
    _registrar(ticket, Ticket.Estado.ATENDIDO.label, 'Ticket tomado por el administrador')
    ticket.save(update_fields=['estado', 'atendido_en', 'historial', 'actualizado_en'])
    transaction.on_commit(
        lambda: notificar_cambio_estado(ticket, estado_anterior)
    )
    return ticket


@transaction.atomic
def finalizar_ticket(ticket_id):
    ticket = _obtener_ticket(ticket_id)
    if ticket.estado not in (Ticket.Estado.ATENDIDO, Ticket.Estado.ESCALADO):
        raise TransicionInvalida(
            f'El ticket {ticket.radicado} aún no ha sido tomado, no se puede finalizar.'
        )
    nota = (
        'Finalizado por la dependencia superior'
        if ticket.estado == Ticket.Estado.ESCALADO
        else 'Finalizado por el administrador'
    )
    estado_anterior = ticket.estado
    ticket.estado = Ticket.Estado.FINALIZADO
    ticket.finalizado_en = timezone.now()
    _registrar(ticket, Ticket.Estado.FINALIZADO.label, nota)
    ticket.save(update_fields=['estado', 'finalizado_en', 'historial', 'actualizado_en'])
    transaction.on_commit(
        lambda: notificar_cambio_estado(ticket, estado_anterior)
    )
    return ticket


@transaction.atomic
def escalar_ticket(ticket_id, dependencia):
    ticket = _obtener_ticket(ticket_id)
    if ticket.estado != Ticket.Estado.ATENDIDO:
        raise TransicionInvalida(
            f'El ticket {ticket.radicado} no puede escalarse en su estado actual.'
        )
    dependencia = (dependencia or '').strip()
    if dependencia not in Ticket.Dependencia.values:
        raise TransicionInvalida('Seleccione una dependencia válida.')
    etiqueta = Ticket.Dependencia(dependencia).label
    ticket.estado = Ticket.Estado.ESCALADO
    ticket.dependencia = dependencia
    estado_anterior = Ticket.Estado.ATENDIDO
    _registrar(ticket, Ticket.Estado.ESCALADO.label, f'Escalado a {etiqueta}')
    ticket.save(update_fields=['estado', 'dependencia', 'historial', 'actualizado_en'])
    transaction.on_commit(
        lambda: notificar_cambio_estado(ticket, estado_anterior)
    )
    return ticket
