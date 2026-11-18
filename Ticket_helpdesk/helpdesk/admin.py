from django.contrib import admin

from .models import Ticket, Usuario


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ('nombre_completo', 'tipo', 'telefono_formateado', 'correo', 'direccion', 'cuenta', 'creado_en')
    list_filter = ('tipo', 'creado_en')
    search_fields = ('nombre', 'apellido', 'telefono', 'correo', 'direccion', 'cuenta__username')
    ordering = ('-creado_en',)
    fieldsets = (
        (None, {'fields': ('cuenta', 'nombre', 'apellido', 'direccion', 'telefono', 'correo', 'tipo')}),
        ('Auditoría', {'fields': ('creado_en', 'actualizado_en')}),
    )


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        'radicado',
        'usuario',
        'producto_texto',
        'estado',
        'dependencia',
        'creado_en',
    )
    list_filter = ('estado', 'producto', 'dependencia', 'creado_en')
    search_fields = (
        'radicado',
        'usuario__nombre',
        'usuario__apellido',
        'usuario__telefono',
        'usuario__direccion',
        'dependencia',
    )
    readonly_fields = (
        'radicado',
        'historial',
        'creado_en',
        'actualizado_en',
        'atendido_en',
        'finalizado_en',
    )
    ordering = ('-creado_en',)
    fieldsets = (
        (None, {'fields': ('radicado', 'estado', 'dependencia')}),
        ('Usuario', {'fields': ('usuario',)}),
        ('Solicitud', {'fields': ('producto', 'producto_otro', 'descripcion')}),
        ('Seguimiento', {'fields': ('atendido_en', 'finalizado_en', 'historial')}),
        ('Auditoría', {'fields': ('creado_en', 'actualizado_en')}),
    )
