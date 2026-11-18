(function () {
  var menus = document.querySelectorAll('.menu-usuario');
  if (!menus.length) {
    return;
  }

  function cerrarTodos(excepto) {
    menus.forEach(function (menu) {
      if (menu !== excepto) {
        menu.open = false;
      }
    });
  }

  menus.forEach(function (menu) {
    menu.addEventListener('toggle', function () {
      if (menu.open) {
        cerrarTodos(menu);
      }
    });
  });

  document.addEventListener('click', function (evento) {
    menus.forEach(function (menu) {
      if (menu.open && !menu.contains(evento.target)) {
        menu.open = false;
      }
    });
  });

  document.addEventListener('keydown', function (evento) {
    if (evento.key === 'Escape') {
      cerrarTodos(null);
    }
  });
})();
