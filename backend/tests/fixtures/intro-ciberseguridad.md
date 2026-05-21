# Introducción a la Ciberseguridad Personal

Guía práctica para proteger tus cuentas, dispositivos y conexiones de red.

---

## 1. Autenticación de múltiples factores (2FA)

La autenticación de múltiples factores añade una segunda capa de verificación
más allá de la contraseña. Aunque un atacante robe tu contraseña, no podrá
entrar a tu cuenta sin el segundo factor.

**Cómo habilitarlo:**

- En Google: Cuenta → Seguridad → Verificación en dos pasos.
- En GitHub: Settings → Password and authentication → Two-factor authentication.
- Aplicaciones recomendadas: Google Authenticator, Aegis (Android), Raivo (iOS).

**Por qué importa:** el 80 % de las brechas de cuentas se habrían evitado
con 2FA activo, según informes de Microsoft Security.

---

## 2. Gestión de contraseñas

Usar la misma contraseña en varios sitios multiplica el daño de cualquier
filtración. Un gestor de contraseñas genera y almacena contraseñas largas
y únicas por sitio.

**Herramientas recomendadas:**

- **Bitwarden** (código abierto, gratis, auto-alojable): la mejor opción para
  usuarios que quieren transparencia. Extensión para Chrome/Firefox y app móvil.
- **KeePassXC** (local, sin nube): ideal si no quieres sincronización en línea.

**Contraseña maestra:** debe ser una frase de al menos cuatro palabras
aleatorias (p. ej. `luna-frío-castillo-postal`). No la reutilices en ningún
otro sitio.

---

## 3. Redes públicas de internet y VPN

Las redes Wi-Fi públicas (cafeterías, aeropuertos, hoteles) son peligrosas
porque cualquier persona en la misma red puede capturar tráfico no cifrado.

**Medidas mínimas en redes públicas:**

1. Visita solo sitios con HTTPS (candado verde en la barra de direcciones).
2. Evita acceder a banca en línea o cuentas críticas desde Wi-Fi público.
3. Desactiva la conexión automática a redes conocidas en tu móvil.

**Uso de VPN:**

Una red privada virtual (VPN) cifra todo tu tráfico entre tu dispositivo
y el servidor VPN antes de que salga a internet.

- **ProtonVPN**: opción recomendada. Código abierto, auditada
  independientemente, con plan gratuito sin límite de datos. Sede en Suiza
  (jurisdicción favorable a la privacidad). Disponible para Windows, macOS,
  Linux, Android e iOS.
- Se recomienda mantener la VPN activa siempre que uses redes públicas, y
  opcionalmente en casa si la privacidad frente al ISP es una preocupación.

> Nota: una VPN no te hace anónimo frente a los sitios web que visitas ni
> protege frente a malware descargado. Es una capa de protección del
> transporte, no una solución integral.

---

## 4. Actualizaciones del sistema operativo y apps

El vector más común de ataques reales es la explotación de vulnerabilidades
conocidas en software desactualizado.

**Regla práctica:** activar actualizaciones automáticas en el SO (Windows
Update, macOS Software Update, `apt`/`dnf` en Linux) y en el navegador.
Las actualizaciones de seguridad no son opcionales.

---

## 5. Phishing y ingeniería social

El phishing es el intento de engañarte para que entregues credenciales o
descargues malware haciéndose pasar por una entidad de confianza.

**Señales de alerta:**

- Urgencia artificial ("tu cuenta será suspendida en 24 h").
- Dirección del remitente que no coincide con el dominio oficial
  (p. ej. `soporte@g00gle.com` en vez de `google.com`).
- Enlace que al pasar el cursor apunta a un dominio diferente.

**Defensa:** ante cualquier duda, accede directamente al sitio escribiendo
la URL en el navegador, no desde el enlace del correo.

---

## Resumen de medidas prioritarias

| Medida | Esfuerzo | Impacto |
|--------|----------|---------|
| Activar 2FA en correo y redes sociales | Bajo | Muy alto |
| Adoptar gestor de contraseñas (Bitwarden) | Medio | Alto |
| Usar ProtonVPN en redes públicas | Bajo | Alto |
| Mantener SO y apps actualizados | Muy bajo | Alto |
| Reconocer señales de phishing | Bajo | Medio |
