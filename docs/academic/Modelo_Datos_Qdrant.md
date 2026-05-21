# Modelo de datos vectorial — Mentor IA (Qdrant)

> Documento técnico de diseño del modelo de datos vectorial para Mentor
> IA. Describe el estado actual del esquema, la configuración de la
> colección, la estrategia de chunking, el payload de cada punto y las
> limitaciones identificadas, junto con un diseño propuesto de mejora
> documentado como trabajo futuro.
>
> Versión: 3.0 · Fecha: 2026-05-17.

---

## Tabla de contenidos

1. [Estado actual del esquema](#1-estado-actual-del-esquema)
2. [Configuración de la colección Qdrant](#2-configuración-de-la-colección-qdrant)
3. [Estrategia de chunking](#3-estrategia-de-chunking)
4. [Payload de cada punto](#4-payload-de-cada-punto)
5. [Limitaciones identificadas](#5-limitaciones-identificadas)
6. [Diseño propuesto de mejora](#6-diseño-propuesto-de-mejora)
7. [Para defender en sustentación](#7-para-defender-en-sustentación)

---

## 1. Estado actual del esquema

La siguiente tabla resume el estado actual del modelo de datos vectorial
en el sistema, tal como está implementado en
`backend/src/services/openai_service.py` y
`backend/src/agentes/agente_extraccion.py`.

| Aspecto                       | Valor actual                                                            |
| ----------------------------- | ----------------------------------------------------------------------- |
| Colección                     | `mentor_ia_aprendizaje` (configurable vía env `QDRANT_COLLECTION`)       |
| Dimensión del vector          | 768                                                                     |
| Distancia                     | COSINE                                                                  |
| Modelo de embeddings          | OpenAI `text-embedding-3-large` con `dimensions=768` (MRL nativo + renormalización) |
| Tamaño de chunk               | 900 caracteres                                                          |
| Solape entre chunks           | 150 caracteres                                                          |
| Máximo de chunks por documento | 100                                                                    |
| Tipos de fuente soportados    | PDF (`pypdf`), PDF escaneado (`pypdfium2` + OpenAI Vision), imagen PNG/JPG (OpenAI Vision), texto plano (`.txt`/`.md`) |
| Identificador del punto       | UUIDv5 determinístico desde `source_path \| chunk_index`                |
| Índices de payload            | Ninguno (búsquedas son globales sin filtros activos)                    |
| Filtros aplicados en búsqueda | Ninguno (búsqueda global sobre toda la colección)                       |

El sistema está diseñado como instancia única para un solo usuario. No
existen conceptos de propietario del documento, curso, asignatura ni
control de acceso, porque están fuera del alcance académico (ver
[`Documento_Tecnico.md`](./Documento_Tecnico.md), sección 3).

---

## 2. Configuración de la colección Qdrant

### 2.1 Parámetros de la colección

La colección se crea con la siguiente configuración:

```python
client.create_collection(
    collection_name="mentor_ia_aprendizaje",
    vectors_config=VectorParams(
        size=768,
        distance=Distance.COSINE,
    ),
)
```

### 2.2 Justificación de la dimensión 768

La dimensión 768 es una **decisión de diseño anclada al sistema** que
se preservó a lo largo de tres migraciones de modelo de embeddings
(ver [`Documento_Tecnico.md`](./Documento_Tecnico.md) §6.7 para la
cronología). Hoy el modelo es OpenAI `text-embedding-3-large`, cuya
salida nativa es de 3072 dimensiones; la dimensión 768 se conserva
mediante el parámetro `dimensions=768`, que aplica **Matryoshka
Representation Learning (MRL)** para truncar el vector preservando su
calidad semántica.

Mantener 768 (en lugar de migrar a 3072 nativos) responde a tres
razones: compatibilidad con la colección Qdrant ya configurada,
eficiencia operativa (vectores 4× más pequeños) y calidad equivalente
gracias a MRL.

Esto tiene una consecuencia de diseño importante: la dimensión está
acoplada a la **configuración** del modelo de embeddings. Cambiar a un
modelo con `dimensions` no soportadas o a otra familia obligaría a
borrar la colección y re-indexar el corpus. Por eso el payload incluye
`embedding_model` y `embedding_dim` (ver §4): permiten auditar con qué
modelo se generó cada vector y planificar migraciones futuras.

**Nota operativa.** Tras truncar con MRL, los vectores no quedan
normalizados a norma 1 (efecto observado tanto en Gemini como en
OpenAI). Como la métrica COSINE en Qdrant trabaja idealmente sobre
vectores unitarios, `OpenAIService.embed_texts` aplica una
renormalización explícita antes de devolver los vectores. Sin ese
paso, la métrica COSINE se degrada y los scores de búsqueda se vuelven
inestables.

### 2.3 Justificación de la distancia COSINE

La distancia coseno mide la similitud de **dirección** entre dos
vectores, ignorando su magnitud. Para embeddings de texto esto es lo
deseable porque:

- Los embeddings semánticos codifican el significado en la **dirección**
  del vector, no en su tamaño.
- COSINE es la métrica recomendada para embeddings semánticos por la
  literatura general de RAG y por las guías oficiales tanto de Google
  Gemini como de OpenAI.
- Los vectores se renormalizan a norma 1 en
  `services/openai_service.py` tras el truncamiento MRL (con
  `dimensions=768` la salida cruda no está unitarizada), así que
  COSINE y producto punto dan resultados equivalentes; pero COSINE es
  más legible al interpretarse como similitud entre 0 y 1.

Alternativas evaluadas y descartadas:

- **Distancia euclidiana**: sensible a la magnitud, lo cual no aporta
  información útil cuando los vectores están normalizados.
- **Producto punto**: equivalente a COSINE con vectores normalizados,
  pero menos legible en los logs (el rango no está acotado entre 0 y 1).

---

## 3. Estrategia de chunking

### 3.1 Parámetros del chunking

El chunking se realiza en
`mentor-ia-aprendizaje/src/agentes/agente_extraccion.py` con tres
parámetros:

| Parámetro      | Valor | Significado                                          |
| -------------- | ----- | ---------------------------------------------------- |
| `max_chars`    | 900   | Tamaño máximo de cada chunk en caracteres            |
| `overlap`      | 150   | Caracteres de solape entre chunks consecutivos        |
| `max_chunks`   | 100   | Tope máximo de chunks generados por documento         |

### 3.2 Justificación del tamaño 900

La elección de 900 caracteres responde a un balance entre dos fuerzas
opuestas:

- **Chunks pequeños** (200–400 caracteres) generan respuestas más
  precisas porque cada chunk es muy específico, pero pierden contexto:
  un chunk puede contener una oración sin la frase anterior que la
  introduce.
- **Chunks grandes** (1500–2000 caracteres) preservan contexto pero
  diluyen la respuesta entre texto irrelevante, lo que reduce el score
  de similitud y empeora la precisión del RAG.

900 caracteres equivale aproximadamente a un párrafo medio en español
(150–180 palabras) y captura una unidad de pensamiento completa en la
mayoría de los textos académicos.

### 3.3 Justificación del solape 150

El solape entre chunks consecutivos evita perder oraciones que queden
partidas en el límite entre chunks. Por ejemplo, si el corte cae en
mitad de "Por lo tanto, los algoritmos de ordenamiento como quicksort y
mergesort comparten…", sin solape el chunk siguiente empezaría a media
oración. Con 150 caracteres de solape, esa oración aparece completa en
al menos uno de los dos chunks.

El valor 150 es aproximadamente un 16% del tamaño del chunk, lo cual es
un rango habitual en sistemas RAG (entre 10% y 20%).

### 3.4 Justificación del tope 100 chunks por documento

El tope `max_chunks=100` es una salvaguarda contra documentos
extremadamente largos. Sin él, un PDF de un libro completo de 500
páginas podría generar miles de chunks en una sola operación,
disparando coste y latencia del lote de embeddings. 100 chunks
equivalen a ~90 000 caracteres (aproximadamente 18 000 palabras),
suficiente para cualquier documento académico habitual (un capítulo,
un artículo, una tesis corta).

Documentos más largos quedan **truncados**: solo se indexan los
primeros 100 chunks. Esta es una limitación reconocida (ver sección 5).

---

## 4. Payload de cada punto

### 4.1 Estructura actual

Cada punto que se inserta en Qdrant lleva el siguiente payload:

```json
{
  "texto": "contenido del chunk...",
  "source_path": "data/ejemplos/ml_intro.pdf",
  "nombre_archivo": "ml_intro.pdf",
  "tipo_fuente": "pdf",
  "chunk_index": 0,
  "embedding_model": "text-embedding-3-large",
  "embedding_dim": 768,
  "schema_version": "1.2",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "document_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "created_at": "2026-05-17T02:14:30Z"
}
```

### 4.2 Significado de cada campo

| Campo             | Tipo    | Uso                                                                                |
| ----------------- | ------- | ---------------------------------------------------------------------------------- |
| `texto`           | string  | El texto del chunk; se usa como contexto del prompt RAG y como excerpt al frontend |
| `source_path`     | string  | Ruta relativa al archivo original (`data/ejemplos/...`)                            |
| `nombre_archivo`  | string  | Nombre del archivo sin path, usado en la UI                                        |
| `tipo_fuente`     | string  | Uno de `pdf`, `txt`, `md`, `image`. Usado para iconografía en la lista de docs    |
| `chunk_index`     | integer | Posición del chunk dentro del documento original (0, 1, 2...)                      |
| `session_id`      | string  | UUIDv4 del visitante (header `X-Session-ID`); filtra consultas y borrados          |
| `document_id`     | string  | UUIDv5 estable por `session_id` + `nombre_archivo`; agrupa chunks y borrado      |
| `embedding_model` | string  | Modelo que generó el vector. Útil para auditoría y migraciones progresivas         |
| `embedding_dim`   | integer | Dimensión del vector. Validación contra la `size` configurada en la colección      |
| `schema_version` | string  | Versión del esquema de payload, permite evolución sin romper datos viejos          |
| `created_at`     | string  | Timestamp ISO-8601 UTC de cuando se indexó el chunk                                |

### 4.3 Identificador del punto

El `point_id` es un **UUIDv5 determinístico** derivado de:

```python
uuid.uuid5(uuid.NAMESPACE_URL, f"{session_id}|{source_path}|{chunk_index}")
```

Esto garantiza que **el mismo chunk del mismo documento siempre produce
el mismo ID**. Al hacer upsert con ese ID, Qdrant sobrescribe el punto
anterior en lugar de crear uno duplicado. Re-indexar un documento
simplemente reemplaza sus chunks existentes.

### 4.4 Cómo se consume el payload

- El endpoint `/query` devuelve los campos `nombre_archivo`,
  `chunk_index`, el score y un excerpt de `texto` como **fuentes** al
  frontend.
- El endpoint `/documentos-indexados` hace `scroll` filtrado por
  `session_id` y agrupa por `document_id` para listar documentos de la sesión.
- Los campos `embedding_model`, `embedding_dim`, `schema_version` y
  `created_at` no se exponen al frontend; sirven para auditoría
  interna y para soportar evoluciones futuras del esquema.

---

## 5. Limitaciones identificadas

El esquema actual cumple su función para el alcance académico, pero
tiene dos limitaciones técnicas reconocidas:

### 5.1 No hay índices de payload

Qdrant permite crear índices sobre campos del payload para que los
filtros sean eficientes. La implementación actual no crea ningún
índice. Hoy esto no es un problema porque ninguna búsqueda usa
filtros (todas son globales sobre la colección entera), pero si en el
futuro se quisiera filtrar por `tipo_fuente` o por `embedding_model`,
los filtros serían lentos a gran escala. La sección 6 describe el
diseño de índices propuesto.

### 5.2 Chunks excedentes huérfanos al re-subir un documento más corto

El `point_id` es UUIDv5 determinístico desde `source_path|chunk_index`,
por lo que re-indexar el **mismo número de chunks** simplemente
sobrescribe los puntos anteriores. Pero si la nueva versión del
documento genera **menos chunks** que la anterior (p. ej. se eliminaron
páginas), los chunks excedentes de la versión vieja quedan huérfanos
en Qdrant: nadie los referencia desde `/documentos-indexados` (que
agrupa por `source_path` y muestra el conteo actual), pero ocupan
espacio en la colección. La mitigación es borrar los chunks por
`source_path` antes de re-indexar. Está documentado como trabajo
futuro en [`Documento_Tecnico.md`](./Documento_Tecnico.md) §10.2.

---

## 6. Diseño propuesto de mejora

Esta sección describe los índices de payload que **no están
implementados** pero resolverían la limitación 5.1. Se documenta como
trabajo futuro técnicamente justificado.

### 6.1 Índices de payload para filtros eficientes

Crear índices sobre los campos que probablemente se usarían como
filtro:

```python
client.create_payload_index(
    collection_name="mentor_ia_aprendizaje",
    field_name="tipo_fuente",
    field_schema=PayloadSchemaType.KEYWORD,
)
client.create_payload_index(
    collection_name="mentor_ia_aprendizaje",
    field_name="source_path",
    field_schema=PayloadSchemaType.KEYWORD,
)
client.create_payload_index(
    collection_name="mentor_ia_aprendizaje",
    field_name="embedding_model",
    field_schema=PayloadSchemaType.KEYWORD,
)
```

Estos índices habilitarían filtros eficientes para casos futuros como:

- "Buscar solo en imágenes" (`filter: tipo_fuente == "image"`).
- "Buscar dentro de un documento específico" (`filter: source_path == X`).
- "Re-indexar todos los chunks de un modelo viejo"
  (`filter: embedding_model != "text-embedding-3-large"`).
- "Borrar chunks huérfanos" (combinación de `source_path` con
  `chunk_index` para identificar el rango excedente).

### 6.2 Coste estimado

Implementar los índices requiere ~30 minutos: añadir las llamadas a
`create_payload_index` en el método `ensure_collection` del servicio
Qdrant. Sin migración de datos: los índices se construyen en vivo
sobre los puntos existentes.

### 6.3 Identificador único de documento (implementado — schema 1.2)

El campo `document_id` es un UUIDv5 derivado de `session_id|nombre_archivo`.
Permite listar, consultar y borrar (`DELETE /documentos/{document_id}`) un
documento completo sin depender solo de `source_path`. El borrado en Qdrant
usa siempre filtro `session_id` + `document_id`.

---

## 7. Para defender en sustentación

Cuatro puntos clave sobre el modelo de datos:

1. **La dimensión 768 y la distancia COSINE no son arbitrarias.** El
   sistema usa OpenAI `text-embedding-3-large` con `dimensions=768`
   aplicando Matryoshka Representation Learning: se obtienen las 768
   dimensiones más informativas del vector original de 3072 que el
   modelo produce nativamente. COSINE es la métrica estándar para
   embeddings semánticos. Si surge la pregunta "¿por qué no euclidiana?",
   la respuesta es: tras renormalizar los vectores a norma 1, la
   magnitud no aporta información; coseno mide solo dirección, que es
   lo que codifica el significado. La cronología de migraciones de
   modelo que llevó al stack actual está en
   [`Documento_Tecnico.md`](./Documento_Tecnico.md) §6.7.

2. **El chunking 900/150 balancea precisión y contexto.** Chunks más
   pequeños serían más precisos pero perderían contexto; más grandes
   preservarían contexto pero diluirían la similitud. 900 caracteres
   equivale a un párrafo medio en español. El solape de 150 evita
   oraciones cortadas en el límite. El tope de 100 chunks por
   documento es una salvaguarda contra textos enormes y contra el
   coste/latencia de un único lote masivo de embeddings.

3. **El payload incluye metadata de auditoría y trazabilidad.** Cada
   chunk indexado guarda `embedding_model`, `embedding_dim`,
   `schema_version` y `created_at`, además del texto y los datos de
   identificación. Esto permite saber con qué modelo se generó cada
   vector (clave para migraciones futuras), validar la dimensión al
   leer y evolucionar el esquema sin romper datos viejos.

4. **El esquema cumple las propiedades clave de un RAG productivo:**
   identificadores idempotentes (UUIDv5 determinístico), metadata de
   modelo en payload, y separación clara entre texto consultable y
   metadata operativa. Las dos limitaciones reconocidas (sin índices
   de payload activos y chunks excedentes huérfanos al re-subir un
   documento más corto) están documentadas con su mitigación en la
   sección 5 y el diseño de mejora propuesto en la sección 6.

---

_Última actualización: 2026-05-17._
