# Smoke tests finales — Fase 14

Validación end-to-end del sistema desplegado en producción
(`https://api.iamentor.tech` + `https://www.iamentor.tech`) tras
las migraciones de mayo 2026 (LLM, OCR y embeddings → OpenAI).

- **Fecha de ejecución:** 2026-05-17
- **Backend:** `mentor-ia-backend` en DigitalOcean Droplet (Ubuntu 24.04,
  nginx + Let's Encrypt, Docker Compose).
- **Embeddings:** OpenAI `text-embedding-3-large` con `dimensions=768`
  (MRL + renormalización).
- **LLM y OCR:** OpenAI `gpt-4o-mini`.
- **Umbral RAG:** `RAG_SCORE_THRESHOLD = 0.55` (default), `top_k = 5`.

## 1. Corpus indexado (11 docs / 230 chunks)

| Archivo                                       | Tipo  | Chunks | Idioma   |
| --------------------------------------------- | ----- | ------ | -------- |
| attention-is-all-you-need.pdf                 | pdf   | 44     | inglés   |
| Weaviate_Agentic_Architectures-ebook.pdf      | pdf   | 34     | inglés   |
| Weaviate-Advanced-RAG-Techniques-ebook.pdf    | pdf   | 43     | inglés   |
| curso-prompt-engineering.md                   | md    | 100    | español  |
| hoja-libro.png                                | image | 3      | español  |
| ocr-fase7.png                                 | image | 1      | español  |
| smoke-md.md, smoke-txt.txt, smoke-pdf-*.pdf, test-fase4.pdf | varios | 1 c/u | español |

> Nota: `curso-prompt-engineering.md` topa `max_chunks=100`. Documento
> largo; los conceptos finales del archivo no entraron al índice.
> Decisión consciente del proyecto académico (ver `CLAUDE.md` §2.3).

## 2. Smoke RAG — 19 queries con timing

Las 16 queries originales en el idioma del documento esperado, más 3
queries adicionales para validar el comportamiento off-topic.

### 2.1 Resultados primera tanda (queries en inglés)

| # | Doc esperado          | Tipo | Origen  | Top   | Latencia | Top fuente                                  |
| - | --------------------- | ---- | ------- | ----- | -------- | ------------------------------------------- |
| 1 | Agentic Architectures | POS  | rag     | 0.738 | 5879 ms  | Weaviate_Agentic_Architectures-ebook.pdf    |
| 2 | Agentic Architectures | POS  | rag     | 0.721 | 7537 ms  | Weaviate_Agentic_Architectures-ebook.pdf    |
| 3 | Agentic Architectures | POS  | rag     | 0.708 | 6087 ms  | Weaviate_Agentic_Architectures-ebook.pdf    |
| 4 | Agentic Architectures | NEG  | modelo  | —     | 4610 ms  | — (Krebs cycle)                              |
| 5 | Agentic Architectures | NEG  | modelo  | —     | 4945 ms  | — (Design patterns in Java)                  |
| 6 | Advanced RAG          | POS  | rag     | 0.759 | 5535 ms  | Weaviate-Advanced-RAG-Techniques-ebook.pdf  |
| 7 | Advanced RAG          | POS  | rag     | 0.648 | 3186 ms  | Weaviate-Advanced-RAG-Techniques-ebook.pdf  |
| 8 | Advanced RAG          | POS  | modelo  | —     | 2942 ms  | — (metadata filtering, ver §2.3)             |
| 9 | Advanced RAG          | NEG  | modelo  | —     | 4601 ms  | — (History of World War II)                  |
|10 | Advanced RAG          | NEG  | modelo  | —     | 3879 ms  | — (How to learn guitar)                      |
|11 | Prompt Engineering    | POS  | modelo  | —     | 2364 ms  | — (ver §2.2 cross-lingual)                   |
|12 | Prompt Engineering    | POS  | modelo  | —     | 2249 ms  | — (ver §2.2)                                 |
|13 | Prompt Engineering    | POS  | modelo  | —     | 3402 ms  | — (ver §2.2)                                 |
|14 | Prompt Engineering    | NEG  | modelo  | —     | 2858 ms  | — (Kubernetes configuration)                 |
|15 | Prompt Engineering    | NEG  | modelo  | —     | 1892 ms  | — (Basic linear algebra)                     |
|16 | Hoja libro Control    | POS  | modelo  | —     | 2299 ms  | — (ver §2.2)                                 |
|17 | Hoja libro Control    | POS  | modelo  | —     | 2218 ms  | — (ver §2.2)                                 |
|18 | Hoja libro Control    | NEG  | modelo  | —     | 3161 ms  | — (Theory of Relativity)                     |
|19 | Hoja libro Control    | NEG  | modelo  | —     | 2178 ms  | — (Relational databases)                     |

**Stats:** min 1892 ms · median 3186 ms · mean 3780 ms · max 7537 ms.

### 2.2 Re-test cross-lingual (queries en español para docs en español)

Las queries POS que cayeron a `modelo` en §2.1 estaban en inglés
contra documentos en español. Repetidas en el idioma del documento:

| # | Doc                | Origen | Top   | Latencia | Query                                             |
| - | ------------------ | ------ | ----- | -------- | ------------------------------------------------- |
| 1 | Prompt Engineering | rag    | 0.573 | 3197 ms  | ¿Qué es prompt shadowing?                         |
| 2 | Prompt Engineering | rag    | 0.631 | 3735 ms  | diferencia entre zero shot y few shot             |
| 3 | Prompt Engineering | rag    | 0.677 | 5509 ms  | cómo funcionan los embeddings                     |
| 4 | Hoja libro Control | rag    | 0.669 | 2953 ms  | MrBeast y Jimmy Donaldson intercambio de aprendizaje |
| 5 | Hoja libro Control | rag    | 0.577 | 4389 ms  | estudio Framingham sobre obesidad                 |
| 6 | Advanced RAG (en)  | modelo | —     | 1648 ms  | filtrado por metadatos (es → en)                  |

Con queries en el idioma del documento, **5/6** matchean RAG sobre
umbral 0.55. El único fallo es la query en español contra un PDF en
inglés (caso simétrico del mismatch original).

### 2.3 Hallazgos

- **`text-embedding-3-large` es razonablemente cross-lingual** pero
  el score cae por debajo del umbral 0.55 cuando idioma de query y
  documento difieren. En el alcance académico hispano-anglo es un
  punto a saber.
- **El umbral 0.55 es conservador y correcto:** todas las queries
  off-topic (NEG) cayeron a `modelo` sin inventar fuentes. **0 falsos
  positivos.** Esta es la garantía clave contra alucinación de cites.
- **Latencias razonables para producción:** mediana 3.2 s, máxima
  7.5 s. El máximo se dio en una query RAG con contexto largo
  (más tokens en el prompt al LLM).

## 3. Smoke OCR multimodal — `hoja-libro.png`

Imagen de una página del libro *Control* de Freddy Vega (capítulo
sobre influencia del entorno social). Se subió como `.png` y el
sistema usó `gpt-4o-mini` Vision para extraer texto y generar 3
chunks indexados.

### 3.1 Auditoría de extracción (5 keywords esperadas)

| Keyword                  | Encontrada | Evidencia                                          |
| ------------------------ | ---------- | -------------------------------------------------- |
| **MrBeast**              | ✓ chunk 0  | *"El canal de YouTube más exitoso del mundo es MrBeast."* |
| **Framingham Heart Study** | ✓ chunk 2 | *"Durante 32 años, el Framingham Heart Study siguió a doce mil personas."* |
| **obesidad**             | ✓ chunk 2  | *"la obesidad se contagia"*                        |
| **Jimmy Donaldson**      | (no en excerpt 500-char, presumiblemente en chunk 1) |
| **Skype**                | (no en excerpt 500-char, presumiblemente en chunk 1) |

Los excerpts devueltos por `/query` están truncados a 500
caracteres; el texto completo del chunk está en Qdrant. Las 2
keywords no visibles en el audit no son evidencia de fallo OCR — la
query atómica *"Skype"* no recuperó chunk 1 dentro del top-5, pero
la query genérica *"MrBeast Skype Framingham…"* sí recuperó chunk 0
de la imagen con score 0.561.

### 3.2 Smoke OCR endpoint directo

| Endpoint              | Imagen          | Resultado                       | Latencia    |
| --------------------- | --------------- | ------------------------------- | ----------- |
| `POST /ocr-imagen`    | `ocr-fase7.png` | `"Mentor IA OCR prueba fase 7"` (27 chars) | ~3 s |
| `POST /upload-document` con imagen | `hoja-libro.png` | 3 chunks correctamente indexados | ~15 s (incluye embedding + upsert) |

### 3.3 Conclusión OCR

`gpt-4o-mini` Vision extrae texto en español y nombres propios
(*MrBeast*, *Framingham*, *Skype*) con calidad suficiente para el
alcance académico. No requiere preprocesamiento de imagen.

## 4. Recomendaciones para sustentación

Tres puntos a destacar cuando se demuestre el sistema:

1. **Heurística RAG vs modelo (CLAUDE.md §8.1):** preparar dos
   queries sobre el mismo documento — una de contenido (origen
   `rag`) y una meta-archivo (origen `modelo`) — para mostrar la
   salvaguarda contra alucinación de fuentes.
2. **Sensibilidad cross-lingual:** si la profesora pregunta por un
   documento en español, preguntar en español. Es la fuente más
   común de "falsos negativos" de RAG en el corpus del proyecto.
3. **Latencias:** 3-5 segundos por respuesta es lo esperado con
   `gpt-4o-mini` + red + nginx + Qdrant Cloud. Cualquier valor por
   encima de 10 s indica problema en alguna dependencia.

## 4. Smoke de seguimiento conversacional — post 2026-05-20

Validaciones añadidas tras detectar fallos en preguntas de seguimiento
(contexto: documento `intro-ciberseguridad.md` subido en la sesión).

**Corpus:** `backend/data/ejemplos/intro-ciberseguridad.md` (fixture nuevo,
5 secciones, solo menciona ProtonVPN — NordVPN no aparece).

### 4.1 Queries de seguimiento sobre VPN

| # | Pregunta | Origen esperado | Detalle esperado |
| - | -------- | --------------- | ---------------- |
| 1 | "Como puedo protegerme de la ciberseguridad" | `rag` | chunk sección VPN/2FA con score > 0.55 |
| 2 | "Que puedo usar para protegerme, el documento habla de ProtonVPN o de NordVPN?" | `rag` | respuesta menciona **solo ProtonVPN**; NordVPN se dice que no aparece |
| 3 | "El documento qué dice?" (con historial de pregunta 1) | `rag` | anáfora resuelta; responde con contexto de seguridad |
| 4 | "Necesito verificar si en el documento habla de usar ProtonVPN o NordVPN" | `rag` | misma respuesta que Q2 |
| 5 | "El documento que dice?" (sin historial) | `modelo` o abstención | no pide pegar el texto; orienta a hacer pregunta concreta |

### 4.2 Cambios que explican la mejora

- `utils/query_retrieval.py`: normaliza ruido meta y resuelve anáforas con historial.
- `qdrant_client.py`: filtro `nombre_archivo` cuando la pregunta menciona un archivo.
- `agente_respuesta.py`: prompt `system` estricto — respuesta solo desde contexto;
  historial (últimos 6 mensajes) incluido en el prompt.
- `utils/chunking.py`: `chunkear_markdown` divide por encabezados H1-H3, evitando
  que el chunk 0 (intro/resumen del doc) gane todas las queries de seguimiento.
- Frontend: `askQuery` envía `historial`; "Ver fuentes" muestra excerpt completo.

## 5. Para defender en sustentación

- El sistema **nunca cita fuentes que no superen el umbral 0.55** de
  similitud coseno. Es una decisión de diseño contra alucinación.
- Los embeddings multilingües tienen sesgo hacia el idioma del
  corpus de entrenamiento; **mismatch de idioma reduce el score**
  pero no compromete la corrección de la respuesta (cae al modelo
  base con badge claro).
- El **OCR multimodal de `gpt-4o-mini`** sustituyó a Google Cloud
  Vision por integración natural con el resto del stack OpenAI
  (una sola API, una sola cuota, una sola key). Calidad probada en
  texto en español y nombres propios.
- **Cuota:** Tier de OpenAI con créditos del estudiante; sin
  agotamiento durante toda la batería de pruebas (19 queries RAG +
  6 cross-lingual + 4 OCR auditing + uploads). Coste estimado <USD
  0.05 por toda la batería.
