from django.urls import path

from . import views

app_name = 'helpdesk'

urlpatterns = [
    # Acceso de los clientes
    path('ingresar/', views.AccesoView.as_view(), name='ingresar'),
    path('registro/', views.registro, name='registro'),
    path('salir/', views.LogoutView.as_view(), name='salir'),
    # Área del cliente (con sesión iniciada)
    path('', views.inicio, name='inicio'),
    path('solicitar/', views.solicitar, name='solicitar'),
    path('solicitud/<str:radicado>/', views.solicitud_creada, name='solicitud_creada'),
    path('seguimiento/', views.seguimiento, name='seguimiento'),
    # Panel del administrador
    path('panel/login/', views.panel_login, name='panel_login'),
    path('panel/', views.panel_dashboard, name='panel_dashboard'),
    path(
        'panel/en-proceso/',
        views.panel_seccion,
        {'seccion': 'proceso'},
        name='panel_en_proceso',
    ),
    path(
        'panel/atendidos/',
        views.panel_seccion,
        {'seccion': 'atendidos'},
        name='panel_atendidos',
    ),
    path(
        'panel/otra-dependencia/',
        views.panel_seccion,
        {'seccion': 'dependencia'},
        name='panel_otra_dependencia',
    ),
    path(
        'panel/finalizados/',
        views.panel_seccion,
        {'seccion': 'finalizados'},
        name='panel_finalizados',
    ),
    path('panel/reportes/', views.panel_reportes, name='panel_reportes'),
    path('panel/reportes/excel/', views.panel_reportes_excel, name='panel_reportes_excel'),
    path('panel/reportes/csv/', views.panel_reportes_csv, name='panel_reportes_csv'),
    path('panel/usuarios/', views.panel_usuarios, name='panel_usuarios'),
    path('panel/ticket/<int:pk>/', views.panel_ticket_detalle, name='panel_ticket_detalle'),
    path(
        'panel/ticket/<int:pk>/atender/',
        views.panel_ticket_atender,
        name='panel_ticket_atender',
    ),
    path(
        'panel/ticket/<int:pk>/finalizar/',
        views.panel_ticket_finalizar,
        name='panel_ticket_finalizar',
    ),
    path(
        'panel/ticket/<int:pk>/escalar/',
        views.panel_ticket_escalar,
        name='panel_ticket_escalar',
    ),
]
