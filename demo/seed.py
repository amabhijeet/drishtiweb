"""Initialize only the demo volume, after the demo processor creates its SQLite schema."""
from pathlib import Path
import sqlite3
import subprocess

from .portal import root
from app import schema


def seed(directory):
    with sqlite3.connect(directory / "drishti.sqlite3") as db:
        db.executescript(schema)
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT 1 FROM segments WHERE id='sample-survey'").fetchone():
            return
        folder = directory / "uploads" / "sample-survey"
        folder.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        "testsrc2=size=480x270:rate=12:duration=18", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", str(folder / "video.mp4")], check=True)
        image = directory / "instances" / "sample.jpg"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(folder / "video.mp4"),
                        "-frames:v", "1", str(image)], check=True)
        track = "".join(f'<trkpt lat="{26.1+i/10000}" lon="91.7"><time>2026-01-01T00:00:{i:02}Z</time></trkpt>' for i in range(18))
        (folder / "track.gpx").write_text(f'<gpx version="1.1"><trk><trkseg>{track}</trkseg></trk></gpx>')
        db.execute("""INSERT INTO segments(id,session,fingerprint,metadata,directory,status)
                      VALUES('sample-survey','demo','synthetic','{}','sample-survey','done')""")
        for i in range(1, 8):
            rid = f"sample-{i:02}"
            lat = 26.1 + 2*i/10000
            db.execute("""INSERT INTO detections(id,segment,asset,latitude,longitude,confidence,
                          offset,accuracy,bbox,image) VALUES(?,'sample-survey',?,?,91.7,0.9,?,5,'[0,0,1,1]','sample.jpg')""",
                       (rid, rid, lat, i*2000))
            db.execute("""INSERT INTO web_reports(id,source,source_id,title,description,place,
                       original_lat,original_lon,lat,lon,evidence,captured)
                       VALUES(?,'video','sample-survey',?,'Synthetic demonstration footage',
                       'Demo route',?,91.7,?,91.7,'/instances/sample.jpg',?)""",
                       (rid, f"[Demo] Pothole detection {i:02}", lat, lat, f"2026-01-01T00:00:{2*i:02}Z"))


if __name__ == "__main__":
    seed(root)
