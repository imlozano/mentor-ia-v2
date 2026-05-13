# Skill — Añadir un componente shadcn/ui al frontend

Aplicable cuando: el frontend necesita un componente de shadcn/ui que aún
no está instalado.

## Reglas

1. shadcn/ui se instala componente por componente, no como librería
   completa.
2. Cada componente se descarga en `frontend/components/ui/<nombre>.tsx`
   y se modifica si es necesario (es código tuyo, no de una dependencia).
3. Antes de instalar, verificar si el componente ya está en
   `frontend/components/ui/`.

## Cómo instalar

```bash
cd frontend
npx shadcn@latest add <componente>
```

Componentes comunes que el proyecto usa:

| Componente   | Uso típico                                |
| ------------ | ----------------------------------------- |
| `alert`      | Mensajes de error y aviso.                |
| `badge`      | Etiquetas pequeñas (origen RAG, tipo).    |
| `button`     | Cualquier acción.                         |
| `card`       | Tarjetas de documento, planes, etc.       |
| `input`      | Inputs de texto y email.                  |
| `label`      | Etiquetas de campos.                      |
| `radio-group`| Modo Tema vs Archivo en Plan de Repaso.   |
| `scroll-area`| Listas largas con scroll suave.           |
| `separator`  | Líneas divisorias.                        |
| `skeleton`   | Estado de carga.                          |
| `tabs`       | Tabs principales y sub-tabs.              |
| `textarea`   | Resultado OCR, prompts largos.            |

## Reglas de uso

- NO modificar `components/ui/*.tsx` si solo necesitas ajustar
  estilos puntuales: pasa `className` como prop con `cn()`.
- Si necesitas cambiar el comportamiento del componente (no solo
  estilos), entonces sí modifica el archivo.
- Si shadcn rompe entre versiones de Tailwind: verificar en
  https://ui.shadcn.com/ las instrucciones para Tailwind 4.

## Tokens de color a usar

Los componentes shadcn usan estos tokens (definidos en `globals.css`):

- `bg-background` / `text-foreground` — fondo y texto principal.
- `bg-primary` / `text-primary-foreground` — botones primarios.
- `bg-muted` / `text-muted-foreground` — fondos sutiles.
- `border-border` — bordes.
- `bg-destructive` / `text-destructive-foreground` — errores.

No usar colores Tailwind directos (`bg-blue-500`, etc.) en componentes
de dominio. Usar siempre los tokens semánticos.

## Después de añadir el componente

1. Importarlo donde se necesite.
2. Verificar que no hay warning de TypeScript ni de Tailwind.
3. `npm run build` para confirmar que no rompe el build.
