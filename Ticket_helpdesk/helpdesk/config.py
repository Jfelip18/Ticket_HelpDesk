"""Configuración editable de la aplicación.

Aquí se cambian las longitudes de los campos SIN tocar `helpdesk/models.py`.
"""

# Longitud máxima (en caracteres) de los campos del formulario de REGISTRO.
# OJO: el valor nunca puede superar el tamaño de la columna en la base de
# datos (definido en `helpdesk/models.py`, modelo `Usuario`). Si lo superas,
# el formulario se ajusta solo al valor de la base de datos para que no haya
# errores al guardar. Para ampliar de verdad la BD hay que cambiar el modelo
# y correr una migración.
LONGITUDES_REGISTRO = {
    'nombre': 100,
    'apellido': 100,
    'direccion':100,
    'telefono': 100,
    'usuario': 100,
}

# Longitud máxima de los campos del formulario de ACTUALIZAR DATOS del cliente.
LONGITUDES_PERFIL = {
    'nombre': 100,
    'apellido': 100,
    'direccion':100,
    'telefono': 100,
}

# Longitud máxima de la descripción del problema (no tiene límite en la BD).
LONGITUD_DESCRIPCION = 1000
