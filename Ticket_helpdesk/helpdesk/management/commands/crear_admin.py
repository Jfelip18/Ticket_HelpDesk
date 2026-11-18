"""Comando auxiliar para generar el SQL del administrador del Help Desk."""

from datetime import datetime

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone

SQL_AUTH = """
INSERT INTO auth_user (
    password, is_superuser, is_staff, is_active, date_joined,
    username, first_name, last_name, email
)
VALUES (%s, false, false, true, %s, %s, %s, %s, %s);
"""

SQL_PERFIL = """
INSERT INTO helpdesk_usuario (
    cuenta_id, nombre, apellido, direccion, telefono, tipo, creado_en, actualizado_en
)
SELECT id, %s, %s, %s, %s, 'ADMIN', %s, %s
FROM auth_user
WHERE username = %s;
"""


def sql_legible(sql, valores):
    """Sustituye los parámetros por literales (NOW() para las fechas)."""
    partes = sql.split('%s')
    salida = partes[0]
    for valor, resto in zip(valores, partes[1:]):
        texto = 'NOW()' if isinstance(valor, datetime) else f"'{valor}'"
        salida += texto + resto
    return salida


class Command(BaseCommand):
    help = (
        'Genera el SQL para crear el usuario administrador del Help Desk. '
        'El acceso al panel se decide por el rol (tipo ADMIN); la cuenta no '
        'tiene permisos en el admin de Django.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--usuario', default='admin')
        parser.add_argument('--nombre', default='Administrador')
        parser.add_argument('--apellido', default='Help Desk')
        parser.add_argument('--email', default='admin@local')
        parser.add_argument('--telefono', default='3000000000')
        parser.add_argument('--direccion', default='Sede principal')
        parser.add_argument('--password', required=True, help='Contraseña del administrador')
        parser.add_argument(
            '--ejecutar',
            action='store_true',
            help='Ejecuta el SQL en la base de datos (si no, solo lo muestra)',
        )
        parser.add_argument(
            '--actualizar',
            action='store_true',
            help='Actualiza la contraseña de un administrador que ya existe',
        )

    def handle(self, *args, **options):
        usuario = options['usuario']
        telefono = ''.join(c for c in options['telefono'] if c.isdigit())

        if options['ejecutar']:
            if options['actualizar']:
                self._actualizar_contrasena(usuario, opciones['password'])
                return
            self._validar(usuario, telefono)

        ahora = timezone.now()
        valores_auth = [
            make_password(options['password']),
            ahora,
            usuario,
            options['nombre'],
            options['apellido'],
            options['email'],
        ]
        valores_perfil = [
            options['nombre'],
            options['apellido'],
            options['direccion'],
            telefono,
            ahora,
            ahora,
            usuario,
        ]

        if not options['ejecutar']:
            self.stdout.write(sql_legible(SQL_AUTH, valores_auth))
            self.stdout.write(sql_legible(SQL_PERFIL, valores_perfil))
            self.stdout.write('')
            self.stdout.write(
                self.style.WARNING(
                    'Copia este SQL y ejecútalo en tu base de datos, '
                    'o vuelve a correr el comando con --ejecutar.'
                )
            )
            return

        with connection.cursor() as cursor:
            cursor.execute(SQL_AUTH, valores_auth)
            cursor.execute(SQL_PERFIL, valores_perfil)

        self.stdout.write(self.style.SUCCESS(f'Administrador "{usuario}" creado correctamente.'))

    def _actualizar_contrasena(self, usuario, contrasena):
        with connection.cursor() as cursor:
            cursor.execute(
                'UPDATE auth_user SET password = %s WHERE username = %s',
                [make_password(contrasena), usuario],
            )
            if cursor.rowcount == 0:
                raise CommandError(f'El usuario "{usuario}" no existe.')
        self.stdout.write(
            self.style.SUCCESS(f'Contraseña de "{usuario}" actualizada correctamente.')
        )

    def _validar(self, usuario, telefono):
        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM auth_user WHERE username = %s', [usuario])
            if cursor.fetchone()[0]:
                raise CommandError(f'El usuario "{usuario}" ya existe.')
            cursor.execute(
                'SELECT COUNT(*) FROM helpdesk_usuario WHERE telefono = %s', [telefono]
            )
            if cursor.fetchone()[0]:
                raise CommandError(
                    f'El teléfono {telefono} ya está registrado en helpdesk_usuario; '
                    'usa otro con --telefono.'
                )
