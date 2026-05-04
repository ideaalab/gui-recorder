# GUI Recorder

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/v/release/ideaalab/gui-recorder)](https://github.com/ideaalab/gui-recorder/releases)

Custom component para Home Assistant que añade un panel lateral para gestionar la configuración del `recorder` (qué entidades se graban) y el mantenimiento de la base de datos (purgas, repack, estadísticas) sin tener que tocar `configuration.yaml`.

> **Solo SQLite.** MariaDB y PostgreSQL están explícitamente bloqueados en el flujo de configuración con un mensaje claro.

## Características

- **Panel lateral** integrado en la barra de Home Assistant.
- **Gestión por dispositivo y por entidad**: activar/desactivar la grabación con un toggle, sin editar YAML.
- **Estadísticas de la base de datos**: registros totales / actuales / obsoletos, exclusiones, tamaño en disco (suma `.db` + `.db-wal` + `.db-shm`), ruta del archivo SQLite.
- **Acciones de mantenimiento**:
  - Purgar la base de datos (usa la retención global).
  - Purgar las entidades excluidas (historial completo, ignora retención).
  - Auto-actualizar datos tras cada purga (opcional).
  - Repack tras purga manual (opcional).
  - Reiniciar Home Assistant.
- **Detección de exclusiones huérfanas**: muestra exclusiones en `gui_recorder.yaml` que ya no coinciden con ninguna entidad y permite eliminarlas en lote.
- **Migración asistida**: importa la configuración heredada del `recorder` desde `configuration.yaml` en 3 pasos (importar → desactivar el bloque antiguo → activar el `!include`).
- **Cache busting**: el JS del panel se sirve con `?v=VERSION` para evitar versiones cacheadas tras una actualización.

## Instalación

### Vía HACS (recomendada)

1. Ve a HACS → Integraciones → menú `⋮` → **Custom repositories**.
2. Añade `https://github.com/ideaalab/gui-recorder` con categoría **Integration**.
3. Busca **GUI Recorder**, instala y reinicia Home Assistant.
4. Ve a **Ajustes → Dispositivos y servicios → Añadir integración** y elige **GUI Recorder**.

### Manual

1. Copia `custom_components/gui_recorder/` a `<config>/custom_components/gui_recorder/`.
2. Reinicia Home Assistant.
3. **Ajustes → Dispositivos y servicios → Añadir integración → GUI Recorder**.

## Uso

Tras instalar y configurar la integración aparece un panel **GUI Recorder** en la barra lateral. Desde ahí puedes:

- Filtrar entidades por `entity_id`, nombre, dominio o plataforma.
- Activar/desactivar dispositivos completos o entidades concretas.
- Lanzar análisis de la base de datos y purgas (globales, por dispositivo o por entidad).
- Importar la configuración del `recorder` que ya tuvieras en `configuration.yaml`.

La configuración generada se escribe a `gui_recorder.yaml`, que se incluye desde `configuration.yaml` con:

```yaml
recorder: !include gui_recorder.yaml
```

La integración escribe ese archivo automáticamente. Si ya tenías un bloque `recorder:` en `configuration.yaml`, el flujo de migración del panel te guía para sustituirlo.

## Requisitos

- Home Assistant **2024.1.0** o superior.
- Base de datos del `recorder` en **SQLite** (la integración rechaza MariaDB y PostgreSQL).

## Soporte

- Issues: https://github.com/ideaalab/gui-recorder/issues

## Licencia

[MIT](LICENSE)
