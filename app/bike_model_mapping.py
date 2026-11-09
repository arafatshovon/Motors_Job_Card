"""Motors' model groups imported from Mapped model name.xlsx, rows 2–76.

Merged cells in column B apply to every detailed model in the merged range.
Keep the mapping in config/bike_model_groups.json as the shared source.
"""

import json
from pathlib import Path


def load_bike_model_mapping():
    path = Path(__file__).parent / "config" / "bike_model_groups.json"
    groups = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(groups, dict) or not groups:
        raise ValueError("Bike model mapping must contain model groups")

    seen = set()
    for group, models in groups.items():
        if not group or not isinstance(models, list) or not models:
            raise ValueError(f"Invalid bike model group: {group}")
        for model in models:
            key = model.casefold()
            if not model.strip() or key in seen:
                raise ValueError(f"Empty or duplicate bike model mapping: {model}")
            seen.add(key)
    return groups
