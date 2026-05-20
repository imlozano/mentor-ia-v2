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

No hay CVEs Moderate/Low activos documentados como "no aplicables"
después de actualizar `urllib3` a `2.7.0` y re-ejecutar
`uv run pip-audit` el 2026-05-14.

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

## 4.bis Endurecimiento de producción (Sprint 1 — 2026-05-20)

Cambios aplicados para blindar el despliegue público (`api.iamentor.tech`)
sin introducir autenticación (CLAUDE.md §2.1):

- **Rate limiting** (`slowapi`) en `/query`, `/upload-document`, `/plan-repaso`
  y `/ocr-imagen`, por IP + `X-Session-ID`. Configurable por env
  (`RATE_LIMIT_*`). Mitiga el abuso de coste de créditos OpenAI.
- **Aislamiento por `session_id` anónimo**: el frontend genera un UUIDv4 y lo
  envía en `X-Session-ID`. Los documentos, consultas y planes se filtran por
  ese id en Qdrant; los documentos sin `session_id` (legacy) quedan aislados.
- **Tope de páginas OCR** (`OCR_PDF_MAX_PAGES`, default 20) para PDFs
  escaneados: evita cientos de llamadas a OpenAI Vision por un solo archivo.
- **Validación uniforme de archivos** (extensión y tamaño, incl. TXT/MD) y
  `max_tokens` acotados en todas las llamadas OpenAI.
- `source_path` deja de exponerse en `/documentos-indexados`.

Pendiente (Sprint 2): política de retención/borrado de archivos subidos,
unificación del plan en una sola llamada LLM, `pnpm audit` bloqueante.

## 5. Histórico de CVEs resueltos

### 5.1 CVE-2026-44431 — `urllib3` header leak en redirects cross-origin

| Campo                           | Valor                                                           |
| ------------------------------- | --------------------------------------------------------------- |
| Identificador                   | CVE-2026-44431 (GHSA-qccp-gfcp-xxvc)                           |
| Dependencia afectada            | `urllib3` `<2.7.0`                                              |
| Estado                          | Resuelto                                                        |
| Acción aplicada                 | Upgrade a `urllib3==2.7.0` (`uv lock --upgrade-package urllib3`) |
| Verificación                    | `uv run pip-audit`: sin vulnerabilidades conocidas              |
| Fecha resolución (UTC)          | 2026-05-14                                                      |

### 5.2 CVE-2026-44432 — `urllib3` consumo excesivo en streaming+decompress

| Campo                           | Valor                                                           |
| ------------------------------- | --------------------------------------------------------------- |
| Identificador                   | CVE-2026-44432 (GHSA-mf9v-mfxr-j63j)                           |
| Dependencia afectada            | `urllib3` `<2.7.0`                                              |
| Estado                          | Resuelto                                                        |
| Acción aplicada                 | Upgrade a `urllib3==2.7.0` (`uv lock --upgrade-package urllib3`) |
| Verificación                    | `uv run pip-audit`: sin vulnerabilidades conocidas              |
| Fecha resolución (UTC)          | 2026-05-14                                                      |

---

_Última actualización: 2026-05-14._
