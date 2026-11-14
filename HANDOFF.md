# Handoff: SwingCheck (golf swing form analyzer)

Prompt to start Claude Code on the laptop:
"Read HANDOFF.md and README.md and continue from Next steps."

## Goal
Self-hosted swing form analyzer on Matt's Lightsail server instead of paying for a TrackMan.
Matt only cares about swing form (not ball data). He films face-on and down-the-line,
at 30, 120 and 240 fps. He wants to compare his swing to Max Homa's.

## Where things are
- Code: GitHub `Hollmatt1/Claude`, branch `swingcheck` (public repo; never commit `.env` or passwords).
- Server: Lightsail instance `BGCraft-l`, Ubuntu, 8 GB RAM / 2 vCPU, static IP 100.59.211.221,
  console region us-east-2 page, instance in Virginia (us-east-1). Also runs other things (BGCraft,
  possibly the Miniflux RSS reader).
- On the server: `~/swingcheck` (git clone of the branch), `~/swingcheck/.env` (login password,
  BIND=0.0.0.0), `~/swingcheck/data` (uploaded swings). Login user is `golf`; the password is in
  `.env` on the server (`grep APP_PASSWORD ~/swingcheck/.env`).
- Install/update command (run on the server):
  `curl -fsSL https://raw.githubusercontent.com/Hollmatt1/Claude/swingcheck/install.sh | bash`

## Status as of 2026-11-14
- Installed and running in Docker on BGCraft-l, listening on port 8077 (`docker compose ps` in `~/swingcheck`).
- NOT reachable yet: Lightsail's firewall doesn't allow port 8077.
- The pose model and analysis were only tested with synthetic swings (the cloud session couldn't download
  the MediaPipe model). No real video has been analyzed yet.
- The cloud Claude session couldn't reach AWS (network allowlist), so the firewall step was left undone.

## Next steps
1. Make the app reachable. Either:
   - open TCP 8077 in Lightsail (instance > Networking > IPv4 firewall, or
     `aws lightsail open-instance-public-ports --region us-east-1 --instance-name BGCraft-l --port-info fromPort=8077,toPort=8077,protocol=TCP`), or
   - move it to port 80 if nothing else uses it: `sudo ss -ltn | grep ':80 '`; if free,
     `echo PORT=80 >> ~/swingcheck/.env` and rerun the install command.
   If Miniflux/Caddy already holds 80/443, add a site block in that Caddyfile
   (`swing.<domain> { request_body { max_size 600MB } reverse_proxy <host>:8077 }`) and keep BIND=127.0.0.1 or use the docker network.
2. Open http://100.59.211.221:8077 (or :80), log in, upload a real swing. Check the report and
   `docker compose logs -f` for errors (MediaPipe import, model path, ffmpeg).
3. Tune thresholds in `app/analyze.py` against real swings if any check looks wrong.
   Phase detection (address/top/impact/finish) uses hand height and speed; tempo uses a 4%-of-max-speed
   threshold for takeaway.
4. Matt uploads a Max Homa clip from the same camera angle with "reference swing" ticked; check the comparison view.
5. If Minecraft players notice lag during analysis, add `cpus: 1.0` to the service in docker-compose.yml.
6. Later: HTTPS on a subdomain.
