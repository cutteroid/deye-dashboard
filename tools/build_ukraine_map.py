#!/usr/bin/env python3
"""Build static/data/ukraine-regions.json: SVG paths of Ukraine's regions and districts.

Source: OCHA Common Operational Dataset "Ukraine - Subnational Administrative
Boundaries" (State Scientific Production Enterprise "Kartographia"), licensed
CC BY-IGO: https://data.humdata.org/dataset/cod-ab-ukr
Download "ukr_admin_boundaries.geojson.zip" and unzip it.

alerts.in.ua location ids (UIDs) are matched by oblast + raion name from their
public location list (https://devs.alerts.in.ua/ links the Google Sheet), exported
as CSV:
https://docs.google.com/spreadsheets/d/1XnTOzcPHd1LZUrarR1Fk43FUyl8Ae6a6M7pcwDRjNdA/export?format=csv

Usage:
    python tools/build_ukraine_map.py path/to/unzipped/ocha/folder alerts_locations.csv

Output:
    regions:   27 oblasts + Kyiv + Sevastopol + Crimea, id = ISO 3166-2 code (UA-05 ...)
    districts: raions (post-2020 reform), id = OCHA pcode (UA0502 ...), with the
               ISO code of their region and Ukrainian/English names
    Both carry their alerts.in.ua UID ("alerts_uid"); NEPTUN data is matched to
    districts by the Ukrainian name instead.
Region display names live in locales/*.json (alerts.regions.*).
"""
import json
import math
import os
import sys

OUTPUT = "static/data/ukraine-regions.json"
WIDTH = 1000          # viewBox width; height follows the projected aspect ratio
CENTER_LAT = 48.5     # equirectangular projection, x scaled by cos(center latitude)
REGION_TOLERANCE = 1.2
DISTRICT_TOLERANCE = 1.2
MIN_RING_AREA = 2.0   # drop islands smaller than this (output units^2)

# OCHA oblast pcodes that differ from ISO 3166-2; the rest map UAnn -> UA-nn
PCODE_TO_ISO = {"UA01": "UA-43", "UA44": "UA-09", "UA73": "UA-77", "UA80": "UA-30", "UA85": "UA-40"}


def load_alerts_uids(csv_path, region_names_uk, district_regions):
    """alerts.in.ua UIDs: ({region_iso: uid}, {(region_iso, raion_name): uid}).

    The sheet is roughly hierarchical (oblast row, then its raions and hromadas),
    but not strictly: e.g. Crimea's row sits between Volyn and Volyn's raions. So a
    raion is matched by name against the OCHA districts (district_regions:
    {raion_name: [region_iso, ...]}); the sheet position only breaks ties.
    """
    import csv
    name_to_iso = {name: code for code, name in region_names_uk.items()}
    region_uids, raion_uids = {}, {}
    current = None
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) < 3 or not row[0].strip().isdigit():
                continue
            uid, name, kind = row[0].strip(), row[1].strip(), row[2].strip()
            if kind in ("Область", "Місто з спеціальним статусом"):
                current = name_to_iso.get(name)
                if current is None:
                    sys.exit(f"Unknown oblast in alerts list: {name!r}")
                region_uids[current] = int(uid)
            elif kind == "Район":
                raion = name.removesuffix(" район")
                candidates = district_regions.get(raion, [])
                region = candidates[0] if len(candidates) == 1 else current
                raion_uids[(region, raion)] = int(uid)
    return region_uids, raion_uids


def region_iso(pcode):
    return PCODE_TO_ISO.get(pcode, f"UA-{pcode[2:]}")


def project(lon, lat):
    return lon * math.cos(math.radians(CENTER_LAT)), -lat


def simplify(points, tol):
    """Douglas-Peucker on an open polyline of (x, y)."""
    if len(points) < 3:
        return points
    (x1, y1), (x2, y2) = points[0], points[-1]
    dx, dy = x2 - x1, y2 - y1
    norm = math.hypot(dx, dy) or 1e-12
    max_d, index = 0.0, 0
    for i in range(1, len(points) - 1):
        px, py = points[i]
        d = abs(dy * px - dx * py + x2 * y1 - y2 * x1) / norm
        if d > max_d:
            max_d, index = d, i
    if max_d <= tol:
        return [points[0], points[-1]]
    return simplify(points[:index + 1], tol)[:-1] + simplify(points[index:], tol)


def simplify_ring(points, tol):
    """Simplify a closed ring (first point not repeated at the end).

    Plain Douglas-Peucker can't handle a closed ring (start == end), so split it
    at the point farthest from the start and simplify the two halves.
    """
    x0, y0 = points[0]
    far = max(range(len(points)), key=lambda i: (points[i][0] - x0) ** 2 + (points[i][1] - y0) ** 2)
    first = simplify(points[:far + 1], tol)
    second = simplify(points[far:] + [points[0]], tol)
    return first[:-1] + second[:-1]


def ring_area(points):
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]))) / 2


def load(folder, level):
    path = os.path.join(folder, f"ukr_admin{level}.geojson")
    with open(path, encoding="utf-8") as f:
        return json.load(f)["features"]


def polygons_of(feature):
    g = feature["geometry"]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    return [[[project(lon, lat) for lon, lat in ring] for ring in poly] for poly in polys]


def to_path(polygons, transform, tol):
    parts = []
    for poly in polygons:
        for i, ring in enumerate(poly):
            pts = [transform(p) for p in ring]
            if pts[0] == pts[-1]:
                pts = pts[:-1]
            if i == 0 and ring_area(pts) < MIN_RING_AREA:
                break  # tiny island: skip it with its holes
            pts = simplify_ring(pts, tol)
            if len(pts) < 3:
                continue
            parts.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z")
    return "".join(parts)


def main(folder, alerts_csv):
    admin1 = load(folder, 1)
    admin2 = load(folder, 2)
    with open("locales/uk.json", encoding="utf-8") as f:
        region_names_uk = json.load(f)["alerts"]["regions"]
    district_regions = {}
    for f in admin2:
        district_regions.setdefault(f["properties"]["adm2_name1"], []).append(
            region_iso(f["properties"]["adm1_pcode"]))
    region_uids, raion_uids = load_alerts_uids(alerts_csv, region_names_uk, district_regions)

    region_polys = {region_iso(f["properties"]["adm1_pcode"]): polygons_of(f) for f in admin1}
    all_pts = [p for polys in region_polys.values() for poly in polys for ring in poly for p in ring]
    min_x, max_x = min(p[0] for p in all_pts), max(p[0] for p in all_pts)
    min_y, max_y = min(p[1] for p in all_pts), max(p[1] for p in all_pts)
    scale = WIDTH / (max_x - min_x)
    height = round((max_y - min_y) * scale)

    def transform(p):
        return (p[0] - min_x) * scale, (p[1] - min_y) * scale

    regions = [{"id": code, "alerts_uid": region_uids.get(code),
                "d": to_path(region_polys[code], transform, REGION_TOLERANCE)}
               for code in sorted(region_polys)]
    districts = []
    for f in sorted(admin2, key=lambda f: f["properties"]["adm2_pcode"]):
        p = f["properties"]
        region = region_iso(p["adm1_pcode"])
        districts.append({
            "id": p["adm2_pcode"],
            "region": region,
            # Kyiv/Sevastopol are a single "district" = the city itself
            "alerts_uid": raion_uids.get((region, p["adm2_name1"])) or
                          (region_uids.get(region) if p["adm2_pcode"] in ("UA8000", "UA8500") else None),
            "name": {"uk": p["adm2_name1"], "en": p["adm2_name"]},
            "d": to_path(polygons_of(f), transform, DISTRICT_TOLERANCE),
        })

    out = {
        "source": ('OCHA COD-AB "Ukraine - Subnational Administrative Boundaries" '
                   '(SSPE "Kartographia"), CC BY-IGO, https://data.humdata.org/dataset/cod-ab-ukr; '
                   "generated by tools/build_ukraine_map.py"),
        "viewBox": f"0 0 {WIDTH} {height}",
        "regions": regions,
        "districts": districts,
    }
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    size = os.path.getsize(OUTPUT)
    print(f"Wrote {OUTPUT}: {len(regions)} regions, {len(districts)} districts, "
          f"viewBox 0 0 {WIDTH} {height}, {size / 1024:.1f} KB")
    missing_regions = [r["id"] for r in regions if r["alerts_uid"] is None]
    unmatched = [f"{d['id']} {d['name']['uk']} ({d['region']})" for d in districts
                 if d["alerts_uid"] is None and d["region"] != "UA-43"]
    used = {d["alerts_uid"] for d in districts}
    unused = [f"{name} ({region})" for (region, name), uid in raion_uids.items() if uid not in used]
    print(f"  alerts.in.ua UIDs: regions without uid: {missing_regions or 'none'}")
    print(f"  districts without uid (outside Crimea): {unmatched or 'none'}")
    print(f"  alerts.in.ua raions not matched: {unused or 'none'}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
