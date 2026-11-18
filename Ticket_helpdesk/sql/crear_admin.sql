-- ============================================================================
--  Crear el usuario administrador del Help Desk
-- ============================================================================
--  Este script lo ejecutas TÚ en tu base de datos (Neon / SQL Editor).
--
--  El acceso al panel (/panel/) se decide SOLO por el rol del usuario:
--  helpdesk_usuario.tipo = 'ADMIN'. Por eso la cuenta de abajo queda con
--  is_staff = false e is_superuser = false: así NADIE puede entrar al admin
--  de Django (/admin/), el Help Desk se maneja solo desde /panel/.
--
--  PASO 1 - Genera el hash de la contraseña (copia el resultado):
--
--      python manage.py shell -c "from django.contrib.auth.hashers import make_password; print(make_password('TU_CLAVE_AQUI'))"
--
--  PASO 2 - Reemplaza <HASH> (y 'admin' si usas otro nombre de usuario) y
--            ejecuta este script completo.
-- ============================================================================

-- 1) Cuenta de acceso (tabla de autenticación de Django)
--    is_staff / is_superuser en false = sin acceso al admin de Django.
INSERT INTO auth_user (
    password, is_superuser, is_staff, is_active, date_joined,
    username, first_name, last_name, email
)
VALUES (
    'pbkdf2_sha256$1500000$LxUcY3tnZXhSZ7pmRJal1i$VRb5Q7CXN/kmn/QNwd6Wyzk6b7pPkZqf/8nclu5EJMM=
', false, false, true, NOW(),
    'admin', 'Administrador', 'Help Desk', 'admin@local'
);

-- 2) Ficha del administrador en la tabla de usuarios de la aplicación.
--    tipo = 'ADMIN' es lo que le da acceso al panel /panel/.
INSERT INTO helpdesk_usuario (
    cuenta_id, nombre, apellido, direccion, telefono, tipo, creado_en, actualizado_en
)
SELECT
    id,
    'Administrador',
    'Help Desk',
    'Sede principal',
    '3000000000',
    'ADMIN',
    NOW(),
    NOW()
FROM auth_user
WHERE username = 'admin';

-- 3) Verificación: debe aparecer tipo = ADMIN y is_staff = false
SELECT
    u.id,
    u.username,
    u.is_staff,
    u.is_superuser,
    u.is_active,
    h.tipo,
    h.telefono
FROM auth_user u
LEFT JOIN helpdesk_usuario h ON h.cuenta_id = u.id
WHERE u.username = 'admin';
