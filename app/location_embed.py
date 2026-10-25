import json
from typing import Iterable

from .models import DropOffLocation


LOCATION_TYPE_LABELS = {
    "dropbox": "Sammelbox",
    "donationbox": "Spendenbox",
    "office": "Büro",
    "storage": "Lager",
    "dispense": "Ausgabestandort",
}


def _serialize_public_locations(locations: Iterable[DropOffLocation]) -> str:
    """Serialize only fields intended for publication in the embed code."""
    payload = [
        {
            "name": location.name,
            "address": location.address,
            "city": location.city or "",
            "latitude": location.latitude,
            "longitude": location.longitude,
            "type": LOCATION_TYPE_LABELS.get(location.location_type, "Standort"),
        }
        for location in locations
    ]
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def build_location_embed_code(locations: Iterable[DropOffLocation]) -> str:
    """Build a standalone Leaflet map snippet from selected locations."""
    public_locations = _serialize_public_locations(locations)
    return f'''<!-- PfotenRegister Standortkarte
     Nicht direkt als file://-Datei öffnen. Lokal beispielsweise mit
     "python -m http.server 8000" über http://localhost:8000 bereitstellen. -->
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<div id="pfotenregister-location-map" style="width:100%;height:520px;min-height:360px;border-radius:16px;overflow:hidden;"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
(function () {{
    "use strict";
    const locations = {public_locations};
    const mapElement = document.getElementById("pfotenregister-location-map");
    if (window.location.protocol === "file:") {{
        mapElement.innerHTML = '<div style="box-sizing:border-box;padding:1.25rem;background:#fff3cd;color:#664d03;height:100%;">' +
            '<strong>Lokale Kartenvorschau blockiert</strong><br>' +
            'OpenStreetMap verlangt für Webseiten einen HTTP-Referrer. Stelle diese Datei lokal über einen Webserver bereit, zum Beispiel mit ' +
            '<code>python -m http.server 8000</code>, und öffne anschließend <code>http://localhost:8000</code>.</div>';
        return;
    }}

    const map = L.map(mapElement, {{ scrollWheelZoom: false }}).setView([51.1657, 10.4515], 6);

    L.tileLayer("https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>-Mitwirkende'
    }}).addTo(map);

    function escapeHtml(value) {{
        const element = document.createElement("div");
        element.textContent = String(value || "");
        return element.innerHTML;
    }}

    const markers = locations.map(function (location) {{
        const address = [location.address, location.city].filter(Boolean).join(", ");
        const popup = "<strong>" + escapeHtml(location.name) + "</strong><br>" +
            escapeHtml(address) + "<br><small>" + escapeHtml(location.type) + "</small>";
        return L.marker([location.latitude, location.longitude]).addTo(map).bindPopup(popup);
    }});

    if (markers.length === 1) {{
        map.setView(markers[0].getLatLng(), 14);
    }} else if (markers.length > 1) {{
        map.fitBounds(L.featureGroup(markers).getBounds().pad(0.15));
    }}
}})();
</script>'''
