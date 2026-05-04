# GUI Recorder

Panel lateral para Home Assistant que gestiona la configuración del `recorder` y el mantenimiento de la base de datos (SQLite) desde una UI, sin tocar `configuration.yaml`.

## Qué hace

- Activa/desactiva la grabación por dispositivo y por entidad con un toggle.
- Muestra estadísticas de la base de datos: registros totales / actuales / obsoletos, exclusiones, tamaño en disco, ruta del SQLite.
- Acciones de mantenimiento: purgar BD, purgar entidades excluidas (historial completo), repack, reiniciar HA.
- Detecta exclusiones huérfanas (que ya no coinciden con ninguna entidad) y permite eliminarlas en lote.
- Migración asistida del `recorder` heredado desde `configuration.yaml`.

## Requisitos

- Home Assistant 2024.1.0+
- Base de datos del recorder en **SQLite** (MariaDB / PostgreSQL no soportados).

## Configuración

Tras instalar, añade la integración desde **Ajustes → Dispositivos y servicios → Añadir integración → GUI Recorder**. El panel aparece en la barra lateral.
