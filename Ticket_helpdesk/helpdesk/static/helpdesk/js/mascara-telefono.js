(function () {
  function soloDigitos(valor) {
    return valor.replace(/\D/g, '');
  }

  function formatear(digitos) {
    if (digitos.length <= 3) { return digitos; }
    if (digitos.length <= 6) { return digitos.slice(0, 3) + ' ' + digitos.slice(3); }
    return digitos.slice(0, 3) + ' ' + digitos.slice(3, 6) + ' ' + digitos.slice(6, 10);
  }

  function aplicarMascara(input) {
    var digitos = soloDigitos(input.value).slice(0, 10);
    var texto = formatear(digitos);
    if (input.value !== texto) {
      input.value = texto;
      var posicion = texto.length;
      try { input.setSelectionRange(posicion, posicion); } catch (error) { }
    }
  }

  document.querySelectorAll('input.telefono').forEach(function (input) {
    aplicarMascara(input);
    input.addEventListener('input', function () { aplicarMascara(input); });
    input.addEventListener('blur', function () { aplicarMascara(input); });
  });
})();
