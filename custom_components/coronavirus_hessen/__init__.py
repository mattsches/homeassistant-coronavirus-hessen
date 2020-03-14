"""The corona_hessen component."""

from datetime import timedelta
import logging

import async_timeout
import asyncio
import bs4

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, ENDPOINT, OPTION_TOTAL

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Coronavirus Hessen component."""
    # Make sure coordinator is initialized.
    await get_coordinator(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Coronavirus Hessen from a config entry."""

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    return unload_ok


async def get_coordinator(hass):
    """Get the data update coordinator."""
    if DOMAIN in hass.data:
        return hass.data[DOMAIN]

    async def async_get_data():
        with async_timeout.timeout(10):
            response = await aiohttp_client.async_get_clientsession(hass).get(ENDPOINT)
            raw_html = await response.text()

        data = bs4.BeautifulSoup(raw_html, "html.parser")
        
        result = dict()
        rows = data.select("article table:first-of-type tr")

        # Counties
        for row in rows[1:-1]:
            line = row.select("td")
            if len(line) != 4:
                continue

            try:
                county = line[0].text.strip()
                cases_str = line[3].text.strip()
                if len(cases_str) and cases_str != "-":
                    cases = int(cases_str)
                else:
                    cases = 0
            except ValueError:
                _LOGGER.error("Error processing line {}, skipping".format(line))
                continue
            result[county] = cases

        # Total
        line = rows[-1].select("td")
        try:
            result[OPTION_TOTAL] = int(line[-1].select("p strong")[0].text.strip())
        except ValueError:
            _LOGGER.error("Error processing total value from {}, skipping".format(line))

        _LOGGER.debug("Corona Hessen: {!r}".format(result))
        return result

    hass.data[DOMAIN] = DataUpdateCoordinator(
        hass,
        logging.getLogger(__name__),
        name=DOMAIN,
        update_method=async_get_data,
        update_interval=timedelta(hours=12), # 12h as the data apparently only updates once per day anyhow
    )
    await hass.data[DOMAIN].async_refresh()
    return hass.data[DOMAIN]