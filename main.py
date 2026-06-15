import os
import json
import base64
import hashlib
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
import uvicorn

from kms_pqc import KMSServer
from video_processor import VideoProcessor
from streaming_service import StreamingService

app = FastAPI(title="PQC OTT System", version="1.1")

kms = KMSServer()
video_proc = VideoProcessor("vid.webm", "cdn_storage")
streaming_service = StreamingService(kms, video_proc)

ROTATION_INTERVAL = 10

class LoginRequest(BaseModel):
    username: str
    password: str

@app.on_event("startup")
async def startup_event():
    print("\n" + "="*70)
    print("System PQC OTT się uruchamia...")
    print("="*70)
    
    cdn_path = "cdn_storage"
    if not os.path.exists(cdn_path):
        os.makedirs(cdn_path)
    
    segment_files = sorted([f for f in os.listdir(cdn_path) if f.startswith("segment_") and f.endswith(".ts")])
    
    if not segment_files:
        print("[Startup] Segmentacja wideo...")
        video_proc.segment_video()
        segment_files = [f for f in os.listdir(cdn_path) if f.startswith("segment_") and f.endswith(".ts")]
        
        num_segments = len(segment_files)
        print(f"[Startup] Szyfrowanie {num_segments} segmentów z rotacją klucza AES-256 (co {ROTATION_INTERVAL} segmentów)...")
        
        keys_map = {}
        for i in range(0, max(1, num_segments + ROTATION_INTERVAL), ROTATION_INTERVAL):
            keys_map[i] = os.urandom(32)
            
        video_proc.encrypt_segments(keys_map, interval=ROTATION_INTERVAL)
        
        serializable_map = {str(k): base64.b64encode(v).decode() for k, v in keys_map.items()}
        keys_file_path = os.path.join(cdn_path, ".content_keys.json")
        with open(keys_file_path, 'w') as f:
            json.dump(serializable_map, f)
            
        streaming_service.set_content_keys(keys_map)
        print("[Startup] Przetwarzanie wideo ukończone")
    else:
        print(f"[Startup] Znaleziono {len(segment_files)} segmentów")
        keys_file_path = os.path.join(cdn_path, ".content_keys.json")
        if os.path.exists(keys_file_path):
            try:
                with open(keys_file_path, 'r') as f:
                    sm = json.load(f)
                    keys_map = {int(k): base64.b64decode(v) for k, v in sm.items()}
                streaming_service.set_content_keys(keys_map)
                print("[Startup] Załadowano istniejące klucze rotacyjne AES")
            except (IOError, OSError, ValueError, KeyError) as e:
                print(f"[Startup] Błąd wczytywania kluczy: {e}")
        else:
            print("[Startup] Brakuje mapy kluczy! Usuń katalog cdn_storage i uruchom ponownie.")
            
    print("\n" + "="*70)
    print("System PQC OTT gotowy")
    print("Dostęp: http://localhost:8000/")
    print("="*70 + "\n")


@app.get("/", response_class=HTMLResponse)
def dashboard():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>PQC OTT System - Logowanie</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', sans-serif; background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
            .login-container { background: white; border-radius: 15px; box-shadow: 0 20px 60px rgba(0,0,0,0.4); width: 100%; max-width: 450px; padding: 40px; text-align: center; }
            .header h1 { color: #333; margin-bottom: 10px; font-size: 2.2em; }
            .header p { color: #666; margin-bottom: 30px; font-size: 1em; }
            .form-group { margin-bottom: 20px; text-align: left; }
            .form-group label { display: block; margin-bottom: 8px; color: #555; font-weight: bold; }
            .form-group input { width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 8px; font-size: 1em; }
            button { width: 100%; background: #2a5298; color: white; padding: 15px; border: none; border-radius: 8px; font-size: 1.1em; font-weight: bold; cursor: pointer; margin-top: 10px; }
            .accounts-info { margin-top: 30px; padding: 15px; background: #f8f9fa; border-radius: 8px; text-align: left; font-size: 0.9em; color: #555; }
            .accounts-info h4 { margin-bottom: 10px; color: #333; }
            #errorMsg { color: #dc3545; margin-bottom: 15px; font-weight: bold; display: none; }
        </style>
    </head>
    <body>
        <div class="login-container">
            <div class="header">
                <h1>PQC OTT</h1>
                <p>Zaloguj się, aby uzyskać dostęp do strumienia</p>
            </div>
            <div id="errorMsg">Nieprawidłowy login lub hasło!</div>
            <form id="loginForm">
                <div class="form-group"><label>Nazwa użytkownika</label><input type="text" id="username" required></div>
                <div class="form-group"><label>Hasło</label><input type="password" id="password" required></div>
                <button type="submit">Zaloguj się</button>
            </form>
            <div class="accounts-info">
                <h4>Konta testowe:</h4>
                <ul><li><b>admin / admin</b> - Pełny dostęp</li><li><b>guest / guest</b> - Brak uprawnień</li></ul>
            </div>
        </div>
        <script>
            document.getElementById('loginForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const u = document.getElementById('username').value, p = document.getElementById('password').value;
                try {
                    const r = await fetch('/auth/login-user', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({username: u, password: p}) });
                    if (!r.ok) { document.getElementById('errorMsg').style.display = 'block'; return; }
                    const data = await r.json();
                    localStorage.setItem('sessionId', data.session_id);
                    localStorage.setItem('isAuthorized', data.is_authorized);
                    window.location.href = '/streaming/video';
                } catch (err) { document.getElementById('errorMsg').style.display = 'block'; }
            });
        </script>
    </body>
    </html>
    """
    return html

@app.post("/auth/login-user")
def login_user(req: LoginRequest):
    if req.username == "admin" and req.password == "admin":
        result = streaming_service.create_session("User-Admin-Premium", is_authorized=True)
        return {"status": "success", "session_id": result["session_id"], "is_authorized": True}
    elif req.username == "guest" and req.password == "guest":
        result = streaming_service.create_session("User-Guest-Basic", is_authorized=False)
        return {"status": "success", "session_id": result["session_id"], "is_authorized": False}
    raise HTTPException(status_code=401, detail="Nieautoryzowany")

@app.get("/streaming/watermark")
def get_watermark(session_id: str):
    if session_id not in streaming_service.sessions:
        raise HTTPException(status_code=404, detail="Sesja nie znaleziona")
    
    session = streaming_service.sessions[session_id]
    if not session.is_authorized or not session.aes_keys:
        return {"status": "denied", "watermark": "BRAK_DOSTĘPU", "aes_preview": "Brak klucza"}
    
    first_key = session.aes_keys.get(0, b"")
    raw_data = f"{session.user_id}:{session.session_id}:{first_key.hex()}"
    watermark_hash = hashlib.sha256(raw_data.encode()).hexdigest()
    
    return {
        "status": "success",
        "user_id": session.user_id,
        "watermark_token": watermark_hash,
        "aes_preview": first_key.hex()[:16] + "..." 
    }

@app.get("/streaming/session-info")
def get_session_info(session_id: str):
    info = streaming_service.get_session_info(session_id)
    if "error" in info:
        raise HTTPException(status_code=404, detail=info["error"])
    return info

@app.get("/streaming/video/stream")
def get_video_stream(session_id: str):
    if session_id not in streaming_service.sessions:
        raise HTTPException(status_code=404, detail="Sesja nie znaleziona")

    session = streaming_service.sessions[session_id]
    if not session.is_authorized:
        raise HTTPException(status_code=403, detail="Brak dostępu")

    segment_ids = streaming_service.get_available_segments()
    if not segment_ids:
        raise HTTPException(status_code=404, detail="Brak segmentów")

    def stream_generator():
        current_interval = -1
        for sid in segment_ids:
            interval = (sid // ROTATION_INTERVAL) * ROTATION_INTERVAL
            if interval != current_interval:
                print(f"\n[KMS PQC] ROTACJA KLUCZA: Granica segmentu {sid}.")
                print(f"[KMS PQC] Symulacja zapytania z odtwarzacza: Pobieranie nowej paczki klucza AES!")
                current_interval = interval
                
            data, meta = streaming_service.get_segment(session_id, sid, interval=ROTATION_INTERVAL)
            if data is not None:
                yield data 

    return StreamingResponse(
        stream_generator(),
        media_type="video/mp2t",
        headers={"Content-Disposition": "inline; filename=video.ts"}
    )

@app.get("/streaming/video/stream-encrypted")
def get_encrypted_video_stream(session_id: str):
    """Zwraca strumień WSZYSTKICH zaszyfrowanych segmentów dla przeglądu"""
    if session_id not in streaming_service.sessions:
        raise HTTPException(status_code=404, detail="Sesja nie znaleziona")

    segment_ids = streaming_service.get_available_segments()
    if not segment_ids:
        raise HTTPException(status_code=404, detail="Brak segmentów")

    print(f"[Encrypted Stream] Pobieranie {len(segment_ids)} ALL encrypted segmentów")

    def stream_generator():
        for sid in segment_ids:
            segment_file = os.path.join("cdn_storage", f"segment_{sid:03d}.ts")
            try:
                with open(segment_file, 'rb') as f:
                    yield f.read()
            except (IOError, OSError) as e:
                print(f"[Encrypted Stream] Błąd: {e}")

    return StreamingResponse(
        stream_generator(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=encrypted_all.bin"}
    )

@app.get("/streaming/video", response_class=HTMLResponse)
def stream_video_page():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Video Player - PQC OTT System</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #1a1a1a; color: #fff; padding: 20px; }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; padding-bottom: 20px; border-bottom: 2px solid #667eea; }
            .header h1 { color: #667eea; font-size: 1.5em; }
            .back-btn { background: #667eea; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; }
            .back-btn:hover { background: #764ba2; }
            .session-info { background: #2a2a2a; padding: 20px; border-radius: 10px; margin-bottom: 20px; display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
            .info-item { padding: 15px; background: #333; border-radius: 5px; border-left: 3px solid #667eea; }
            .info-item label { font-size: 0.85em; color: #aaa; display: block; margin-bottom: 5px; }
            .info-item value { font-weight: bold; color: #fff; word-break: break-all; font-family: monospace; font-size: 0.9em; display: block; }
            .access-granted { border-left-color: #28a745; color: #28a745; }
            .access-denied { border-left-color: #dc3545; color: #dc3545; }
            .watermark-box { border-left-color: #f39c12; background: #2c210b; }
            .watermark-box value { color: #f39c12; }
            .video-container { background: #000; border-radius: 10px; overflow: hidden; margin-bottom: 30px; position: relative; }
            video { width: 100%; display: block; background: #000; }
            .watermark-overlay { position: absolute; bottom: 60px; right: 20px; background: rgba(0,0,0,0.6); color: rgba(255,255,255,0.5); padding: 5px 10px; border-radius: 5px; font-family: monospace; font-size: 0.8em; pointer-events: none; display: none; }
            .access-denied-message { text-align: center; padding: 100px 20px; background: #dc3545; border-radius: 10px; margin-bottom: 30px; }
            .controls { display: flex; gap: 10px; margin-top: 20px; }
            button.play-btn { background: #667eea; color: white; padding: 12px 24px; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; font-size: 1em; }
            button.play-btn:disabled { background: #666; cursor: not-allowed; }
            .status-text { margin-top: 10px; font-size: 0.9em; color: #aaa; }
            .logout-btn { background: #dc3545; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; margin-left: 10px;}
        </style>
        <script src="https://cdn.jsdelivr.net/npm/mpegts.js@latest/dist/mpegts.js"></script>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>PQC OTT Video Player</h1>
                <div><button class="back-btn" onclick="goHome()">Odśwież</button><button class="logout-btn" onclick="logout()">Wyloguj</button></div>
            </div>
            <div class="session-info">
                <div class="info-item" id="userIdInfo"><label>Użytkownik</label><value id="userId">Ładowanie...</value></div>
                <div class="info-item" id="accessStatusInfo"><label>Uprawnienia</label><value id="accessStatus">Ładowanie...</value></div>
                <div class="info-item watermark-box" id="watermarkInfo"><label>Cyfrowy Znak Wodny (ID)</label><value id="watermarkToken">Weryfikacja...</value></div>
                <div class="info-item watermark-box"><label>Początkowy Klucz AES</label><value id="aesPreview">Oczekiwanie...</value></div>
            </div>
            <div id="videoSection"></div>
            <div class="controls"><button onclick="playVideo()" id="playBtn" class="play-btn">Odtwórz Wideo</button></div>
            <div class="status-text" id="statusText">System gotowy.</div>
            <div class="status-text" style="color:#f39c12">Info dla testera: Obserwuj konsolę terminala serwera, aby zobaczyć powiadomienia o zrotowaniu klucza ML-KEM podczas odtwarzania wideo!</div>
        </div>
        <script>
            let sessionId = localStorage.getItem('sessionId');
            let isAuthorized = localStorage.getItem('isAuthorized') === 'true';
            
            function logout() { localStorage.clear(); window.location.href = '/'; }

            async function loadSessionInfo() {
                try {
                    const resp = await fetch(`/streaming/session-info?session_id=${sessionId}`);
                    if (!resp.ok) return;
                    const sessionInfo = await resp.json();
                    
                    document.getElementById('userId').textContent = sessionInfo.user_id;
                    const accessEl = document.getElementById('accessStatusInfo');
                    
                    if (sessionInfo.is_authorized) {
                        accessEl.className = 'info-item access-granted';
                        document.getElementById('accessStatus').textContent = 'DOSTĘP PRZYZNANY';
                    } else {
                        accessEl.className = 'info-item access-denied';
                        document.getElementById('accessStatus').textContent = 'ZABLOKOWANE';
                    }

                    const wmResp = await fetch(`/streaming/watermark?session_id=${sessionId}`);
                    const wmInfo = await wmResp.json();
                    
                    document.getElementById('watermarkToken').textContent = wmInfo.watermark_token;
                    document.getElementById('aesPreview').textContent = wmInfo.aes_preview;
                    
                    if(wmInfo.status === 'success') {
                        const overlay = document.getElementById('wmOverlay');
                        if(overlay) {
                            overlay.textContent = "ID: " + wmInfo.watermark_token.substring(0, 15);
                            overlay.style.display = 'block';
                        }
                    }
                } catch (e) { console.error('Error loading session info:', e); }
            }
            
            let mpegtsPlayer = null;
            
            async function playVideo() {
                const videoSection = document.getElementById('videoSection');
                const playBtn = document.getElementById('playBtn');
                const statusText = document.getElementById('statusText');
                
                if (!isAuthorized) {
                    playBtn.disabled = true;
                    playBtn.style.display = 'none';
                    statusText.textContent = 'Pobieranie zaszyfrowanych segmentow...';
                    
                    videoSection.innerHTML = `<div class="video-container" style="position:relative;">
                        <canvas id="noiseCanvas" width="640" height="360" style="width:100%; background:#000; display:block;"></canvas>
                        <div id="wmOverlay" class="watermark-overlay">ENCRYPTED</div>
                    </div>`;

                    try {
                        console.log('Guest: Pobieranie encrypted segments...');
                        statusText.textContent = 'Pobieranie encrypted segmentow...';
                        
                        const canvas = document.getElementById('noiseCanvas');
                        const ctx = canvas.getContext('2d');
                        let byteOffset = 0;
                        
                        const videoUrl = `/streaming/video/stream-encrypted?session_id=${sessionId}`;
                        const response = await fetch(videoUrl);
                        if (!response.ok) { statusText.textContent = 'Blad: ' + response.status; return; }
                        
                        const reader = response.body.getReader();
                        let chunkCount = 0;
                        
                        while (true) {
                            const {done, value} = await reader.read();
                            if (done) break;
                            
                            chunkCount++;
                            
                            // Rysuj bieżący segment na canvasie bez agregacji
                            const imageData = ctx.createImageData(canvas.width, canvas.height);
                            const pixelData = imageData.data;
                            
                            for (let i = 0; i < pixelData.length; i += 4) {
                                const byteIndex = (i / 4) % value.length;
                                const byte = value[byteIndex];
                                pixelData[i] = byte;
                                pixelData[i + 1] = byte;
                                pixelData[i + 2] = byte;
                                pixelData[i + 3] = 255;
                            }
                            ctx.putImageData(imageData, 0, 0);
                            
                            statusText.textContent = `Segment ${chunkCount}: ${(value.length/1024).toFixed(0)} KB`;
                        }
                        
                        console.log('Skonczone: ', chunkCount, 'segments');
                        statusText.textContent = `GOTOWE! Pobrano ${chunkCount} segmentow`;
                    } catch (err) { 
                        console.error('Guest error:', err);
                        statusText.textContent = 'Blad: ' + err.message; 
                    }
                    return;
                }

                playBtn.disabled = true;
                statusText.textContent = 'Zestawianie bezpiecznego tunelu...';
                videoSection.innerHTML = `<div class="video-container"><video id="videoPlayer" controls autoplay></video><div id="wmOverlay" class="watermark-overlay"></div></div>`;

                try {
                    const videoUrl = `/streaming/video/stream?session_id=${sessionId}`;
                    const response = await fetch(videoUrl);
                    if (!response.ok) { statusText.textContent = 'Błąd serwera strumieniowania.'; return; }
                    const blob = await response.blob();
                    statusText.textContent = 'Wideo pobrane. Decodowanie i nakładanie watermarku...';

                    const video = document.getElementById('videoPlayer');
                    const videoObjectURL = URL.createObjectURL(blob);
                    
                    loadSessionInfo();

                    if (typeof window.mpegts !== 'undefined') {
                        mpegtsPlayer = window.mpegts.createPlayer({ type: 'mse', isLive: false, url: videoObjectURL });
                        mpegtsPlayer.attachMediaElement(video);
                        mpegtsPlayer.load();
                        mpegtsPlayer.play().then(() => {
                            statusText.textContent = 'Transmisja zabezpieczona. Obserwuj terminal serwera dla zdarzeń rotacji klucza!';
                            playBtn.style.display = 'none';
                        }).catch(err => { video.src = videoObjectURL; video.play(); });
                    } else {
                        video.src = videoObjectURL; video.play();
                    }
                } catch (err) { statusText.textContent = 'Błąd krytyczny odtwarzacza.'; }
            }
            function goHome() { location.reload(); }
            window.onload = () => {
                if (!sessionId) { window.location.href = '/'; return; }
                loadSessionInfo();
            };
        </script>
    </body>
    </html>
    """
    return html

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)