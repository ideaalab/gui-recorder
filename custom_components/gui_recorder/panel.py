from __future__ import annotations

from pathlib import Path

from aiohttp import web

from homeassistant.components import frontend
from homeassistant.core import HomeAssistant

from .const import DOMAIN, INTEGRATION_VERSION, PANEL_ICON, PANEL_MODULE_URL, PANEL_TITLE, PANEL_URL_PATH


async def _serve_panel_js(_request: web.Request) -> web.Response:
    path = Path(__file__).parent / "frontend" / "gui-recorder-panel.js"
    return web.Response(text=path.read_text(encoding="utf-8"), content_type="application/javascript")


async def async_setup_panel(hass: HomeAssistant) -> None:
    hass.http.app.router.add_get(PANEL_MODULE_URL, _serve_panel_js)

    await frontend.async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        frontend_url_path=PANEL_URL_PATH,
        config={
            "_panel_custom": {
                "name": "gui-recorder-panel",
                "module_url": f"{PANEL_MODULE_URL}?v={INTEGRATION_VERSION}",
                "trust_external": False,
            }
        },
        require_admin=True,
    )

    hass.data.setdefault(DOMAIN, {})["panel_registered"] = True
