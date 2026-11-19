(function () {
  var boton = document.querySelector('[data-ver-clave]');
  var campo = document.querySelector('input[name="password"]');
  if (!boton || !campo) {
    return;
  }

  var iconoVer = boton.querySelector('[data-icono-ver]');
  var iconoOcultar = boton.querySelector('[data-icono-ocultar]');

  boton.addEventListener('click', function () {
    var mostrar = campo.type === 'password';
    campo.type = mostrar ? 'text' : 'password';
    boton.setAttribute('aria-label', mostrar ? 'Ocultar contraseña' : 'Mostrar contraseña');
    boton.setAttribute('aria-pressed', mostrar ? 'true' : 'false');
    if (iconoVer && iconoOcultar) {
      iconoVer.hidden = mostrar;
      iconoOcultar.hidden = !mostrar;
    }
    campo.focus();
  });
})();
