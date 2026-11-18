from io import BytesIO

from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from .models import Ticket, Usuario
from .services import (
    TransicionInvalida,
    crear_ticket,
    escalar_ticket,
    finalizar_ticket,
    registrar_cliente,
    tomar_ticket,
)

DATOS_REGISTRO = {
    'nombre': 'Ana',
    'apellido': 'Ramírez',
    'direccion': 'Calle 10 # 20-30',
    'telefono': '3001234567',
    'correo': 'ana@example.com',
    'usuario': 'ana',
    'contrasena': 'ClaveSegura#2026',
    'repetir_contrasena': 'ClaveSegura#2026',
    'terminos': 'on',
    'datos_personales': 'on',
}

DATOS_SOLICITUD = {
    'producto': Ticket.Producto.VIDEOBEAM,
    'descripcion': 'No enciende y no muestra señal.',
    'producto_otro': '',
}


def crear_cliente(**cambios):
    datos = {**DATOS_REGISTRO, **cambios}
    return registrar_cliente(
        datos['nombre'],
        datos['apellido'],
        datos['direccion'],
        datos['telefono'],
        datos['usuario'],
        datos['contrasena'],
        correo=datos['correo'],
    )


def crear_ticket_de_prueba(perfil):
    return crear_ticket(usuario=perfil, **DATOS_SOLICITUD)


CAMPOS_CLIENTE = ('nombre', 'apellido', 'direccion', 'telefono', 'correo')
CAMPOS_CUENTA = (
    'usuario',
    'contrasena',
    'repetir_contrasena',
    'terminos',
    'datos_personales',
)


def registrarse(cliente, **cambios):
    """Completa los dos pasos del registro y devuelve la respuesta final."""
    datos = {**DATOS_REGISTRO, **cambios}
    cliente.post(
        reverse('helpdesk:registro'),
        {campo: datos[campo] for campo in CAMPOS_CLIENTE},
    )
    return cliente.post(
        reverse('helpdesk:registro_cuenta'),
        {campo: datos[campo] for campo in CAMPOS_CUENTA},
    )


class RegistroClienteTests(TestCase):
    def test_la_pagina_de_registro_se_abre(self):
        respuesta = self.client.get(reverse('helpdesk:registro'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Registro de usuario')
        self.assertContains(respuesta, 'Correo electrónico *')
        self.assertNotContains(respuesta, 'Repetir contraseña')

    def test_la_cuenta_se_pide_en_un_paso_posterior(self):
        respuesta = self.client.post(
            reverse('helpdesk:registro'),
            {campo: DATOS_REGISTRO[campo] for campo in CAMPOS_CLIENTE},
        )

        self.assertRedirects(respuesta, reverse('helpdesk:registro_cuenta'))
        respuesta = self.client.get(reverse('helpdesk:registro_cuenta'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Cuenta de acceso')
        self.assertContains(respuesta, 'Repetir contraseña *')
        self.assertContains(respuesta, 'Acepto los términos y condiciones')
        self.assertContains(respuesta, 'Autorizo el tratamiento de mis datos personales')
        self.assertContains(respuesta, 'Retrato de estudiante')

    def test_la_cuenta_no_se_puede_crear_sin_los_datos_previos(self):
        respuesta = self.client.get(reverse('helpdesk:registro_cuenta'))

        self.assertRedirects(respuesta, reverse('helpdesk:registro'))
        self.assertFalse(Usuario.objects.exists())

    def test_el_registro_crea_la_cuenta_y_la_ficha_del_cliente(self):
        respuesta = registrarse(self.client)

        self.assertEqual(respuesta.status_code, 302)
        self.assertRedirects(respuesta, reverse('helpdesk:inicio'))
        perfil = Usuario.objects.get()
        self.assertEqual(perfil.nombre_completo, 'Ana Ramírez')
        self.assertEqual(perfil.tipo, Usuario.Tipo.CLIENTE)
        self.assertEqual(perfil.correo, 'ana@example.com')
        self.assertEqual(perfil.cuenta.email, 'ana@example.com')
        self.assertTrue(perfil.cuenta.is_active)
        self.assertFalse(perfil.cuenta.is_staff)

    def test_el_cliente_queda_iniciando_sesion_al_registrarse(self):
        registrarse(self.client)

        respuesta = self.client.get(reverse('helpdesk:inicio'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Ana')

    def test_la_portada_muestra_el_banner_en_la_derecha(self):
        crear_cliente()
        self.client.login(username='ana', password='ClaveSegura#2026')

        html = self.client.get(reverse('helpdesk:inicio')).content.decode()

        self.assertIn('portada-imagen', html)
        self.assertIn('/img/img.', html)

    def test_el_telefono_se_guarda_solo_con_digitos_y_se_muestra_formateado(self):
        registrarse(self.client, telefono='324 344 1263')

        perfil = Usuario.objects.get()
        self.assertEqual(perfil.telefono, '3243441263')
        self.assertEqual(perfil.telefono_formateado, '324 344 1263')

    def test_no_se_puede_registrar_un_telefono_ya_existente(self):
        crear_cliente()

        respuesta = self.client.post(
            reverse('helpdesk:registro'),
            {campo: DATOS_REGISTRO[campo] for campo in CAMPOS_CLIENTE},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Usuario.objects.count(), 1)
        self.assertContains(respuesta, 'Ya existe una cuenta registrada con ese número de teléfono')

    def test_no_se_puede_registrar_un_usuario_ya_existente(self):
        crear_cliente()

        respuesta = registrarse(
            self.client,
            telefono='3011112222',
            correo='otra@example.com',
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Usuario.objects.count(), 1)
        self.assertContains(respuesta, 'Ese nombre de usuario ya está en uso.')

    def test_las_contrasenas_deben_coincidir(self):
        respuesta = registrarse(self.client, repetir_contrasena='OtraClave#2026')

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Usuario.objects.exists())
        self.assertContains(respuesta, 'Las contraseñas no coinciden.')

    def test_debe_aceptar_los_terminos_y_autorizar_los_datos(self):
        self.client.post(
            reverse('helpdesk:registro'),
            {campo: DATOS_REGISTRO[campo] for campo in CAMPOS_CLIENTE},
        )

        respuesta = self.client.post(
            reverse('helpdesk:registro_cuenta'),
            {
                'usuario': DATOS_REGISTRO['usuario'],
                'contrasena': DATOS_REGISTRO['contrasena'],
                'repetir_contrasena': DATOS_REGISTRO['repetir_contrasena'],
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Usuario.objects.exists())
        self.assertContains(respuesta, 'Debe aceptar los términos y condiciones.')
        self.assertContains(
            respuesta, 'Debe autorizar el tratamiento de sus datos personales.'
        )


class CrearAdminCommandTests(TestCase):
    def test_el_sql_generado_no_trae_saltos_de_linea_en_el_hash(self):
        import re
        from io import StringIO

        from django.core.management import call_command

        salida = StringIO()
        call_command('crear_admin', '--password', 'ClaveAdmin#2026', stdout=salida)

        sql = salida.getvalue()
        valores = re.findall(r"'([^'\n]*)'", sql)
        self.assertTrue(valores, 'el comando debe imprimir el SQL')
        hash_ = valores[0]
        self.assertIn('$', hash_)
        self.assertNotIn('\n', hash_)
        self.assertNotIn('\r', hash_)
        self.assertNotIn(' ', hash_)

    def test_el_ingreso_muestra_el_error_real(self):
        respuesta = self.client.post(
            reverse('helpdesk:ingresar'), {'username': 'nadie', 'password': 'malaclave'}
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Usuario o contraseña incorrectos.')


class AccesoClienteTests(TestCase):
    def test_el_ingreso_muestra_el_aviso_de_carga(self):
        respuesta = self.client.get(reverse('helpdesk:ingresar'))

        contenido = respuesta.content.decode()
        self.assertContains(respuesta, 'data-cargando')
        self.assertIn('cargando-overlay', contenido)
        self.assertIn('circulo-carga', contenido)

    def test_el_registro_muestra_el_aviso_de_carga(self):
        respuesta = self.client.get(reverse('helpdesk:registro'))

        self.assertContains(respuesta, 'data-cargando')

    def test_la_portada_pide_iniciar_sesion(self):
        respuesta = self.client.get(reverse('helpdesk:inicio'))

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('helpdesk:ingresar'), respuesta.url)

    def test_solicitar_y_seguimiento_exigen_sesion(self):
        for nombre in ('helpdesk:solicitar', 'helpdesk:seguimiento'):
            respuesta = self.client.get(reverse(nombre))
            self.assertEqual(respuesta.status_code, 302)
            self.assertIn(reverse('helpdesk:ingresar'), respuesta.url)

    def test_el_cliente_no_ve_el_boton_inicio_en_el_menu(self):
        crear_cliente()
        self.client.login(username='ana', password='ClaveSegura#2026')

        html = self.client.get(reverse('helpdesk:inicio')).content.decode()

        self.assertNotIn('>Inicio<', html)
        self.assertIn('menu-usuario-icono', html)
        self.assertIn('Ver mis tickets', html)
        self.assertIn('Registrar solicitud', html)
        self.assertIn('Cerrar sesión', html)
        self.assertNotIn('>Salir<', html)

        inicio_nav = html.index('<nav class="nav-principal">')
        fin_nav = html.index('</nav>', inicio_nav)
        self.assertNotIn('Mis tickets', html[inicio_nav:fin_nav])
        self.assertNotIn('Registrar solicitud', html[inicio_nav:fin_nav])

        inicio_menu = html.index('<details class="menu-usuario">')
        fin_menu = html.index('</details>', inicio_menu)
        menu = html[inicio_menu:fin_menu]
        self.assertIn('Actualizar datos', menu)
        self.assertNotIn('Registrar solicitud', menu)

    def test_el_menu_no_muestra_opciones_de_acceso_a_los_visitantes(self):
        respuesta = self.client.get(reverse('helpdesk:ingresar'))

        contenido = respuesta.content.decode()
        inicio_nav = contenido.index('<nav class="nav-principal">')
        fin_nav = contenido.index('</nav>', inicio_nav)

        self.assertNotIn('href', contenido[inicio_nav:fin_nav])

    def test_ingreso_correcto(self):
        crear_cliente()

        respuesta = self.client.post(
            reverse('helpdesk:ingresar'),
            {'username': 'ana', 'password': 'ClaveSegura#2026'},
        )

        self.assertRedirects(respuesta, reverse('helpdesk:inicio'))

    def test_ingreso_incorrecto(self):
        crear_cliente()

        respuesta = self.client.post(
            reverse('helpdesk:ingresar'),
            {'username': 'ana', 'password': 'clave-mala'},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Usuario o contraseña incorrectos.')

    def test_salir_cierra_la_sesion(self):
        crear_cliente()
        self.client.login(username='ana', password='ClaveSegura#2026')

        self.client.post(reverse('helpdesk:salir'))

        respuesta = self.client.get(reverse('helpdesk:inicio'))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('helpdesk:ingresar'), respuesta.url)


class SesionTests(TestCase):
    def setUp(self):
        crear_cliente()
        self.client.login(username='ana', password='ClaveSegura#2026')

    def test_la_sesion_se_cierra_despues_de_cuatro_minutos(self):
        self.assertEqual(settings.SESSION_COOKIE_AGE, 60 * 4)
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)

    def test_el_ping_renueva_la_sesion(self):
        respuesta = self.client.post(reverse('helpdesk:ping'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()['ok'])
        self.assertTrue(respuesta.json()['autenticado'])
        self.assertEqual(respuesta.json()['expira_en'], 240)
        self.assertIn('ultima_actividad', self.client.session)
        self.assertEqual(int(respuesta.cookies['sessionid']['max-age']), 240)

    def test_el_ping_solo_acepta_post(self):
        respuesta = self.client.get(reverse('helpdesk:ping'))

        self.assertEqual(respuesta.status_code, 405)

    def test_el_ping_establece_la_cookie_csrf(self):
        respuesta = self.client.post(reverse('helpdesk:ping'))

        self.assertIn('csrftoken', respuesta.cookies)

    def test_el_ping_tambien_responde_sin_iniciar_sesion(self):
        self.client.logout()

        respuesta = self.client.post(reverse('helpdesk:ping'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.json()['autenticado'])

    def test_las_paginas_muestran_el_aviso_de_sesion_por_vencer(self):
        html = self.client.get(reverse('helpdesk:inicio')).content.decode()

        self.assertIn('/js/sesion.', html)
        self.assertIn('modal-sesion', html)
        self.assertIn('Renovar sesión', html)

    def test_la_pagina_de_ingresar_avisa_cuando_la_sesion_se_cerro(self):
        self.client.logout()

        respuesta = self.client.get(reverse('helpdesk:ingresar'), {'sesion': 'cerrada'})

        self.assertContains(respuesta, 'Su sesión se cerró por inactividad')


class SolicitudClienteTests(TestCase):
    def setUp(self):
        self.cuenta, self.perfil = crear_cliente()
        self.client.login(username='ana', password='ClaveSegura#2026')

    def test_registra_la_solicitud_con_los_datos_ya_guardados(self):
        respuesta = self.client.post(reverse('helpdesk:solicitar'), DATOS_SOLICITUD)

        self.assertEqual(respuesta.status_code, 302)
        ticket = Ticket.objects.get()
        self.assertEqual(ticket.usuario, self.perfil)
        self.assertEqual(ticket.usuario.telefono, '3001234567')
        self.assertEqual(ticket.estado, Ticket.Estado.EN_PROCESO)

    def test_no_vuelve_a_pedir_los_datos_del_cliente(self):
        respuesta = self.client.get(reverse('helpdesk:solicitar'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, 'name="nombre"')
        self.assertNotContains(respuesta, 'name="telefono"')
        self.assertContains(respuesta, '300 123 4567')

    def test_preselecciona_el_producto_que_venia_en_la_url(self):
        respuesta = self.client.get(reverse('helpdesk:solicitar'), {'producto': 'TV'})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, '<option value="TV" selected>', html=False)

    def test_el_producto_otro_exige_el_nombre_del_producto(self):
        respuesta = self.client.post(
            reverse('helpdesk:solicitar'), {**DATOS_SOLICITUD, 'producto': 'OTRO'}
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Ticket.objects.exists())
        self.assertContains(respuesta, 'Escriba el producto que necesita soporte.')

    def test_el_cliente_puede_actualizar_sus_datos(self):
        respuesta = self.client.post(
            reverse('helpdesk:inicio'),
            {
                'nombre': 'Ana María',
                'apellido': 'Ramírez',
                'direccion': 'Carrera 11 # 22-33',
                'telefono': '3001234567',
                'correo': 'ana@example.com',
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.nombre, 'Ana María')
        self.assertEqual(self.perfil.direccion, 'Carrera 11 # 22-33')

    def test_el_correo_es_obligatorio_al_actualizar_los_datos(self):
        respuesta = self.client.post(
            reverse('helpdesk:inicio'),
            {
                'nombre': 'Ana',
                'apellido': 'Ramírez',
                'direccion': 'Carrera 11 # 22-33',
                'telefono': '3001234567',
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Correo electrónico *')
        self.assertContains(respuesta, 'Este campo es obligatorio.')


class SeguimientoClienteTests(TestCase):
    def setUp(self):
        self.cuenta, self.perfil = crear_cliente()
        self.ticket = crear_ticket_de_prueba(self.perfil)
        self.client.login(username='ana', password='ClaveSegura#2026')

    def test_el_cliente_ve_su_propio_ticket(self):
        respuesta = self.client.get(
            reverse('helpdesk:seguimiento'), {'radicado': self.ticket.radicado}
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.ticket.radicado)
        self.assertContains(respuesta, Ticket.Estado.EN_PROCESO.label)

    def test_el_seguimiento_muestra_la_linea_del_tiempo(self):
        tomar_ticket(self.ticket.pk)

        html = self.client.get(
            reverse('helpdesk:seguimiento'), {'radicado': self.ticket.radicado}
        ).content.decode()

        self.assertIn('linea-tiempo', html)
        self.assertIn('punto-proceso', html)
        self.assertIn('punto-atendido', html)
        self.assertIn('insignia-proceso', html)
        self.assertIn('insignia-atendido', html)
        self.assertIn('Ticket creado por el cliente', html)
        self.assertIn('Ticket tomado por el administrador', html)

    def test_el_formulario_de_consulta_no_muestra_el_aviso_de_obligatorios(self):
        respuesta = self.client.get(reverse('helpdesk:seguimiento'))

        self.assertNotContains(respuesta, 'Los campos marcados con')
        self.assertNotContains(respuesta, 'Radicado del ticket *')

    def test_los_tickets_del_cliente_enlazan_a_su_linea_del_tiempo(self):
        html = self.client.get(reverse('helpdesk:seguimiento')).content.decode()

        enlace = f'href="/seguimiento/?radicado={self.ticket.radicado}"'
        self.assertIn(enlace, html)
        self.assertNotIn('Ver línea de tiempo', html)
        self.assertIn('data-cargando', html)

    def test_el_cliente_no_ve_los_tickets_de_otro_cliente(self):
        otro_cuenta, otro_perfil = crear_cliente(
            nombre='Luis', telefono='3011112222', usuario='luis'
        )
        ticket_ajeno = crear_ticket_de_prueba(otro_perfil)

        respuesta = self.client.get(
            reverse('helpdesk:seguimiento'), {'radicado': ticket_ajeno.radicado}
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'No encontramos ningún ticket con ese radicado.')
        self.assertNotContains(respuesta, 'Seguimiento del caso')
        self.assertContains(respuesta, self.ticket.radicado)


class ModeloYTransicionesTests(TestCase):
    def setUp(self):
        self.cuenta, self.perfil = crear_cliente()
        self.ticket = crear_ticket_de_prueba(self.perfil)

    def test_el_ticket_apunta_a_un_usuario(self):
        self.assertIsInstance(self.ticket.usuario, Usuario)
        self.assertEqual(self.ticket.usuario.nombre_completo, 'Ana Ramírez')
        self.assertEqual(self.ticket.usuario.tickets.count(), 1)

    def test_radicados_son_unicos(self):
        otro_cuenta, otro_perfil = crear_cliente(
            nombre='Luis', telefono='3011112222', usuario='luis'
        )
        segundo = crear_ticket_de_prueba(otro_perfil)

        self.assertNotEqual(self.ticket.radicado, segundo.radicado)

    def test_producto_otro_guarda_el_texto_ingresado(self):
        ticket = crear_ticket(
            usuario=self.perfil,
            producto=Ticket.Producto.OTRO,
            producto_otro='Proyector de sala 3',
            descripcion='No prende.',
        )

        self.assertEqual(ticket.producto_texto, 'Proyector de sala 3')

    def test_tomar_ticket_pasa_a_atendido(self):
        ticket = tomar_ticket(self.ticket.pk)

        self.assertEqual(ticket.estado, Ticket.Estado.ATENDIDO)
        self.assertIsNotNone(ticket.atendido_en)
        self.assertEqual(ticket.historial[-1]['estado'], Ticket.Estado.ATENDIDO.label)

    def test_crear_ticket_envia_correo_de_confirmacion(self):
        with self.captureOnCommitCallbacks(execute=True):
            ticket = crear_ticket_de_prueba(self.perfil)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['ana@example.com'])
        self.assertIn(ticket.radicado, mail.outbox[0].subject)
        self.assertIn(Ticket.Estado.EN_PROCESO.label, mail.outbox[0].body)
        html = mail.outbox[0].alternatives[0].content
        self.assertEqual(mail.outbox[0].alternatives[0].mimetype, 'text/html')
        self.assertIn(ticket.radicado, html)
        self.assertIn('Consultar seguimiento', html)

    def test_tomar_ticket_envia_correo_al_cliente(self):
        with self.captureOnCommitCallbacks(execute=True):
            tomar_ticket(self.ticket.pk)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['ana@example.com'])
        self.assertIn(self.ticket.radicado, mail.outbox[0].subject)
        self.assertIn(Ticket.Estado.ATENDIDO.label, mail.outbox[0].body)
        html = mail.outbox[0].alternatives[0].content
        self.assertEqual(mail.outbox[0].alternatives[0].mimetype, 'text/html')
        self.assertIn(Ticket.Estado.ATENDIDO.label, html)
        self.assertIn(self.ticket.radicado, html)
        self.assertIn('Consultar seguimiento', html)

    def test_escalar_ticket_envia_correo_con_la_dependencia(self):
        tomar_ticket(self.ticket.pk)

        with self.captureOnCommitCallbacks(execute=True):
            escalar_ticket(self.ticket.pk, Ticket.Dependencia.SOPORTE_TECNICO)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(Ticket.Estado.ESCALADO.label, mail.outbox[0].subject)
        self.assertIn('Soporte técnico', mail.outbox[0].body)
        self.assertIn('Soporte técnico', mail.outbox[0].alternatives[0].content)

    def test_finalizar_ticket_envia_correo_al_cliente(self):
        tomar_ticket(self.ticket.pk)

        with self.captureOnCommitCallbacks(execute=True):
            finalizar_ticket(self.ticket.pk)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(Ticket.Estado.FINALIZADO.label, mail.outbox[0].subject)
        self.assertIn(Ticket.Estado.FINALIZADO.label, mail.outbox[0].alternatives[0].content)

    def test_no_se_envia_correo_si_el_cliente_no_tiene_correo(self):
        self.perfil.correo = ''
        self.perfil.save(update_fields=['correo'])

        with self.captureOnCommitCallbacks(execute=True):
            tomar_ticket(self.ticket.pk)

        self.assertEqual(len(mail.outbox), 0)

    def test_una_transicion_invalida_no_envia_correo(self):
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(TransicionInvalida):
                finalizar_ticket(self.ticket.pk)

        self.assertEqual(len(mail.outbox), 0)

    def test_no_se_puede_tomar_un_ticket_ya_atendido(self):
        tomar_ticket(self.ticket.pk)

        with self.assertRaises(TransicionInvalida):
            tomar_ticket(self.ticket.pk)

    def test_no_se_puede_finalizar_un_ticket_en_proceso(self):
        with self.assertRaises(TransicionInvalida):
            finalizar_ticket(self.ticket.pk)

    def test_escalar_ticket_guarda_la_dependencia(self):
        tomar_ticket(self.ticket.pk)

        ticket = escalar_ticket(self.ticket.pk, Ticket.Dependencia.SOPORTE_TECNICO)

        self.assertEqual(ticket.estado, Ticket.Estado.ESCALADO)
        self.assertEqual(ticket.dependencia, Ticket.Dependencia.SOPORTE_TECNICO)

    def test_dependencia_texto_devuelve_la_etiqueta(self):
        tomar_ticket(self.ticket.pk)

        ticket = escalar_ticket(self.ticket.pk, Ticket.Dependencia.SISTEMAS)

        self.assertEqual(ticket.dependencia_texto, 'Sistemas / TI')

    def test_no_se_puede_escalar_a_una_dependencia_invalida(self):
        tomar_ticket(self.ticket.pk)

        with self.assertRaises(TransicionInvalida):
            escalar_ticket(self.ticket.pk, 'cualquier texto')

        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.estado, Ticket.Estado.ATENDIDO)

    def test_escalado_se_finaliza_desde_la_dependencia(self):
        tomar_ticket(self.ticket.pk)
        escalar_ticket(self.ticket.pk, Ticket.Dependencia.SOPORTE_TECNICO)

        ticket = finalizar_ticket(self.ticket.pk)

        self.assertEqual(ticket.estado, Ticket.Estado.FINALIZADO)
        self.assertIsNotNone(ticket.finalizado_en)


class PanelAdministradorTests(TestCase):
    def setUp(self):
        # El administrador se define por su ROL (tipo ADMIN), no por is_staff.
        self.usuario = User.objects.create_user(
            username='soporte',
            password='clave-de-prueba-123',
        )
        self.perfil_admin = Usuario.objects.create(
            cuenta=self.usuario,
            nombre='Soporte',
            apellido='Help Desk',
            direccion='Sede principal',
            telefono='3009998888',
            tipo=Usuario.Tipo.ADMIN,
        )
        self.cuenta, self.perfil = crear_cliente()
        self.ticket = crear_ticket_de_prueba(self.perfil)

    def test_el_panel_requiere_iniciar_sesion(self):
        respuesta = self.client.get(reverse('helpdesk:panel_dashboard'))

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('helpdesk:ingresar'), respuesta.url)

    def test_los_botones_de_filtro_quedan_juntos_en_el_panel(self):
        self.client.login(username='soporte', password='clave-de-prueba-123')

        for nombre in ('helpdesk:panel_en_proceso', 'helpdesk:panel_reportes', 'helpdesk:panel_usuarios'):
            html = self.client.get(reverse(nombre)).content.decode()

            self.assertIn('filtros-campos', html)
            self.assertIn('filtros-acciones', html)
            self.assertIn('>Filtrar<', html)
            self.assertIn('>Limpiar<', html)

    def test_el_login_del_panel_redirige_al_ingreso_comun(self):
        respuesta = self.client.get(reverse('helpdesk:panel_login'))

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('helpdesk:ingresar'), respuesta.url)

    def test_usuario_sin_permisos_no_entra_al_panel(self):
        self.client.login(username='ana', password='ClaveSegura#2026')

        respuesta = self.client.get(reverse('helpdesk:panel_dashboard'))

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.url, reverse('helpdesk:inicio'))

    def test_el_rol_decide_el_acceso_y_no_los_permisos_de_django(self):
        # Un usuario con is_staff=True pero rol CLIENTE tampoco entra.
        usuario_staff = User.objects.create_user(
            username='otro',
            password='clave-de-prueba-123',
            is_staff=True,
        )
        Usuario.objects.create(
            cuenta=usuario_staff,
            nombre='Otro',
            apellido='Usuario',
            direccion='Sede principal',
            telefono='3018887777',
            tipo=Usuario.Tipo.CLIENTE,
        )
        self.client.login(username='otro', password='clave-de-prueba-123')

        respuesta = self.client.get(reverse('helpdesk:panel_dashboard'))

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.url, reverse('helpdesk:inicio'))

    def test_el_administrador_entra_al_panel_sin_is_staff(self):
        self.assertFalse(self.usuario.is_staff)
        self.assertFalse(self.usuario.is_superuser)
        self.client.login(username='soporte', password='clave-de-prueba-123')

        respuesta = self.client.get(reverse('helpdesk:panel_dashboard'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Resumen de tickets')

    def test_administrador_toma_y_escala_un_ticket(self):
        self.client.login(username='soporte', password='clave-de-prueba-123')

        respuesta = self.client.post(reverse('helpdesk:panel_ticket_atender', args=[self.ticket.pk]))

        self.assertEqual(respuesta.status_code, 302)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.estado, Ticket.Estado.ATENDIDO)

        respuesta = self.client.post(
            reverse('helpdesk:panel_ticket_escalar', args=[self.ticket.pk]),
            {'dependencia': Ticket.Dependencia.SOPORTE_TECNICO},
        )

        self.assertEqual(respuesta.status_code, 302)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.estado, Ticket.Estado.ESCALADO)
        self.assertEqual(self.ticket.dependencia, Ticket.Dependencia.SOPORTE_TECNICO)

        respuesta = self.client.post(reverse('helpdesk:panel_ticket_finalizar', args=[self.ticket.pk]))

        self.assertEqual(respuesta.status_code, 302)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.estado, Ticket.Estado.FINALIZADO)

    def test_el_formulario_de_escalar_solo_ofrece_dependencias_validas(self):
        tomar_ticket(self.ticket.pk)
        self.client.login(username='soporte', password='clave-de-prueba-123')

        respuesta = self.client.get(
            reverse('helpdesk:panel_ticket_escalar', args=[self.ticket.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        for etiqueta in ('Sistemas / TI', 'Soporte técnico', 'Otra dependencia'):
            self.assertContains(respuesta, etiqueta)

    def test_no_escala_con_una_dependencia_invalida(self):
        tomar_ticket(self.ticket.pk)
        self.client.login(username='soporte', password='clave-de-prueba-123')

        respuesta = self.client.post(
            reverse('helpdesk:panel_ticket_escalar', args=[self.ticket.pk]),
            {'dependencia': 'dependencia-invalida'},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Seleccione una dependencia válida.')
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.estado, Ticket.Estado.ATENDIDO)

    def test_el_panel_muestra_el_usuario_una_sola_vez_y_sin_links_de_cliente(self):
        self.client.login(username='soporte', password='clave-de-prueba-123')

        html = self.client.get(reverse('helpdesk:panel_dashboard')).content.decode()

        self.assertNotIn('>Salir<', html)
        self.assertIn('Cerrar sesión', html)
        self.assertIn('menu-usuario-icono', html)
        self.assertNotIn('Ver mis tickets', html)
        self.assertNotIn('Registrar solicitud', html)
        self.assertNotIn('Actualizar datos', html)
        self.assertNotIn('>Inicio<', html)

    def test_el_administrador_no_usa_el_area_de_cliente(self):
        self.client.login(username='soporte', password='clave-de-prueba-123')

        for nombre in ('helpdesk:solicitar', 'helpdesk:seguimiento'):
            respuesta = self.client.get(reverse(nombre))
            self.assertRedirects(respuesta, reverse('helpdesk:panel_dashboard'))

    def test_la_ficha_del_ticket_muestra_la_linea_del_tiempo(self):
        tomar_ticket(self.ticket.pk)
        self.client.login(username='soporte', password='clave-de-prueba-123')

        html = self.client.get(
            reverse('helpdesk:panel_ticket_detalle', args=[self.ticket.pk])
        ).content.decode()

        self.assertIn('linea-tiempo', html)
        self.assertIn('punto-proceso', html)
        self.assertIn('punto-atendido', html)
        self.assertIn('Ticket tomado por el administrador', html)

    def test_seccion_otra_dependencia_solo_muestra_finalizar(self):
        tomar_ticket(self.ticket.pk)
        escalar_ticket(self.ticket.pk, Ticket.Dependencia.SOPORTE_TECNICO)
        self.client.login(username='soporte', password='clave-de-prueba-123')

        respuesta = self.client.get(reverse('helpdesk:panel_otra_dependencia'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Finalizar')
        self.assertNotContains(respuesta, 'Tomar ticket')
        self.assertNotContains(respuesta, 'Subir a otra dependencia')

    def test_descarga_de_reporte_csv(self):
        self.client.login(username='soporte', password='clave-de-prueba-123')

        respuesta = self.client.get(reverse('helpdesk:panel_reportes_csv'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('text/csv', respuesta['Content-Type'])
        self.assertIn(self.ticket.radicado, respuesta.content.decode('utf-8-sig'))

    def test_descarga_de_reporte_excel(self):
        self.client.login(username='soporte', password='clave-de-prueba-123')

        respuesta = self.client.get(reverse('helpdesk:panel_reportes_excel'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('spreadsheetml.sheet', respuesta['Content-Type'])
        self.assertIn('.xlsx', respuesta['Content-Disposition'])

        libro = load_workbook(BytesIO(respuesta.content))
        hoja = libro['Tickets']
        self.assertEqual(hoja.cell(row=1, column=1).value, 'Radicado')
        self.assertEqual(hoja.cell(row=2, column=1).value, self.ticket.radicado)
        self.assertEqual(hoja.cell(row=2, column=3).value, 'Ana')
        self.assertEqual(hoja.cell(row=2, column=9).value, Ticket.Estado.EN_PROCESO.label)

    def test_el_boton_de_csv_no_deja_la_pantalla_cargando(self):
        self.client.login(username='soporte', password='clave-de-prueba-123')

        html = self.client.get(reverse('helpdesk:panel_reportes')).content.decode()

        self.assertIn('data-spin', html)
        self.assertNotIn('data-cargando href="/panel/reportes/csv/', html)

    def test_panel_lista_los_usuarios_registrados(self):
        self.client.login(username='soporte', password='clave-de-prueba-123')

        respuesta = self.client.get(reverse('helpdesk:panel_usuarios'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Ana Ramírez')
        self.assertContains(respuesta, 'Cliente')
