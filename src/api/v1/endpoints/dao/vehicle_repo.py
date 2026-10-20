"""SQL + normalisation for van_models / pricing_inventory."""
import json

from ..db import get_cursor

_DEFAULT_SPECS = {"solar": False, "battery": "Unknown", "heater": "Unknown", "bed": "Unknown"}


def normalize_specs(raw) -> dict:
    """Accept dict / JSON string / anything; always return the 4-field shape."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            raw = {}
    if not isinstance(raw, dict):
        raw = {}
    return {
        "solar": raw.get("solar") if isinstance(raw.get("solar"), bool) else _DEFAULT_SPECS["solar"],
        "battery": str(raw.get("battery", _DEFAULT_SPECS["battery"])),
        "heater": str(raw.get("heater", _DEFAULT_SPECS["heater"])),
        "bed": str(raw.get("bed", _DEFAULT_SPECS["bed"])),
    }


def list_vehicles() -> list:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT vm.id, vm.model_name, vm.berths, vm.transmission, vm.specs,
                   pi.pickup_date, pi.return_date, pi.price_nzd
            FROM van_models vm
            LEFT JOIN pricing_inventory pi ON vm.id = pi.model_id
            ORDER BY vm.id;
            """
        )
        return [
            {
                "model_name": r[1],
                "berths": r[2],
                "transmission": r[3],
                "specs": normalize_specs(r[4]),
                "price_nzd": float(r[7]) if r[7] is not None else 0.0,
                "pickup_date": r[5].isoformat() if r[5] is not None else None,
                "return_date": r[6].isoformat() if r[6] is not None else None,
            }
            for r in cur.fetchall()
        ]
