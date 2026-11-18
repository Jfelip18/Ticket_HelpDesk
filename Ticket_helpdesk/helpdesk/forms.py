import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone

from .config import LONGITUDES_PERFIL, LONGITUDES_REGISTRO, LONGITUD_DESCRIPCION
from .models import Ticket, Usuario


def _limite_de_la_base_de_datos(campo):
    """Tamaño máximo de la columna en la base de datos para ese campo."""
    if campo == 'usuario':
        return User._meta.get_field('username').max_length
    return Usuario._meta.get_field(campo).max_length


def aplicar_longitudes(form, longitudes):
    """Fija la longitud máxima de los campos indicados (config.py)."""
    for nombre, configurado in longitudes.items():
        if nombre not in form.fields:
            continue
        maximo = min(configurado, _limite_de_la_base_de_datos(nombre))
        form.fields[nombre].max_length = maximo
        form.fields[nombre].widget.attrs['maxlength'] = maximo
    return form


def normalizar_telefono(valor):
    return ''.join(caracter for caracter in (valor or '') if caracter.isdigit())


def marcar_obligatorios(form):
    """Agrega un asterisco a la etiqueta de todos los campos obligatorios."""
    for campo in form.fields.values():
        if campo.required and campo.label:
            campo.label = f'{campo.label} *'
    return form


class AccesoForm(AuthenticationForm):
    """Formulario de ingreso con los estilos de la aplicación."""

    error_messages = {
        'invalid_login': 'Usuario o contraseña incorrectos.',
        'inactive': 'Esta cuenta está inactiva.',
    }

    class Meta:
        model = User
        fields = ['username', 'password']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Usuario'
        self.fields['password'].label = 'Contraseña'
        self.fields['username'].widget.attrs.update(
            {
                'class': 'campo',
                'placeholder': 'Su nombre de usuario',
                'autocomplete': 'username',
                'autofocus': True,
            }
        )
        self.fields['password'].widget.attrs.update(
            {
                'class': 'campo',
                'placeholder': 'Su contraseña',
                'autocomplete': 'current-password',
            }
        )
        marcar_obligatorios(self)


class RegistroForm(forms.Form):
    """Formulario de registro del cliente (crea la cuenta de acceso y su ficha)."""

    nombre = forms.CharField(
        max_length=80,
        label='Nombre',
        widget=forms.TextInput(attrs={'placeholder': 'Nombre', 'class': 'campo'}),
    )
    apellido = forms.CharField(
        max_length=100,
        label='Apellido',
        widget=forms.TextInput(attrs={'placeholder': 'Apellido', 'class': 'campo'}),
    )
    direccion = forms.CharField(
        max_length=200,
        label='Dirección del cliente',
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Dirección del cliente (calle, número, ciudad)',
                'class': 'campo',
            }
        ),
    )
    telefono = forms.CharField(
        max_length=30,
        label='Número de teléfono',
        widget=forms.TextInput(
            attrs={
                'placeholder': '324 344 1263',
                'class': 'campo telefono',
                'inputmode': 'numeric',
                'autocomplete': 'tel',
            }
        ),
    )
    usuario = forms.CharField(
        max_length=150,
        label='Usuario',
        widget=forms.TextInput(
            attrs={'placeholder': 'Nombre de usuario', 'class': 'campo', 'autocomplete': 'username'}
        ),
    )
    contrasena = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(
            attrs={'class': 'campo', 'autocomplete': 'new-password'}
        ),
    )
    repetir_contrasena = forms.CharField(
        label='Repetir contraseña',
        widget=forms.PasswordInput(
            attrs={'class': 'campo', 'autocomplete': 'new-password'}
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # La longitud de los campos sale de helpdesk/config.py.
        aplicar_longitudes(self, LONGITUDES_REGISTRO)
        marcar_obligatorios(self)

    def clean_usuario(self):
        valor = self.cleaned_data['usuario'].strip()
        if User.objects.filter(username__iexact=valor).exists():
            raise ValidationError('Ese nombre de usuario ya está en uso.')
        return valor

    def clean_telefono(self):
        digitos = normalizar_telefono(self.cleaned_data['telefono'])
        if not 7 <= len(digitos) <= 15:
            raise ValidationError('Ingrese un número de teléfono válido (entre 7 y 15 dígitos).')
        if Usuario.objects.filter(telefono=digitos).exists():
            raise ValidationError(
                'Ya existe una cuenta registrada con ese número de teléfono, ingrese con su usuario.'
            )
        return digitos

    def clean(self):
        cleaned_data = super().clean()
        contrasena = cleaned_data.get('contrasena')
        repetir = cleaned_data.get('repetir_contrasena')
        if contrasena and repetir and contrasena != repetir:
            self.add_error('repetir_contrasena', 'Las contraseñas no coinciden.')
        if contrasena:
            try:
                validate_password(contrasena)
            except ValidationError as error:
                self.add_error('contrasena', error)
        return cleaned_data


class PerfilForm(forms.ModelForm):
    """Actualización de los datos del cliente ya registrado."""

    class Meta:
        model = Usuario
        fields = ['nombre', 'apellido', 'direccion', 'telefono']
        labels = {
            'nombre': 'Nombre',
            'apellido': 'Apellido',
            'direccion': 'Dirección del cliente',
            'telefono': 'Número de teléfono',
        }
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'campo'}),
            'apellido': forms.TextInput(attrs={'class': 'campo'}),
            'direccion': forms.TextInput(attrs={'class': 'campo'}),
            'telefono': forms.TextInput(
                attrs={
                    'class': 'campo telefono',
                    'placeholder': '324 344 1263',
                    'inputmode': 'numeric',
                    'autocomplete': 'tel',
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_longitudes(self, LONGITUDES_PERFIL)
        marcar_obligatorios(self)

    def clean_telefono(self):
        digitos = normalizar_telefono(self.cleaned_data['telefono'])
        if not 7 <= len(digitos) <= 15:
            raise ValidationError('Ingrese un número de teléfono válido (entre 7 y 15 dígitos).')
        otros = Usuario.objects.filter(telefono=digitos)
        if self.instance.pk:
            otros = otros.exclude(pk=self.instance.pk)
        if otros.exists():
            raise ValidationError('Ese número de teléfono ya está registrado.')
        return digitos


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = [
            'producto',
            'producto_otro',
            'descripcion',
        ]
        labels = {
            'producto': 'Producto que necesita soporte',
            'producto_otro': 'Nombre del producto',
            'descripcion': 'Describa el problema',
        }
        widgets = {
            'producto': forms.Select(attrs={'class': 'campo'}),
            'producto_otro': forms.TextInput(
                attrs={
                    'placeholder': 'Escriba el producto que necesita soporte',
                    'class': 'campo',
                }
            ),
            'descripcion': forms.Textarea(
                attrs={
                    'rows': 5,
                    'placeholder': 'Cuéntenos qué está pasando con el producto',
                    'class': 'campo',
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['producto_otro'].required = False
        self.fields['descripcion'].max_length = LONGITUD_DESCRIPCION
        self.fields['descripcion'].widget.attrs['maxlength'] = LONGITUD_DESCRIPCION
        marcar_obligatorios(self)

    def clean(self):
        cleaned_data = super().clean()
        producto = cleaned_data.get('producto')
        producto_otro = (cleaned_data.get('producto_otro') or '').strip()
        if producto == Ticket.Producto.OTRO and not producto_otro:
            self.add_error('producto_otro', 'Escriba el producto que necesita soporte.')
        return cleaned_data


class SeguimientoForm(forms.Form):
    radicado = forms.CharField(
        max_length=20,
        label='Radicado del ticket',
        widget=forms.TextInput(
            attrs={'placeholder': 'HD-2026-000001', 'class': 'campo', 'autocomplete': 'off'}
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        marcar_obligatorios(self)

    def clean_radicado(self):
        valor = self.cleaned_data['radicado'].strip().upper()
        digitos = re.sub(r'\D', '', valor)
        if len(digitos) >= 10:
            valor = f'HD-{digitos[:4]}-{digitos[4:10]}'
        elif len(digitos) == 6:
            valor = f'HD-{timezone.localtime().year}-{digitos}'
        return valor
