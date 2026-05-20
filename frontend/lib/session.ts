/**
 * Identificador de sesión anónimo.
 *
 * Mentor IA no tiene login ni cuentas (CLAUDE.md §2.1). Para que los
 * documentos, consultas y planes de cada visitante no se mezclen, el
 * navegador genera un UUIDv4 anónimo y lo persiste en localStorage. El
 * backend lo recibe en el header `X-Session-ID` y lo usa solo como clave
 * de aislamiento en Qdrant — no identifica a ninguna persona.
 */

const STORAGE_KEY = "mentor_ia_session_id";

function generateId(): string {
  // crypto.randomUUID está disponible en todos los navegadores modernos.
  return crypto.randomUUID();
}

/**
 * Devuelve el session_id del navegador, creándolo y persistiéndolo la
 * primera vez. En contextos sin `window` (SSR) devuelve un id efímero.
 */
export function getSessionId(): string {
  if (typeof window === "undefined") {
    return generateId();
  }
  try {
    let id = window.localStorage.getItem(STORAGE_KEY);
    if (!id) {
      id = generateId();
      window.localStorage.setItem(STORAGE_KEY, id);
    }
    return id;
  } catch {
    // localStorage bloqueado (modo privado estricto): id efímero por carga.
    return generateId();
  }
}
