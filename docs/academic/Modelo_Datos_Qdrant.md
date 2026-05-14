# Modelo de datos vectorial — Mentor IA (Qdrant)

> Documento técnico de diseño del modelo de datos vectorial para Mentor
> IA. Describe el estado actual del esquema, la configuración de la
> colección, la estrategia de chunking, el payload de cada punto y las
> limitaciones identificadas, junto con un diseño propuesto de mejora
> documentado como trabajo futuro.
>
> Versión: 2.0 · Fecha: 2026-05-11.
> Tarea ClickUp: Modelado del esquema de base de datos vectorial.

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
`mentor-ia-aprendizaje/src/embeddings.py` y
`mentor-ia-aprendizaje/src/agentes/agente_extraccion.py`.

| Aspecto                       | Valor actual                                                            |
| ----------------------------- | ----------------------------------------------------------------------- |
| Colección                     | `mentor_ia_aprendizaje` (configurable vía env `QDRANT_COLLECTION`)       |
| Dimensión del vector          | 768                                                                     |
| Distancia                     | COSINE                                                                  |
| Modelo de embeddings          | `gemini-embedding-001` (Google Gemini) con `outputDimensionality=768` y renormalización |
| Tamaño de chunk               | 900 caracteres                                                          |
| Solape entre chunks           | 150 caracteres                                                          |
| Máximo de chunks por documento | 100                                                                    |
| Tipos de fuente soportados    | PDF (`pypdf`), imagen (Google Vision OCR), texto plano (`.txt`/`.md`)   |
| Identificador del punto       | `uuid.uuid4().int >> 64` (entero 64-bit aleatorio)                      |
| Índices de payload            | Ninguno                                                                 |
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

La dimensión 768 es una **decisión de diseño anclada al sistema**,
no una imposición del modelo actual. Originalmente venía dada por
`text-embedding-004` (que producía nativamente vectores de 768 dim),
pero tras la deprecación de ese modelo el sistema migró a
`gemini-embedding-001`, cuya salida nativa es de 3072 dimensiones. La
dimensión 768 se conserva mediante el parámetro
`outputDimensionality=768`, que aplica **Matryoshka Representation
Learning (MRL)** para truncar el vector preservando su calidad
semántica.

Mantener 768 (en lugar de migrar a 3072 nativos) responde a tres
razones: compatibilidad con la colección Qdrant ya configurada,
eficiencia operativa (vectores 4× más pequeños) y calidad equivalente
gracias a MRL. La justificación completa de esta decisión está en
[`Documento_Tecnico.md`](./Documento_Tecnico.md) sección 6.7.

Esto tiene una consecuencia importante de diseño: la dimensión está
acoplada a la **configuración** del modelo de embeddings. Si en el
futuro se quisiera migrar a un modelo diferente (por ejemplo, OpenAI
`text-embedding-3-small` con 1536 dimensiones), no bastaría con
cambiar la llamada al API: habría que crear una colección nueva con la
dimensión correcta y re-indexar todo el corpus. Esta es una de las
razones para documentar `embedding_model` y `embedding_dim` en el
payload (ver sección 6).

**Nota operativa.** Tras truncar con MRL, los vectores no quedan
normalizados a norma 1 (se observa empíricamente norma ≈ 0.57). Como
la métrica COSINE en Qdrant trabaja idealmente sobre vectores
unitarios, el wrapper `services/gemini.py` aplica una renormalización
explícita antes de upsertear.

### 2.3 Justificación de la distancia COSINE

La distancia coseno mide la similitud de **dirección** entre dos
vectores, ignorando su magnitud. Para embeddings de texto esto es lo
deseable porque:

- Los embeddings semánticos codifican el significado en la **dirección**
  del vector, no en su tamaño.
- COSINE es la métrica recomendada explícitamente por la documentación
  de Google Gemini para embeddings semánticos.
- Los vectores se renormalizan a norma 1 en `services/gemini.py` tras
  el truncamiento MRL (con `gemini-embedding-001` la salida cruda no
  está unitarizada), así que COSINE y producto punto dan resultados
  equivalentes; pero COSINE es más legible al interpretarse como
  similitud entre 0 y 1.

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
páginas podría generar miles de chunks y agotar la cuota gratuita de
embeddings de Gemini en una sola operación. 100 chunks equivalen a
~90 000 caracteres (aproximadamente 18 000 palabras), suficiente para
cualquier documento académico habitual (un capítulo, un artículo, una
tesis corta).

Documentos más largos quedan **truncados**: solo se indexan los
primeros 100 chunks. Esta es una limitación reconocida (ver sección 5).

---

## 4. Payload de cada punto

### 4.1 Estructura actual

Cada punto que se inserta en Qdrant lleva un payload mínimo:

```json
{
  "texto": "contenido del chunk...",
  "source_path": "data/ejemplos/ml_intro.pdf",
  "nombre_archivo": "ml_intro.pdf",
  "tipo_fuente": "pdf",
  "chunk_index": 0
}
```

### 4.2 Significado de cada campo

| Campo            | Tipo    | Uso                                                                                |
| ---------------- | ------- | ---------------------------------------------------------------------------------- |
| `texto`          | string  | El texto del chunk, devuelto al frontend como fuente de la respuesta               |
| `source_path`    | string  | Ruta relativa al archivo original (`data/ejemplos/...`)                            |
| `nombre_archivo` | string  | Nombre del archivo sin path, usado en la UI                                        |
| `tipo_fuente`    | string  | Uno de `pdf`, `txt`, `md`, `image`. Usado para iconografía en la lista de docs    |
| `chunk_index`    | integer | Posición del chunk dentro del documento original (0, 1, 2...)                      |

### 4.3 Cómo se consume el payload

- El endpoint `/query` devuelve los campos `nombre_archivo`,
  `chunk_index` y el score como **fuentes** al frontend.
- El endpoint `/documentos-indexados` hace `scroll` sobre toda la
  colección agrupando por `source_path` para listar los documentos
  únicos con su conteo de chunks.
- El campo `texto` se usa internamente como contexto del prompt RAG y
  también se muestra al usuario como excerpt de la fuente.

---

## 5. Limitaciones identificadas

El esquema actual cumple su función como prototipo, pero tiene cuatro
limitaciones técnicas reconocidas:

### 5.1 El identificador del punto no es idempotente

El `point_id` se genera como `uuid.uuid4().int >> 64`, es decir, un
entero aleatorio de 64 bits derivado de un UUID v4. Esto tiene dos
problemas:

- **No es idempotente.** Si el mismo documento se sube dos veces, los
  chunks se duplican en Qdrant porque cada upsert genera IDs nuevos
  aleatorios. El sistema no detecta que ya existían.
- **Tiene riesgo teórico de colisión.** El espacio de 64 bits es
  grande, pero al truncar un UUID v4 (que originalmente tiene 122 bits
  de entropía) la probabilidad de colisión sube. En la práctica esto
  no se manifiesta para volúmenes pequeños, pero es una debilidad de
  diseño.

### 5.2 No hay índices de payload

Qdrant permite crear índices sobre campos del payload para que los
filtros sean eficientes. La implementación actual no crea ningún
índice. Hoy esto no es un problema porque ninguna búsqueda usa
filtros (todas son globales), pero si en el futuro se quisiera filtrar
por `tipo_fuente` o por `source_path`, los filtros serían lentos a
gran escala.

### 5.3 No se almacena metadata del modelo de embeddings

El payload no incluye qué modelo generó el vector ni su dimensión. Si
algún día se migrara a un modelo distinto, no habría forma de saber
qué chunks fueron generados con qué modelo, lo que dificultaría una
migración progresiva.

### 5.4 Los chunks viejos no se borran al re-subir un documento

Como el `point_id` no es idempotente, re-subir un documento crea
chunks nuevos pero no borra los viejos. El backend no realiza una
operación de borrado previo, así que los chunks del primer upload
quedan huérfanos en la colección, consumiendo cuota sin ser
referenciados por ningún documento listado en `/documentos-indexados`
(que agrupa por `source_path` y muestra el conteo actual, no
acumulado).

---

## 6. Diseño propuesto de mejora

Esta sección describe un esquema mejorado que resolvería las cuatro
limitaciones de la sección 5. **No está implementado**, se documenta
como trabajo futuro técnicamente justificado.

### 6.1 Identificador determinístico con UUIDv5

Reemplazar `uuid.uuid4().int >> 64` por un UUIDv5 derivado de un
namespace fijo y de la concatenación `source_path + chunk_index`:

```python
import uuid
NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # ej. namespace OID

point_id = str(uuid.uuid5(NAMESPACE, f"{source_path}|{chunk_index}"))
```

Con esta estrategia, **el mismo chunk del mismo documento siempre
produce el mismo ID**. Al hacer upsert con ese ID, Qdrant **sobrescribe**
el punto anterior en lugar de crear uno duplicado. Esto resuelve la
limitación 5.1 (idempotencia) y la 5.4 (chunks huérfanos): re-indexar
un documento simplemente sobrescribe sus chunks existentes.

### 6.2 Payload extendido con metadata de embedding y schema

Añadir cinco campos al payload:

```json
{
  "texto": "contenido del chunk...",
  "source_path": "data/ejemplos/ml_intro.pdf",
  "nombre_archivo": "ml_intro.pdf",
  "tipo_fuente": "pdf",
  "chunk_index": 0,

  "document_id": "uuid-v5-del-documento",
  "embedding_model": "gemini-embedding-001",
  "embedding_dim": 768,
  "schema_version": "v2",
  "created_at": "2026-05-11T18:30:00Z"
}
```

| Campo nuevo        | Propósito                                                      |
| ------------------ | -------------------------------------------------------------- |
| `document_id`      | UUIDv5 estable del documento entero (útil para agrupaciones)    |
| `embedding_model`  | Saber qué modelo generó el vector (migración progresiva futura) |
| `embedding_dim`    | Validación al leer; útil si la colección llegara a tener vectores de modelos distintos |
| `schema_version`   | Permite evolucionar el payload sin romper datos viejos          |
| `created_at`       | Trazabilidad temporal (útil para debugging y para borrados por antigüedad) |

Estos campos resuelven la limitación 5.3.

### 6.3 Índices de payload para filtros futuros

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
    field_name="document_id",
    field_schema=PayloadSchemaType.KEYWORD,
)
client.create_payload_index(
    collection_name="mentor_ia_aprendizaje",
    field_name="embedding_model",
    field_schema=PayloadSchemaType.KEYWORD,
)
```

Estos índices habilitan filtros eficientes para casos futuros como:

- "Buscar solo en imágenes" (`filter: tipo_fuente == "image"`).
- "Buscar dentro de un documento específico" (`filter: document_id == X`).
- "Re-indexar todos los chunks del modelo viejo" (`filter: embedding_model != "gemini-embedding-001"`).

Esto resuelve la limitación 5.2.

### 6.4 Resumen de la mejora

| Limitación                              | Solución propuesta                                |
| --------------------------------------- | ------------------------------------------------- |
| 5.1 Point ID no idempotente             | UUIDv5(`source_path` + `chunk_index`)             |
| 5.2 No hay índices de payload           | Crear índices `KEYWORD` en `tipo_fuente`, `document_id`, `embedding_model` |
| 5.3 Falta metadata del embedding        | Añadir `embedding_model`, `embedding_dim`, `schema_version`, `created_at` |
| 5.4 Chunks huérfanos al re-subir        | Resuelto automáticamente por la idempotencia del ID |

El costo de implementar esta mejora se estima en 1–2 días de trabajo:
modificación de `agente_extraccion.py` para generar el nuevo ID y
payload, creación de los índices al iniciar el backend, y un script
de migración para re-indexar los chunks existentes con el nuevo
esquema.

---

## 7. Para defender en sustentación

Cuatro puntos clave sobre el modelo de datos:

1. **La dimensión 768 y la distancia COSINE no son arbitrarias.** El
   sistema usa `gemini-embedding-001` (reemplazo oficial de
   `text-embedding-004`, deprecado el 14-ene-2026) con
   `outputDimensionality=768` aplicando Matryoshka Representation
   Learning: se obtienen las 768 dimensiones más informativas del
   vector original de 3072. COSINE es la métrica recomendada por
   Google para embeddings semánticos. Si te preguntan "¿por qué no
   euclidiana?", la respuesta es: "porque tras renormalizar los
   vectores a norma 1, la magnitud no aporta información; coseno mide
   solo dirección, que es lo que codifica el significado". La
   justificación completa de la migración del modelo y de mantener 768
   vs 3072 está en [`Documento_Tecnico.md`](./Documento_Tecnico.md)
   sección 6.7.

2. **El chunking 900/150 balancea precisión y contexto.** Chunks más
   pequeños serían más precisos pero perderían contexto; más grandes
   preservarían contexto pero diluirían la similitud. 900 caracteres
   equivale a un párrafo medio en español. El solape de 150 evita
   oraciones cortadas en el límite. El tope de 100 chunks por
   documento es una salvaguarda contra textos enormes que agoten la
   cuota gratuita de Gemini.

3. **El esquema actual tiene cuatro limitaciones técnicas reconocidas.**
   El `point_id` no es idempotente (se duplican chunks al re-subir un
   documento), no hay índices de payload, falta metadata del modelo y
   los chunks viejos quedan huérfanos. Estas limitaciones están
   documentadas en la sección 5 y existe un diseño de mejora
   propuesto en la sección 6 que las resuelve usando UUIDv5
   determinístico y payload extendido.

4. **El diseño es single-tenant intencional.** No hay concepto de
   propietario, curso o tenant porque el alcance académico es de
   instancia individual. No es una omisión: la separación por usuario
   se descartó explícitamente en
   [`Documento_Tecnico.md`](./Documento_Tecnico.md) sección 3.2.

---

_Última actualización: 2026-05-11._
