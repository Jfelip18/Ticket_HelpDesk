import csv
from functools import wraps

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.db import IntegrityError
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .config import LONGITUD_DESCRIPCION
from .exportes import reporte_excel_bytes
from .forms import (
    AccesoForm,
    EscalarForm,
    PerfilForm,
    RegistroForm,
    SeguimientoForm,
    TicketForm,
    normalizar_telefono,
)
from .models import Ticket, Usuario
from .services import (
    TransicionInvalida,
    crear_ticket,
    escalar_ticket,
    es_administrador,
    finalizar_ticket,
    obtener_perfil,
    registrar_cliente,
    tomar_ticket,
)

IMAGENES_PRODUCTO = {
    Ticket.Producto.VIDEOBEAM: 'videobeam.svg',
    Ticket.Producto.TV: 'tv.svg',
    Ticket.Producto.CABLE_HDMI: 'cables-hdmi.svg',
    Ticket.Producto.AIRE_ACONDICIONADO: 'aire-acondicionado.svg',
    Ticket.Producto.OTRO: 'otro.svg',
}

SECCIONES = {    'proceso': {
        'titulo': 'En proceso',
        'estado': Ticket.Estado.EN_PROCESO,
        'url': 'helpdesk:panel_en_proceso',
    },
    'atendidos': {
        'titulo': 'Atendidos',
        'estado': Ticket.Estado.ATENDIDO,
        'url': 'helpdesk:panel_atendidos',
    },
    'dependencia': {
        'titulo': 'Otra dependencia',
        'estado': Ticket.Estado.ESCALADO,
        'url': 'helpdesk:panel_otra_dependencia',
    },
    'finalizados': {
        'titulo': 'Finalizados',
        'estado': Ticket.Estado.FINALIZADO,
        'url': 'helpdesk:panel_finalizados',
    },
}


class AccesoView(LoginView):
    template_name = 'helpdesk/ingresar.html'
    authentication_form = AccesoForm
    redirect_authenticated_user = True

    def get_success_url(self):
        if es_administrador(self.request.user):
            return reverse('helpdesk:panel_dashboard')
        return reverse('helpdesk:inicio')


def admin_required(view_func):
    """Solo los usuarios con rol ADMIN (helpdesk_usuario.tipo) entran al panel."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('helpdesk:ingresar')}?next={request.get_full_path()}")
        if not es_administrador(request.user):
            messages.error(request, 'Su usuario no tiene permisos para acceder al panel.')
            return redirect('helpdesk:inicio')
        return view_func(request, *args, **kwargs)

    return _wrapped


def _destino_seguro(request):
    destino = request.POST.get('next') or ''
    if not url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return reverse('helpdesk:panel_dashboard')
    return destino


def _contexto_panel(request):
    conteos = {
        config['estado']: Ticket.objects.filter(estado=config['estado']).count()
        for config in SECCIONES.values()
    }
    return {
        'es_panel': True,
        'total_tickets': Ticket.objects.count(),
        'conteo_proceso': conteos[Ticket.Estado.EN_PROCESO],
        'conteo_atendidos': conteos[Ticket.Estado.ATENDIDO],
        'conteo_dependencia': conteos[Ticket.Estado.ESCALADO],
        'conteo_finalizados': conteos[Ticket.Estado.FINALIZADO],
        'productos': Ticket.Producto.choices,
        'estados': Ticket.Estado.choices,
    }


def _filtrar_tickets(queryset, params):
    busqueda = (params.get('q') or '').strip()
    if busqueda:
        consulta = (
            Q(radicado__icontains=busqueda)
            | Q(usuario__nombre__icontains=busqueda)
            | Q(usuario__apellido__icontains=busqueda)
            | Q(usuario__telefono__icontains=busqueda)
            | Q(usuario__direccion__icontains=busqueda)
        )
        digitos = normalizar_telefono(busqueda)
        if digitos and digitos != busqueda:
            consulta |= Q(usuario__telefono__icontains=digitos)
        queryset = queryset.filter(consulta)
    producto = (params.get('producto') or '').strip()
    if producto in Ticket.Producto.values:
        queryset = queryset.filter(producto=producto)
    fecha_desde = (params.get('fecha_desde') or '').strip()
    if fecha_desde:
        queryset = queryset.filter(creado_en__date__gte=fecha_desde)
    fecha_hasta = (params.get('fecha_hasta') or '').strip()
    if fecha_hasta:
        queryset = queryset.filter(creado_en__date__lte=fecha_hasta)
    estado = (params.get('estado') or '').strip()
    if estado in Ticket.Estado.values:
        queryset = queryset.filter(estado=estado)
    return queryset


def registro(request):
    if request.user.is_authenticated:
        return redirect('helpdesk:inicio')
    form = RegistroForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        datos = form.cleaned_data
        try:
            cuenta, perfil = registrar_cliente(
                nombre=datos['nombre'],
                apellido=datos['apellido'],
                direccion=datos['direccion'],
                telefono=datos['telefono'],
                usuario=datos['usuario'],
                contrasena=datos['contrasena'],
                correo=datos['correo'],
            )
        except IntegrityError:
            messages.error(request, 'El usuario o el teléfono ya están registrados.')
            return redirect('helpdesk:registro')
        login(request, cuenta, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, f'Bienvenido {perfil.nombre}, su cuenta fue creada.')
        return redirect('helpdesk:inicio')
    return render(request, 'helpdesk/registro.html', {'form': form})


def panel_login(request):
    if es_administrador(request.user):
        return redirect('helpdesk:panel_dashboard')
    destino = reverse('helpdesk:panel_dashboard')
    return redirect(f"{reverse('helpdesk:ingresar')}?next={destino}")


def inicio(request):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('helpdesk:ingresar')}?next={reverse('helpdesk:inicio')}")
    if es_administrador(request.user):
        return redirect('helpdesk:panel_dashboard')

    perfil = obtener_perfil(request.user)
    tickets = Ticket.objects.filter(usuario=perfil)
    form = PerfilForm(instance=perfil, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Sus datos fueron actualizados.')
        return redirect('helpdesk:inicio')

    context = {
        'perfil': perfil,
        'form': form,
        'tickets': tickets,
        'total_tickets': tickets.count(),
        'opciones': [
            (valor, etiqueta, IMAGENES_PRODUCTO[valor])
            for valor, etiqueta in Ticket.Producto.choices
        ],
        'longitud_descripcion': LONGITUD_DESCRIPCION,
    }
    return render(request, 'helpdesk/inicio.html', context)


def solicitar(request):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('helpdesk:ingresar')}?next={reverse('helpdesk:solicitar')}")
    if es_administrador(request.user):
        return redirect('helpdesk:panel_dashboard')
    perfil = obtener_perfil(request.user)
    producto_pedido = request.GET.get('producto', '')
    if producto_pedido not in Ticket.Producto.values:
        producto_pedido = ''
    form = TicketForm(request.POST or None, initial={'producto': producto_pedido})
    if request.method == 'POST' and form.is_valid():
        ticket = crear_ticket(usuario=perfil, **form.cleaned_data)
        return redirect('helpdesk:solicitud_creada', radicado=ticket.radicado)
    return render(request, 'helpdesk/solicitar.html', {'form': form, 'perfil': perfil})


def solicitud_creada(request, radicado):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('helpdesk:ingresar')}?next={reverse('helpdesk:solicitud_creada', kwargs={'radicado': radicado})}")
    if es_administrador(request.user):
        return redirect('helpdesk:panel_dashboard')
    perfil = obtener_perfil(request.user)
    ticket = get_object_or_404(
        Ticket.objects.select_related('usuario'), radicado=radicado, usuario=perfil
    )
    return render(request, 'helpdesk/solicitud_creada.html', {'ticket': ticket})


def seguimiento(request):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('helpdesk:ingresar')}?next={reverse('helpdesk:seguimiento')}")
    if es_administrador(request.user):
        return redirect('helpdesk:panel_dashboard')
    perfil = obtener_perfil(request.user)
    tickets = Ticket.objects.filter(usuario=perfil)
    form = SeguimientoForm(request.GET or None)
    ticket = None
    if request.GET.get('radicado'):
        if form.is_valid():
            ticket = tickets.filter(radicado=form.cleaned_data['radicado']).first()
            if ticket is None:
                messages.error(request, 'No encontramos ningún ticket con ese radicado.')
    return render(
        request,
        'helpdesk/seguimiento.html',
        {'form': form, 'ticket': ticket, 'tickets': tickets},
    )


@admin_required
def panel_dashboard(request):
    context = _contexto_panel(request)
    context['recientes'] = Ticket.objects.select_related('usuario')[:10]
    return render(request, 'helpdesk/panel/dashboard.html', context)


@admin_required
def panel_seccion(request, seccion):
    config = SECCIONES.get(seccion)
    if config is None:
        raise Http404('Sección no encontrada')
    tickets = _filtrar_tickets(
        Ticket.objects.select_related('usuario').filter(estado=config['estado']),
        request.GET,
    )
    context = _contexto_panel(request)
    context.update(
        {
            'seccion': seccion,
            'titulo': config['titulo'],
            'tickets': tickets,
            'filtros': request.GET,
            'url_limpiar': reverse(config['url']),
        }
    )
    return render(request, 'helpdesk/panel/lista.html', context)


@admin_required
def panel_usuarios(request):
    usuarios = Usuario.objects.annotate(total_tickets=Count('tickets'))
    busqueda = (request.GET.get('q') or '').strip()
    if busqueda:
        consulta = (
            Q(nombre__icontains=busqueda)
            | Q(apellido__icontains=busqueda)
            | Q(telefono__icontains=busqueda)
            | Q(direccion__icontains=busqueda)
        )
        digitos = normalizar_telefono(busqueda)
        if digitos and digitos != busqueda:
            consulta |= Q(telefono__icontains=digitos)
        usuarios = usuarios.filter(consulta)
    tipo = (request.GET.get('tipo') or '').strip()
    if tipo in Usuario.Tipo.values:
        usuarios = usuarios.filter(tipo=tipo)
    context = _contexto_panel(request)
    context.update(
        {
            'usuarios': usuarios.order_by('-creado_en'),
            'filtros': request.GET,
            'tipos': Usuario.Tipo.choices,
        }
    )
    return render(request, 'helpdesk/panel/usuarios.html', context)


@admin_required
def panel_ticket_detalle(request, pk):
    ticket = get_object_or_404(Ticket.objects.select_related('usuario'), pk=pk)
    context = _contexto_panel(request)
    context['ticket'] = ticket
    return render(request, 'helpdesk/panel/ticket_detalle.html', context)


@admin_required
@require_POST
def panel_ticket_atender(request, pk):
    try:
        ticket = tomar_ticket(pk)
        messages.success(request, f'Ticket {ticket.radicado} tomado. Estado: Atendido.')
    except TransicionInvalida as exc:
        messages.error(request, str(exc))
    return redirect(_destino_seguro(request))


@admin_required
@require_POST
def panel_ticket_finalizar(request, pk):
    try:
        ticket = finalizar_ticket(pk)
        messages.success(request, f'Ticket {ticket.radicado} finalizado.')
    except TransicionInvalida as exc:
        messages.error(request, str(exc))
    return redirect(_destino_seguro(request))


@admin_required
def panel_ticket_escalar(request, pk):
    ticket = get_object_or_404(Ticket.objects.select_related('usuario'), pk=pk)
    if ticket.estado != Ticket.Estado.ATENDIDO:
        messages.error(request, 'Este ticket no se puede escalar en su estado actual.')
        return redirect('helpdesk:panel_atendidos')

    form = EscalarForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            try:
                ticket = escalar_ticket(pk, form.cleaned_data['dependencia'])
                messages.success(
                    request,
                    f'Ticket {ticket.radicado} escalado a {ticket.dependencia_texto}.',
                )
                return redirect('helpdesk:panel_otra_dependencia')
            except TransicionInvalida as exc:
                messages.error(request, str(exc))
                return redirect('helpdesk:panel_atendidos')
        messages.error(request, 'Seleccione una dependencia válida.')

    context = _contexto_panel(request)
    context['ticket'] = ticket
    context['form'] = form
    return render(request, 'helpdesk/panel/escalar.html', context)


@admin_required
def panel_reportes(request):
    tickets = _filtrar_tickets(Ticket.objects.select_related('usuario'), request.GET)
    context = _contexto_panel(request)
    context.update(
        {
            'tickets': tickets[:200],
            'total_resultados': tickets.count(),
            'por_estado': [
                {'estado': etiqueta, 'total': Ticket.objects.filter(estado=valor).count()}
                for valor, etiqueta in Ticket.Estado.choices
            ],
            'por_producto': [
                {'producto': etiqueta, 'total': Ticket.objects.filter(producto=valor).count()}
                for valor, etiqueta in Ticket.Producto.choices
            ],
            'filtros': request.GET,
        }
    )
    return render(request, 'helpdesk/panel/reportes.html', context)


@admin_required
def panel_reportes_excel(request):
    tickets = _filtrar_tickets(
        Ticket.objects.select_related('usuario'), request.GET
    ).order_by('-creado_en')
    fecha = timezone.localtime().strftime('%Y%m%d')
    respuesta = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    respuesta['Content-Disposition'] = f'attachment; filename="reporte_tickets_{fecha}.xlsx"'
    respuesta.write(reporte_excel_bytes(tickets))
    return respuesta


@admin_required
def panel_reportes_csv(request):
    tickets = _filtrar_tickets(
        Ticket.objects.select_related('usuario'), request.GET
    ).order_by('-creado_en')
    respuesta = HttpResponse(content_type='text/csv; charset=utf-8')
    fecha = timezone.localtime().strftime('%Y%m%d')
    respuesta['Content-Disposition'] = f'attachment; filename="reporte_tickets_{fecha}.csv"'
    respuesta.write('\ufeff')
    escritor = csv.writer(respuesta)
    escritor.writerow(
        [
            'Radicado',
            'Fecha creacion',
            'Nombre',
            'Apellido',
            'Direccion del cliente',
            'Telefono',
            'Producto',
            'Descripcion',
            'Estado',
            'Dependencia',
            'Fecha atendido',
            'Fecha finalizado',
        ]
    )
    for ticket in tickets:
        escritor.writerow(
            [
                ticket.radicado,
                timezone.localtime(ticket.creado_en).strftime('%Y-%m-%d %H:%M'),
                ticket.usuario.nombre,
                ticket.usuario.apellido,
                ticket.usuario.direccion,
                ticket.usuario.telefono_formateado,
                ticket.producto_texto,
                ticket.descripcion,
                ticket.get_estado_display(),
                ticket.dependencia_texto,
                timezone.localtime(ticket.atendido_en).strftime('%Y-%m-%d %H:%M')
                if ticket.atendido_en
                else '',
                timezone.localtime(ticket.finalizado_en).strftime('%Y-%m-%d %H:%M')
                if ticket.finalizado_en
                else '',
            ]
        )
    return respuesta
