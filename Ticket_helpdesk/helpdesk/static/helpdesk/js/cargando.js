(function () {
  var overlay = document.querySelector('.cargando-overlay');

  function mostrarCarga() {
    document.body.classList.add('cargando');
    if (overlay) {
      overlay.setAttribute('aria-hidden', 'false');
    }
  }

  document.querySelectorAll('form[data-cargando]').forEach(function (form) {
    form.addEventListener('submit', function (evento) {
      if (form.dataset.cargandoEnviado === '1') {
        evento.preventDefault();
        return;
      }
      form.dataset.cargandoEnviado = '1';
      var boton = form.querySelector('button[type="submit"]');
      if (boton) {
        boton.disabled = true;
        boton.classList.add('boton-cargando');
      }
      mostrarCarga();
    });
  });

  // Enlaces que llevan a otra vista del servidor: también muestran la carga.
  document.querySelectorAll('a[data-cargando]').forEach(function (enlace) {
    enlace.addEventListener('click', function () {
      mostrarCarga();
    });
  });

  // Enlaces que descargan un archivo: la página no cambia, solo el botón gira.
  document.querySelectorAll('a[data-spin]').forEach(function (enlace) {
    enlace.addEventListener('click', function () {
      enlace.classList.add('boton-cargando');
      window.setTimeout(function () {
        enlace.classList.remove('boton-cargando');
      }, 2500);
    });
  });
})();
