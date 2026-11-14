# tizen-pc-mirror

TizenBrew module that shows your PC screen on a Samsung Tizen TV (tested target: Tizen 3.0).
Video only, no audio. The PC streams MJPEG frames over the local network.

## PC side
```
pip install mss pillow
python pc-server/server.py --allow <TV_IP>
```
Only the TV IP given with `--allow` can fetch the stream (port 8765).

## TV side
TizenBrew -> add GitHub module -> `muhammedmustafakurt/tizen-pc-mirror`.
Colour buttons: green = reconnect, yellow = change PC IP, blue = info.
Default PC address is `192.168.1.17`.
