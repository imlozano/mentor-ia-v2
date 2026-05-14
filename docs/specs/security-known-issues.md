# Vulnerabilidades de seguridad conocidas

> Registro vivo de CVEs detectados por las herramientas de auditoría del
> proyecto (`uv run pip-audit` en backend; `pnpm audit` cuando exista
> código en `frontend/`) que han sido analizados, clasificados como no
> aplicables al contexto de Mentor IA y aceptados temporalmente bajo el
> cooldown de cadena de suministro.
>
> Última actualización: 2026-05-14.

---

## 1. Política de gestión de vulnerabilidades

El proyecto adopta una política simple y defendible:

- **Severidad High o Critical:** bloqueante. Se prioriza el upgrade y se
  considera excepción puntual al cooldown si el fix está dentro de la
  ventana de 7 días.
- **Severidad Moderate o Low:** análisis caso por caso. Si tras el
  análisis se concluye que la vulnerabilidad no aplica al contexto del
  sistema (uso, superficie de ataque, vectores), se documenta en este
  archivo con su análisis y se programa una fecha de re-auditoría.

Las mismas reglas aplican al backend (`uv run pip-audit`) y al frontend
(`pnpm audit`, una vez exista código en `frontend/`).

---

## 2. CVEs conocidos no aplicables (a fecha 2026-05-14)

### 2.1 CVE-2026-44431 — `urllib3` <2.7.0 — header leak en cross-origin redirects

| Campo                                | Valor                                                              |
| ------------------------------------ | ------------------------------------------------------------------ |
| Identificador                        | CVE-2026-44431 (alias GHSA-qccp-gfcp-xxvc)                         |
| Paquete                              | `urllib3` 2.6.3 (transitive de `google-genai`, `qdrant-client`, `httpx`) |
| Severidad GHSA                       | Moderate                                                           |
| Fix disponible                       | `urllib3` 2.7.0                                                    |
| Publicación de urllib3 2.7.0 en PyPI | 2026-05-07 a las 16:13 UTC                                         |
| Fin del cooldown de 7 días           | 2026-05-14 a las 16:13 UTC                                         |
| Re-auditoría programada              | 2026-05-15 o posterior                                             |

**Descripción del CVE.** En cross-origin redirects seguidos vía la API
de bajo nivel
`ProxyManager.connection_from_url().urlopen(..., assert_same_host=False)`,
los headers sensibles (`Authorization`, `Cookie`,
`Proxy-Authorization`) no se eliminan, mientras que sí se eliminan al
usar las APIs de alto nivel `urllib3.request()`,
`PoolManager.request()` y `ProxyManager.request()`.

**Por qué no aplica a Mentor IA.** El backend no instancia
`ProxyManager`, no usa la API de bajo nivel
`connection_from_url().urlopen()` y no sigue redirects cross-origin con
`assert_same_host=False`. `urllib3` entra solo como dependencia
transitive de `google-genai`, `qdrant-client` y `httpx`; las tres
librerías construyen sus clientes HTTP sobre APIs de alto nivel, que sí
eliminan los headers sensibles en redirects.

---

### 2.2 CVE-2026-44432 — `urllib3` <2.7.0 — consumo excesivo de recursos en streaming con decompresión

| Campo                                | Valor                                                              |
| ------------------------------------ | ------------------------------------------------------------------ |
| Identificador                        | CVE-2026-44432 (alias GHSA-mf9v-mfxr-j63j)                         |
| Paquete                              | `urllib3` 2.6.3 (transitive de `google-genai`, `qdrant-client`, `httpx`) |
| Severidad GHSA                       | Moderate                                                           |
| Fix disponible                       | `urllib3` 2.7.0                                                    |
| Publicación de urllib3 2.7.0 en PyPI | 2026-05-07 a las 16:13 UTC                                         |
| Fin del cooldown de 7 días           | 2026-05-14 a las 16:13 UTC                                         |
| Re-auditoría programada              | 2026-05-15 o posterior                                             |

**Descripción del CVE.** Al consumir respuestas HTTP comprimidas con
`Content-Encoding: br|gzip|zstd|deflate` mediante la API de streaming
de urllib3, ciertos flujos (segunda llamada a
`HTTPResponse.read(amt=N)` con respuesta Brotli decodificada por la
librería oficial `brotli`, o llamada a `HTTPResponse.drain_conn()` tras
lectura parcial) decodifican toda la respuesta en lugar del trozo
solicitado, generando consumo excesivo de CPU y memoria (CWE-409).

**Por qué no aplica a Mentor IA.** El backend solo realiza requests
HTTP salientes a cuatro endpoints confiables y bajo control conocido:
Gemini, Qdrant Cloud, Google Cloud Vision y Make.com. No consume
respuestas comprimidas desde fuentes no confiables. No usa
`HTTPResponse.drain_conn()` ni la librería oficial `brotli` (no es
dependencia directa ni transitive del proyecto).

---

### 2.3 Estado al momento de cerrar Fase 1

| Campo                            | Valor                                                              |
| -------------------------------- | ------------------------------------------------------------------ |
| Commit que cierra Fase 1         | `3d1de8e2609b3bf8287707568761ed5ef19f7db7` (short: `3d1de8e`)       |
| Fecha y hora del commit          | 2026-05-14 a las 14:26 UTC                                         |
| Resolución actual de uv          | `urllib3` 2.6.3                                                    |
| Estado del cooldown              | Activo (vence a las 16:13 UTC del mismo día)                       |

El cooldown todavía protege en el momento del commit. `uv` resolverá
`urllib3` 2.7.0 automáticamente la próxima vez que se ejecute
`uv sync` o `uv lock --upgrade` después de las 16:13 UTC del
2026-05-14, sin necesidad de modificar `pyproject.toml`.

---

## 3. Procedimiento de re-auditoría

Cuando se sabe (o se sospecha) que un fix listado en este archivo ya
está fuera del cooldown:

1. Ejecutar `uv lock --upgrade-package <paquete>` para forzar la
   resolución del fix.
2. Ejecutar `uv sync` para aplicar el nuevo lock al venv.
3. Ejecutar `uv run pip-audit` y verificar que los CVEs desaparecen
   del reporte.
4. Actualizar este archivo:
   - Mover la entrada de la sección "CVEs conocidos no aplicables" a
     una nueva sección "Histórico de CVEs resueltos" al final del
     documento, registrando la fecha de resolución y el commit que
     introdujo el fix.
5. Commitear el cambio en `uv.lock` y en este archivo en el mismo
   commit, con mensaje del tipo
   `chore: actualiza <paquete> a <version>, resuelve CVE-...`.

La re-auditoría sistemática del árbol de dependencias se ejecuta como
parte de la **Fase 14** (smoke tests finales) del plan de
implementación.

---

## 4. Para defender en sustentación

1. **El cooldown de 7 días es protección, no negligencia.** La defensa
   de cadena de suministro (`exclude-newer = "7 days"` en uv y
   `minimumReleaseAge: 1440` en pnpm) está diseñada para mitigar
   ataques tipo Shai-Hulud 2.0 y LiteLLM/Telnyx, donde versiones
   maliciosas se publican y suelen ser retiradas en horas o días. El
   coste documentado es que también retrasa fixes legítimos de CVEs
   moderadas durante esa ventana. Aceptar ese coste por escrito es
   parte de la postura de seguridad, no un descuido.

2. **El análisis caso por caso evita teatro de seguridad.** Bumpear
   una dependencia para "limpiar" `pip-audit` sin entender si la
   vulnerabilidad aplica al sistema es reactivo y no informa. El
   análisis por contexto de las dos CVEs de `urllib3` documentadas
   aquí demuestra que el backend no expone las superficies de ataque
   afectadas (no usa `ProxyManager` low-level, no consume responses
   comprimidas desde fuentes no confiables).

3. **El sistema de re-auditoría es automático y verificable.** Pasado
   el cooldown (16:13 UTC del 2026-05-14 en este caso), `uv sync`
   resolverá la versión con fix sin intervención manual. La Fase 14
   del plan de implementación incluye una re-auditoría sistemática
   para mover los CVEs resueltos al histórico de este archivo.

---

_Última actualización: 2026-05-14._
