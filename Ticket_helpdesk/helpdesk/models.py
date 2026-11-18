from django.conf import settings
from django.db import models


class Usuario(models.Model):
    class Tipo(models.TextChoices):
        CLIENTE = 'CLIENTE', 'Cliente'
        ADMIN = 'ADMIN', 'Administrador'

    cuenta = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='perfil_helpdesk',
        null=True,
        blank=True,
        verbose_name='Cuenta de acceso',
    )
    nombre = models.CharField(max_length=80, verbose_name='Nombre')
    apellido = models.CharField(max_length=100, verbose_name='Apellido')
    direccion = models.CharField(max_length=200, verbose_name='Dirección')
    telefono = models.CharField(
        max_length=30,
        unique=True,
        verbose_name='Número de teléfono',
    )
    tipo = models.CharField(
        max_length=10,
        choices=Tipo.choices,
        default=Tipo.CLIENTE,
        db_index=True,
        verbose_name='Tipo de usuario',
    )
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name='Creado')
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name='Actualizado')

    class Meta:
        ordering = ['-creado_en']
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return self.nombre_completo

    @property
    def nombre_completo(self):
        return f'{self.nombre} {self.apellido}'.strip()

    @property
    def es_cliente(self):
        return self.tipo == self.Tipo.CLIENTE

    @property
    def telefono_formateado(self):
        digitos = ''.join(caracter for caracter in self.telefono if caracter.isdigit())
        if len(digitos) == 10:
            return f'{digitos[:3]} {digitos[3:6]} {digitos[6:]}'
        return self.telefono


class Ticket(models.Model):
    class Estado(models.TextChoices):
        EN_PROCESO = 'EN_PROCESO', 'En proceso'
        ATENDIDO = 'ATENDIDO', 'Atendido'
        FINALIZADO = 'FINALIZADO', 'Finalizado'
        ESCALADO = 'ESCALADO', 'Escalado a otra dependencia'

    class Producto(models.TextChoices):
        VIDEOBEAM = 'VIDEOBEAM', 'Videobeam'
        TV = 'TV', 'TV'
        CABLE_HDMI = 'CABLE_HDMI', 'Cables HDMI'
        AIRE_ACONDICIONADO = 'AIRE_ACONDICIONADO', 'Aire acondicionado'
        OTRO = 'OTRO', 'Otro'

    class Dependencia(models.TextChoices):
        SISTEMAS = 'SISTEMAS', 'Sistemas / TI'
        SOPORTE_TECNICO = 'SOPORTE_TECNICO', 'Soporte técnico'
        MANTENIMIENTO = 'MANTENIMIENTO', 'Mantenimiento'
        RECURSOS_HUMANOS = 'RECURSOS_HUMANOS', 'Recursos humanos'
        ADMINISTRACION = 'ADMINISTRACION', 'Administración'
        ACADEMICA = 'ACADEMICA', 'Coordinación académica'
        BIBLIOTECA = 'BIBLIOTECA', 'Biblioteca'
        OTRA = 'OTRA', 'Otra dependencia'

    radicado = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        verbose_name='Radicado',
    )
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name='tickets',
        verbose_name='Usuario',
    )
    producto = models.CharField(
        max_length=30,
        choices=Producto.choices,
        verbose_name='Producto',
    )
    producto_otro = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Otro producto',
    )
    descripcion = models.TextField(verbose_name='Descripción del problema')
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.EN_PROCESO,
        db_index=True,
        verbose_name='Estado',
    )
    dependencia = models.CharField(
        max_length=150,
        blank=True,
        choices=Dependencia.choices,
        verbose_name='Dependencia de destino',
    )
    historial = models.JSONField(default=list, blank=True, verbose_name='Historial')
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name='Creado')
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name='Actualizado')
    atendido_en = models.DateTimeField(null=True, blank=True, verbose_name='Atendido')
    finalizado_en = models.DateTimeField(null=True, blank=True, verbose_name='Finalizado')

    class Meta:
        ordering = ['-creado_en']
        verbose_name = 'Ticket'
        verbose_name_plural = 'Tickets'
        indexes = [models.Index(fields=['estado', '-creado_en'])]

    def __str__(self):
        return f'{self.radicado} - {self.usuario.nombre_completo}'

    @property
    def nombre_completo(self):
        return self.usuario.nombre_completo

    @property
    def producto_texto(self):
        if self.producto == self.Producto.OTRO:
            return self.producto_otro or 'Otro'
        return self.get_producto_display()

    @property
    def dependencia_texto(self):
        return self.get_dependencia_display() if self.dependencia else ''

    @property
    def estado_clase(self):
        return {
            self.Estado.EN_PROCESO: 'insignia-proceso',
            self.Estado.ATENDIDO: 'insignia-atendido',
            self.Estado.ESCALADO: 'insignia-escalado',
            self.Estado.FINALIZADO: 'insignia-finalizado',
        }[self.estado]

    @property
    def puede_atender(self):
        return self.estado == self.Estado.EN_PROCESO

    @property
    def puede_finalizar(self):
        return self.estado in (self.Estado.ATENDIDO, self.Estado.ESCALADO)

    @property
    def puede_escalar(self):
        return self.estado == self.Estado.ATENDIDO
