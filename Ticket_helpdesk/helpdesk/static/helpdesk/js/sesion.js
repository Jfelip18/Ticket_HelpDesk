(function () {
  var cuerpo = document.body;
  if (!cuerpo) {
    return;
  }

  var urlPing = cuerpo.dataset.sesionPing;
  if (!urlPing) {
    return;
  }

  var urlSalir = cuerpo.dataset.sesionSalir;
  var urlIngresar = cuerpo.dataset.sesionIngresar;
  var limite = (parseInt(cuerpo.dataset.sesionLimite, 10) || 240) * 1000;
  var ventanaAviso = (parseInt(cuerpo.dataset.sesionAviso, 10) || 60) * 1000;
  var activa = cuerpo.dataset.sesionActiva === '1';

  var INTERVALO_PING = 30000;
  var INTERVALO_REVISION = 15000;

  var ultimaActividad = Date.now();
  var ultimoPing = 0;
  var avisoVisible = false;
  var cerrada = false;

  var modal = document.getElementById('modal-sesion');
  var cuenta = document.getElementById('sesion-cuenta');
  var botonRenovar = document.getElementById('sesion-renovar');

  function tokenCsrf() {
    var partes = (document.cookie || '').split(';');
    for (var i = 0; i < partes.length; i++) {
      var par = partes[i].trim();
      if (par.indexOf('csrftoken=') === 0) {
        return decodeURIComponent(par.substring('csrftoken='.length));
      }
    }
    var campo = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return campo ? campo.value : '';
  }

  function irAlIngreso() {
    if (urlIngresar) {
      window.location.href = urlIngresar + '?sesion=cerrada';
    } else {
      window.location.reload();
    }
  }

  function cerrarSesion() {
    if (cerrada) {
      return;
    }
    cerrada = true;
    ocultarAviso();
    var solicitud = fetch(urlSalir, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {'X-CSRFToken': tokenCsrf(), 'X-Requested-With': 'XMLHttpRequest'}
    });
    if (solicitud && solicitud.catch) {
      solicitud.catch(function () { });
    }
    window.setTimeout(irAlIngreso, 250);
  }

  function ping(forzar) {
    if (cerrada) {
      return;
    }
    var ahora = Date.now();
    if (!forzar && ahora - ultimoPing < INTERVALO_PING) {
      return;
    }
    ultimoPing = ahora;
    fetch(urlPing, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {'X-CSRFToken': tokenCsrf(), 'X-Requested-With': 'XMLHttpRequest'}
    }).then(function (respuesta) {
      if (activa && (respuesta.status === 401 || respuesta.status === 403)) {
        // La sesión ya no existe en el servidor: hay que volver a ingresar.
        cerrada = true;
        irAlIngreso();
      }
    }).catch(function () { });
  }

  function mostrarAviso() {
    if (!modal || avisoVisible) {
      return;
    }
    avisoVisible = true;
    modal.hidden = false;
    document.body.classList.add('sin-scroll');
    actualizarCuenta();
  }

  function ocultarAviso() {
    if (!modal || !avisoVisible) {
      return;
    }
    avisoVisible = false;
    modal.hidden = true;
    document.body.classList.remove('sin-scroll');
  }

  function actualizarCuenta() {
    if (!cuenta) {
      return;
    }
    var restante = Math.max(0, Math.ceil((limite - (Date.now() - ultimaActividad)) / 1000));
    cuenta.textContent = String(restante);
  }

  function marcarActividad() {
    // Mientras el aviso de sesión está visible, solo el botón "Renovar
    // sesión" puede cerrarlo: mover el mouse no renueva la sesión.
    if (avisoVisible) {
      return;
    }
    ultimaActividad = Date.now();
    ocultarAviso();
    ping(false);
  }

  function revisar() {
    if (document.hidden) {
      // En segundo plano el navegador estrangula los temporizadores:
      // el servidor es quien cierra la sesión por inactividad.
      return;
    }
    var inactivo = Date.now() - ultimaActividad;
    if (activa) {
      if (inactivo >= limite) {
        cerrarSesion();
        return;
      }
      if (inactivo >= limite - ventanaAviso) {
        mostrarAviso();
      } else {
        ocultarAviso();
      }
    }
    if (inactivo < INTERVALO_PING) {
      ping(false);
    }
  }

  ['mousemove', 'keydown', 'click', 'scroll', 'touchstart'].forEach(function (evento) {
    document.addEventListener(evento, marcarActividad, {passive: true});
  });

  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) {
      revisar();
    }
  });

  if (botonRenovar) {
    botonRenovar.addEventListener('click', function () {
      ultimaActividad = Date.now();
      ocultarAviso();
      ping(true);
    });
  }

  window.setInterval(revisar, INTERVALO_REVISION);
  window.setInterval(function () {
    if (avisoVisible) {
      actualizarCuenta();
    }
  }, 1000);
})();
