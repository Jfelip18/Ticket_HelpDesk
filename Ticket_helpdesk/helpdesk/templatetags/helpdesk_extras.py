from django import template

register = template.Library()

INSIGNIA_ESTADO = {
    'EN_PROCESO': 'insignia-proceso',
    'ATENDIDO': 'insignia-atendido',
    'ESCALADO': 'insignia-escalado',
    'FINALIZADO': 'insignia-finalizado',
}

PUNTO_ESTADO = {
    'EN_PROCESO': 'punto-proceso',
    'ATENDIDO': 'punto-atendido',
    'ESCALADO': 'punto-escalado',
    'FINALIZADO': 'punto-finalizado',
}

ETIQUETAS = (
    ('en proceso', 'EN_PROCESO'),
    ('atendid', 'ATENDIDO'),
    ('escalad', 'ESCALADO'),
    ('finalizad', 'FINALIZADO'),
)


def _codigo_de_estado(valor):
    """Acepta el código (EN_PROCESO) o la etiqueta ('En proceso') del estado."""
    if not valor:
        return ''
    texto = str(valor).strip()
    codigo = texto.upper().replace(' ', '_').replace('Á', 'A')
    if codigo in INSIGNIA_ESTADO:
        return codigo
    texto = texto.lower()
    for etiqueta, codigo in ETIQUETAS:
        if etiqueta in texto:
            return codigo
    return ''


@register.filter
def clase_insignia(valor):
    """Clase CSS de la insignia según el estado."""
    return INSIGNIA_ESTADO.get(_codigo_de_estado(valor), '')


@register.filter
def clase_punto(valor):
    """Clase CSS del punto de la línea de tiempo según el estado."""
    return PUNTO_ESTADO.get(_codigo_de_estado(valor), '')
