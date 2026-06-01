#!/usr/bin/env python3
"""Expand the fictional location corpus to a browseable launch depth."""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LOCATIONS_PATH = REPO_ROOT / "site" / "src" / "lib" / "data" / "locations.json"

TARGET_COUNTS = {
    "Transport": 14,
    "Science": 5,
    "Entertainment": 5,
    "Land Art": 5,
    "Waterworks": 5,
    "Structures": 5,
    "Infrastructure": 5,
    "Maritime": 5,
    "Ancient Forms": 5,
    "Sports": 5,
    "Agriculture": 5,
}

CATEGORY_SPECS = {
    "Transport": {
        "forms": ["Loop Terminal", "Switchyard", "Viaduct", "Transit Fan", "Signal Yard", "Rail Basin"],
        "regions": ["North Marrow Shelf", "Grey Fen Expanse", "Cinderplain", "Alta Reed Flats"],
        "tags": ["terminal", "radial", "transit"],
        "summary": "A fictional transit work of pale lanes, service loops, and impossible approach roads.",
    },
    "Science": {
        "forms": ["Mirror Field", "Receiver Array", "Weather Grid", "Dish Garden", "Listening Post"],
        "regions": ["Whitefold Basin", "Isobar Plateau", "Dawnline Steppe"],
        "tags": ["observatory", "array", "research"],
        "summary": "A generated science site of pads, service tracks, and instrument shadows.",
    },
    "Entertainment": {
        "forms": ["Amphitheatre", "Festival Oval", "Moon Court", "Archive Arena", "Civic Bowl"],
        "regions": ["Green Glass Uplands", "Morrow Vale", "Still Orchard"],
        "tags": ["venue", "civic", "oval"],
        "summary": "A fictional gathering place with an oversized footprint and theatrical geometry.",
    },
    "Land Art": {
        "forms": ["Pattern Garden", "Compass Walk", "Sunwork", "Line Field", "Spiral Ground"],
        "regions": ["Moss Meridian", "Verdant Array", "Low Halo Plain"],
        "tags": ["land-art", "pattern", "earthwork"],
        "summary": "A generated earthwork where planted bands and bare ground form a visible pattern.",
    },
    "Waterworks": {
        "forms": ["Canal Locks", "Reservoir Fork", "Pump Terrace", "Weir Garden", "Filter Yard"],
        "regions": ["Sable Delta", "Brine Cut", "Ternwater Flats"],
        "tags": ["canal", "reservoir", "water"],
        "summary": "A fictional water-control site of channels, basins, and service edges.",
    },
    "Structures": {
        "forms": ["Dome Quarter", "Vault Yard", "Nacre Campus", "Crown House", "Shelter Grid"],
        "regions": ["Nacre Peninsula", "Pale Civic Rise", "Shellmark District"],
        "tags": ["structure", "compound", "roof"],
        "summary": "A generated built cluster with roofs, courtyards, and arranged service voids.",
    },
    "Infrastructure": {
        "forms": ["Relay Yard", "Heat Exchange", "Power Fan", "Cable Plain", "Substation Ring"],
        "regions": ["Red Meridian", "Ashline Mesa", "Copper Dust Plain"],
        "tags": ["relay", "utility", "grid"],
        "summary": "A fictional utility field whose lines and pads imply a purpose that does not exist.",
    },
    "Maritime": {
        "forms": ["Drydock", "Shoal Yard", "Pier Maze", "Harbor Comb", "Tidal Apron"],
        "regions": ["Cobalt Shoal", "Blueglass Coast", "Salt Reed Bay"],
        "tags": ["dock", "harbor", "shore"],
        "summary": "A generated coastal work of piers, basins, and oddly calm water.",
    },
    "Ancient Forms": {
        "forms": ["Step Pyramid", "Sun Mound", "Causeway Tomb", "Terrace Shrine", "Oracle Ring"],
        "regions": ["Auric Steppe", "Old Glass Desert", "Thorn Gold Plain"],
        "tags": ["monument", "terrace", "ancient-form"],
        "summary": "A fictional monumental form with ceremonial geometry and no real history.",
    },
    "Sports": {
        "forms": ["Stadium", "Training Oval", "Race Loop", "Night Pitch", "Field Complex"],
        "regions": ["Night Orchard", "Lampwick Downs", "Greenline Borough"],
        "tags": ["sport", "field", "oval"],
        "summary": "A generated sport landscape with pitches, loops, and service courts.",
    },
    "Agriculture": {
        "forms": ["Spiral Farms", "Crop Wheel", "Irrigation Lace", "Orchard Fan", "Terrace Rows"],
        "regions": ["Pale River", "Barley Mirror", "Silt Ribbon Valley"],
        "tags": ["farm", "irrigation", "field"],
        "summary": "A fictional agricultural pattern of fields, rows, and impossible water logic.",
    },
}

PREFIXES = [
    "Aster",
    "Brindle",
    "Cairn",
    "Dawn",
    "Ebon",
    "Fallow",
    "Glimmer",
    "Hollow",
    "Iris",
    "Jade",
    "Kestrel",
    "Lumen",
    "Myr",
    "Nacre",
    "Ochre",
    "Pale",
    "Quill",
    "Red",
    "Sable",
    "Tern",
    "Umber",
    "Verdant",
    "Wisp",
    "Yarrow",
]


def slugify(value: str) -> str:
    return re.sub(r"(^-|-$)", "", re.sub(r"[^a-z0-9]+", "-", value.lower()))


def synthetic_coordinates(index: int) -> str:
    north_south = "N" if index % 2 == 0 else "S"
    east_west = "E" if index % 3 else "W"
    lat = 4 + (index * 7.311) % 71
    lon = 9 + (index * 11.173) % 160
    return f"{north_south}{lat:05.2f} / {east_west}{lon:06.2f}"


def generated_location(category: str, ordinal: int, global_index: int) -> dict[str, object]:
    spec = CATEGORY_SPECS[category]
    prefix = PREFIXES[(global_index + ordinal) % len(PREFIXES)]
    form = spec["forms"][ordinal % len(spec["forms"])]
    title = f"{prefix} {form}"
    slug = slugify(title)
    region = spec["regions"][ordinal % len(spec["regions"])]
    added = date(2026, 6, 1) - timedelta(days=global_index % 28)
    views = 840 - (global_index * 11) + (len(category) * 7)
    summary = spec["summary"]
    description = (
        f"{title} is imaginary satellite-style content generated for VirtualSpaceTrotting. "
        f"From above, the {form.lower()} reads as a convincing site, but every road, edge, "
        f"shadow, and landmark belongs only to this fictional atlas."
    )
    return {
        "slug": slug,
        "title": title,
        "fictional": True,
        "category": category,
        "region": region,
        "syntheticCoordinates": synthetic_coordinates(global_index),
        "dateAdded": added.isoformat(),
        "views": max(120, views),
        "image": f"/assets/locations/{slug}.png",
        "summary": summary,
        "description": description,
        "tags": spec["tags"],
    }


def main() -> int:
    locations = json.loads(LOCATIONS_PATH.read_text(encoding="utf-8"))
    existing_slugs = {entry["slug"] for entry in locations}
    existing_titles = {entry["title"] for entry in locations}
    counts = {category: 0 for category in TARGET_COUNTS}
    for location in locations:
        category = str(location["category"])
        if category in counts:
            counts[category] += 1

    global_index = len(locations) + 1
    for category, target in TARGET_COUNTS.items():
        ordinal = 0
        while counts[category] < target:
            candidate = generated_location(category, ordinal, global_index)
            ordinal += 1
            if candidate["slug"] in existing_slugs or candidate["title"] in existing_titles:
                continue
            locations.append(candidate)
            existing_slugs.add(candidate["slug"])
            existing_titles.add(candidate["title"])
            counts[category] += 1
            global_index += 1

    LOCATIONS_PATH.write_text(json.dumps(locations, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
