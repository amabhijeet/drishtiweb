import math
from datetime import datetime
from defusedxml.ElementTree import fromstring


def point(lat, lon):
    lat, lon = float(lat), float(lon)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        hint = " Possible reversed latitude and longitude." if abs(lon) <= 90 and abs(lat) <= 180 else ""
        raise ValueError("Coordinates outside geographic limits." + hint)
    return lat, lon


def distance(a, b):
    p, q = map(math.radians, [a[0], b[0]])
    dp, dl = q-p, math.radians(b[1]-a[1])
    h = math.sin(dp/2)**2 + math.cos(p)*math.cos(q)*math.sin(dl/2)**2
    return 12742000 * math.asin(math.sqrt(min(1, h)))


def validate(location, reference, tolerance):
    if location is None:
        return "Missing GPS evidence", None
    if reference is None:
        return "Valid coordinate format", None
    meters = distance(location, reference)
    return ("Reference matched" if meters <= tolerance else "Location mismatch"), round(meters, 2)


def read_track(raw):
    rows, warnings = [], []
    for segment in fromstring(raw).findall(".//{*}trkseg"):
        previous = None
        for item in segment.findall("{*}trkpt"):
            coord = point(item.attrib["lat"], item.attrib["lon"])
            stamp = item.findtext("{*}time")
            when = datetime.fromisoformat(stamp.replace("Z", "+00:00")) if stamp else None
            if when is None or when.utcoffset() is None:
                warnings.append("Missing timestamp or timezone")
                when = None
            if previous and when and previous[1]:
                seconds = (when - previous[1]).total_seconds()
                if seconds <= 0 or distance(previous[0], coord) > seconds * 55:
                    warnings.append("Non-increasing timestamp or jump above 55 m/s")
            rows.append([*coord, stamp])
            previous = coord, when
    return rows, sorted(set(warnings))


def photo_gps(image):
    exif = image.getexif()
    gps = exif.get_ifd(34853)
    if not gps:
        return None
    def degrees(parts, ref, positive, negative):
        if ref not in (positive, negative) or len(parts) != 3:
            raise ValueError("Incomplete EXIF GPS")
        d, m, s = map(float, parts)
        if d < 0 or not (0 <= m < 60 and 0 <= s < 60):
            raise ValueError("Malformed EXIF degrees, minutes or seconds")
        return (d + m/60 + s/3600) * (1 if ref == positive else -1)
    return point(degrees(gps[2], gps[1], "N", "S"), degrees(gps[4], gps[3], "E", "W"))
