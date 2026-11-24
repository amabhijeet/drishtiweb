"""Run only against a fresh disposable web + processing server (writes test evidence)."""
import base64
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import tempfile
import time
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
        page.goto(base+"/")
        page.get_by_role("link",name="Open workspace").click()
        assert page.url.endswith("/admin")
        assert page.get_by_role("heading",name="Operations overview").is_visible()
        page.goto(base+"/admin/videos")
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
        deadline = time.monotonic() + 120
        while True:
            response = context.request.get(base + "/admin/videos", params={"q":prefix, "status":"done"})
            assert response.ok
            if response.text().count('>Open player') == 3:
                break
            if time.monotonic() >= deadline:
                raise AssertionError("Three accepted recordings did not finish processing")
            time.sleep(0.25)
        for width in (390,768,1440):
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
        library = base + "/admin/videos"
        assert page.goto(library + "?q=unmatched-" + prefix, wait_until="domcontentloaded").ok
        assert page.get_by_text("No matching recordings", exact=True).is_visible()
        assert page.request.get(library + "/missing-" + prefix).status == 404
        assert page.goto(library + "?status=done&survey=" + prefix + "-camera-0",wait_until="domcontentloaded").ok
        assert page.locator(".video-recordings article").count() == 1, page.locator("main").inner_text()
        page.locator(".video-recordings a[href*='/admin/videos/']").click()
        page.wait_for_function("document.querySelector('#recording').readyState >= 1")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        rejected = page.evaluate("""async () => {
          const form = new FormData(document.querySelector('#trim-form'));
          form.set('title', 'Invalid cut');
          form.set('start', '0.2');
          form.set('end', '10');
          return (await fetch(location.href, {method:'POST', body:form})).status;
        }""")
        assert rejected == 400
        page.locator('[name=title]').fill("Review cut")
        page.locator('[name=start]').fill("0.2")
        page.locator('[name=end]').fill("0.7")
        page.get_by_role("button",name="Preview trim").click()
        page.wait_for_function("document.querySelector('#recording').paused && document.querySelector('#recording').currentTime >= 0.7")
        page.get_by_role("button",name="Save trim").click()
        page.get_by_text("Review cut",exact=True).wait_for()
        export = page.get_by_role("link",name="Download MP4").get_attribute("href")
        exported = context.request.get(base + export)
        assert exported.ok and exported.body() != clips[0]
        cut = Path(folder) / "trimmed.mp4"
        cut.write_bytes(exported.body())
        seconds = float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(cut)]))
        assert 0.4 <= seconds <= 0.6, seconds
        assert context.request.get(base + f"/admin/segments/{prefix}-0/video").body() == clips[0]
        played = page.evaluate("""async prefix => Promise.all([0,1,2].map(async i=>{
          const v=document.createElement('video'); v.muted=true; document.body.append(v);
          v.src='/admin/segments/'+prefix+'-'+i+'/video';
          await v.play();
          await new Promise((resolve,reject)=>{v.onended=resolve;v.onerror=reject;setTimeout(()=>reject(Error('playback timeout')),10000)});
          return v.videoWidth;
        }))""",prefix)
        assert played==[160,160,160] and not errors,(played,errors)
        print("PASS: filtered video library, in-page trim preview, saved clip, MP4 export and original byte preservation.")
        print("PASS: 12 viewport/route combinations, maps, login, 3 parallel segment uploads + duplicate, 3 completed jobs, range responses, GPX views and simultaneous Chromium playback.")
        browser.close()


if __name__=="__main__":
    main()
