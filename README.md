# SwingCheck

A self-hosted swing form analyzer. Upload a swing video from your phone and you get back:

- a slowed-down copy of the video with your skeleton, hand path, and address-position reference lines drawn on it
- stills of your address, top, impact and finish positions
- a list of form checks graded good / check / bad, with a fix for each problem and the most important one shown first
- an optional side-by-side comparison with a reference swing (for example, a pro you upload yourself)

It uses Google's MediaPipe Pose model on the CPU. You don't need a GPU or any paid service.

## What it checks

**Face-on** (camera facing your chest, in line with the ball)
- Tempo (backswing : downswing ratio)
- Head movement in the backswing
- Head position at impact (moving toward the target early)
- Hip sway in the backswing
- Weight shift toward the target at impact
- Lead arm straightness at the top
- Finish balance (hips over the lead foot)

**Down-the-line** (camera behind your hands, pointing at the target)
- Tempo
- Spine tilt at address
- Knee flex at address
- Spine angle kept through impact (standing up)
- Hips moving toward the ball (early extension)
- Head height change at impact
- Downswing hand path vs backswing path (over the top)

The camera angle is detected automatically. You can also choose it when you upload. Left- and right-handed golfers are detected automatically.

## Comparing to a pro

1. Get a clip of the pro's swing filmed from the same angle you use (face-on or down-the-line). A single swing, the full body in frame, and a camera that doesn't move work best. Practice-range and slow-motion clips work better than TV broadcast clips with cuts or camera pans.
2. Upload it with **"This is a reference swing"** ticked and a label such as `Max Homa`.
3. Each of your swings filmed from the same angle now shows your four key positions next to the pro's, plus a table of your numbers next to theirs. If you have more than one reference, you can switch between them on the report page.

Both clips are measured the same way, so any systematic error in a measurement affects your number and the pro's number equally.

## Quick install

On the server, run:

```bash
curl -fsSL https://raw.githubusercontent.com/Hollmatt1/Claude/swingcheck/install.sh | bash
```

It installs Docker if needed, adds swap, generates a password, starts the app on port 8077, and prints the address and login.

## Deploying on Lightsail (manual)

These steps assume Ubuntu or Debian with about 2 GB of RAM.

```bash
# 1. Install Docker (skip if you already have it)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER   # log out and back in after this

# 2. Copy this folder to the server, then:
cd swingcheck
cp .env.example .env
nano .env                       # set APP_PASSWORD
docker compose up -d --build    # the first build takes a few minutes
```

The app listens on `127.0.0.1:8077`. Put it behind HTTPS with your reverse proxy.

**Caddy** (`/etc/caddy/Caddyfile`):
```
swing.yourdomain.com {
    request_body {
        max_size 600MB
    }
    reverse_proxy 127.0.0.1:8077
}
```

**nginx**:
```nginx
server {
    server_name swing.yourdomain.com;
    client_max_body_size 600M;
    proxy_request_buffering off;
    location / {
        proxy_pass http://127.0.0.1:8077;
        proxy_read_timeout 300s;
        proxy_set_header Host $host;
    }
    # plus your usual listen 443 ssl / certbot lines
}
```

Make sure ports 80 and 443 are open in the Lightsail networking tab. On your iPhone, open the site in Safari and use Share → Add to Home Screen to get an app icon.

To update after changing the code, run `docker compose up -d --build`. Your swings are stored in `./data`.

## Filming tips

- Put the phone at hip height, about 10–12 ft away, with your whole body and the club in frame for the entire swing.
- Use a tripod or lean the phone against your bag. Camera movement is measured as body movement.
- Record one swing per clip and trim it to about 1 second before takeaway through the finish.
- Slow-mo (120 or 240 fps) gives the smoothest tracking and the most precise impact frame. Normal 30 or 60 fps works too.
- Keep other people out of the shot.

## Limits

- It measures your body, not the club or the ball. It can't measure club path, face angle, ball speed or spin.
- Measurements are 2D from one camera, so a few checks (lead arm angle, hand path) are approximate. Checks where the body parts were hard to see are labelled low confidence.
- The inch values are approximate. They assume a 15 in shoulder width and a 20 in torso.
- If iOS exports a slow-mo video as slowed-down 30 fps playback, the seconds shown for tempo will be too long, but the tempo ratio is still correct. The report says when this looks like it happened.
- Processing takes about 20–90 seconds per clip on a 2 GB Lightsail instance. Clips are processed one at a time.

## Running tests

```bash
pip install -r requirements.txt
python tests/test_analyze.py   # synthetic swings, including injected faults
python tests/test_e2e.py       # upload → analysis → rendered video, using a mocked pose model
```
