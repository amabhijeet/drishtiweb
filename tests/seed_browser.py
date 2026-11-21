"""Seed a disposable, initialized database with a public gallery for browser tests."""
import io
import sqlite3
import sys
from pathlib import Path
from PIL import Image

def seed(directory, clip):
    image=io.BytesIO()
    Image.new("RGB",(40,30),"blue").save(image,"JPEG")
    with sqlite3.connect(Path(directory)/"drishti.sqlite3") as conn:
        conn.execute("INSERT INTO web_reports(id,title,lat,lon,status) VALUES('browser-gallery','Test observation',26,91,'Published')")
        for i in range(2):
            conn.execute("INSERT INTO web_media VALUES(?,?,?,?,?)",(f"photo-{i}","browser-gallery","photo","test.jpg",image.getvalue()))
            conn.execute("INSERT INTO web_media VALUES(?,?,?,?,?)",(f"video-{i}","browser-gallery","video","test.mp4",Path(clip).read_bytes()))

if __name__=="__main__":
    seed(*sys.argv[1:])
