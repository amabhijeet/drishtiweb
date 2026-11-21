"""Run only against a fresh disposable web + processing server (writes test evidence)."""
import base64
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import tempfile
import subprocess
import uuid

from playwright.sync_api import sync_playwright


def main():
    base = os.environ["TEST_WEB_URL"]
    with tempfile.TemporaryDirectory() as folder, sync_playwright() as pw:
        clips = []
        for color in ("blue","red","green"):
            clip = Path(folder) / (color+".mp4")
            subprocess.run(["ffmpeg","-loglevel","error","-f","lavfi","-i",f"color={color}:s=160x120:r=10","-t","1","-c:v","libx264","-pix_fmt","yuv420p",str(clip)],check=True)
            clips.append(clip.read_bytes())
        assert len(set(clips))==3
        browser = pw.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH"),args=["--no-sandbox","--autoplay-policy=no-user-gesture-required"])
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        errors = []
        page.on("pageerror",lambda exc: errors.append(str(exc)))
        for width in (390,768,1440):
            page.set_viewport_size({"width":width,"height":850})
            for route in ("/","/map","/docs","/login"):
                assert page.goto(base+route,wait_until="domcontentloaded").ok
                assert page.locator("h1").is_visible()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (route,width)
                if route in ("/","/map"):
                    assert page.locator(".leaflet-map-pane").count()==1
        fixture = os.getenv("TEST_FIXTURE_REPORT")
        if fixture:
            page.goto(base+"/map")
            page.locator("#search").fill(fixture)
            page.locator(".leaflet-marker-icon").first.click()
            page.get_by_text("View report and gallery",exact=False).click()
            assert page.url.endswith("/reports/"+fixture)
            page.wait_for_function("Array.from(document.querySelectorAll('main img')).filter(i=>i.complete && i.naturalWidth>0).length===2")
            ok = page.evaluate("""async () => Promise.all([...document.querySelectorAll('main video')].map(async v=>{
              v.muted=true; await v.play();
              await new Promise((resolve,reject)=>{v.onended=resolve; v.onerror=reject; setTimeout(()=>reject(Error('timeout')),10000)});
              return v.videoWidth;
            }))""")
            assert ok==[160,160],ok
        page.goto(base+"/admin")
        assert page.url.endswith("/login")
        page.locator('[name=user]').fill(os.environ["TEST_USER"])
        page.locator('[name=password]').fill(os.environ["TEST_PASSWORD"])
        page.get_by_role("button",name="Sign in").click()
        page.wait_for_url("**/admin")
        prefix = "browser-"+uuid.uuid4().hex[:10]
        stamp = datetime.now(timezone.utc).replace(microsecond=0)
        points = "".join(f'<trkpt lat="26" lon="91"><time>{(stamp+timedelta(seconds=i)).isoformat()}</time><extensions><d:videoOffsetMs>{1000*i}</d:videoOffsetMs><d:accuracyMeters>5</d:accuracyMeters></extensions></trkpt>' for i in range(2))
        track = f'<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:d="urn:drishti:extensions:1" version="1.1"><metadata><extensions><d:videoDurationMs>1000</d:videoDurationMs></extensions></metadata><trk><trkseg>{points}</trkseg></trk></gpx>'
        result = page.evaluate("""async ({prefix, stamp, track, encoded}) => {
          async function upload(i) {
            const bytes = Uint8Array.from(atob(encoded[i]), c=>c.charCodeAt(0));
            const form=new FormData();
            form.set('csrf',document.querySelector('[name=csrf]').value);
            form.set('kind','video');
            form.set('metadata',JSON.stringify({schemaVersion:1,segmentId:prefix+'-'+i,sessionId:prefix+'-camera-'+i,sequence:0,startedAt:stamp,durationMs:1000,timebase:'videoOffsetMs'}));
            form.set('video',new Blob([bytes],{type:'video/mp4'}),'clip.mp4');
            form.set('gpx',new Blob([track],{type:'application/gpx+xml'}),'track.gpx');
            const r=await fetch('/admin/upload',{method:'POST',body:form});
            return [r.status,new URL(r.url).pathname];
          }
          return Promise.all([0,1,2,0].map(upload));
        }""",dict(prefix=prefix,stamp=stamp.isoformat(),track=track,encoded=[base64.b64encode(c).decode() for c in clips]))
        assert all(r==[200,"/admin"] for r in result), result
        page.wait_for_function("""async prefix => {
          const doc=new DOMParser().parseFromString(await (await fetch('/admin')).text(),'text/html');
          const jobs=[...doc.querySelectorAll('article')].filter(a=>a.querySelector('a[href*="/segments/"]') && a.textContent.includes(prefix));
          return jobs.length===3 && jobs.every(a=>a.textContent.includes('done'));
        }""",arg=prefix,timeout=120000)
        for width in (390,1440):
            page.set_viewport_size({"width":width,"height":850})
            for route in ("/admin","/admin/gps","/admin/segments/"+prefix+"-0/track"):
                assert page.goto(base+route,wait_until="domcontentloaded").ok
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (route,width)
            page.goto(base+"/admin")
        for i in range(3):
            url=base+f"/admin/segments/{prefix}-{i}"
            response=context.request.get(url+"/video",headers={"Range":"bytes=0-31"})
            assert response.status==206 and response.body()==clips[i][:32]
            assert context.request.get(url+"/video?download=1").body()==clips[i]
            assert context.request.get(url+"/track").ok
        played = page.evaluate("""async prefix => Promise.all([0,1,2].map(async i=>{
          const v=document.createElement('video'); v.muted=true; document.body.append(v);
          v.src='/admin/segments/'+prefix+'-'+i+'/video';
          await v.play();
          await new Promise((resolve,reject)=>{v.onended=resolve;v.onerror=reject;setTimeout(()=>reject(Error('playback timeout')),10000)});
          return v.videoWidth;
        }))""",prefix)
        assert played==[160,160,160] and not errors,(played,errors)
        print("PASS: 12 viewport/route combinations, maps, login, 3 parallel segment uploads + duplicate, 3 completed jobs, range responses, GPX views and simultaneous Chromium playback.")
        browser.close()


if __name__=="__main__":
    main()
