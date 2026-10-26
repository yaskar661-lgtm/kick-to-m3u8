from flask import Flask, redirect
from curl_cffi import requests
import re
import time
import os

app = Flask(__name__)

STREAM_CACHE = {}
CACHE_TTL = 30  

def get_stream(username, force_refresh=False):
    current_time = time.time()
    
    # Eğer zorla yenileme (force_refresh) istenmediyse ve cache'te varsa cache'ten ver
    if not force_refresh and username in STREAM_CACHE:
        cached_data = STREAM_CACHE[username]
        if current_time - cached_data["time"] < CACHE_TTL:
            return cached_data["url"]

    try:
        api_url = f"https://kick.com/api/v2/channels/{username}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        # curl_cffi ile tarayıcı imzası taklit ediyoruz
        response = requests.get(api_url, headers=headers, impersonate="chrome", timeout=10)
        
        if response.status_code == 200:
            api_content = response.text
            
            m3u8_patterns = [
                r'"([^"]+\.m3u8[^"]*)"',                  
                r'https?://[^\s<>"\']+\.m3u8\?[^\s<>"\']+'  
            ]
            
            for pattern in m3u8_patterns:
                matches = re.findall(pattern, api_content)
                if matches:
                    for match in matches:
                        if ".m3u8" in match:
                            match = match.encode('utf-8').decode('unicode_escape')
                            match = match.replace('\\/', '/')
                            
                            # Yeni linki önbelleğe kaydet
                            STREAM_CACHE[username] = {
                                "url": match,
                                "time": current_time
                            }
                            return match
                            
        return None
    except Exception as e:
        print(f"Hata oluştu ({username}): {e}")
        return None

@app.route('/stream/<username>')
def stream_redirect(username):
    username = username.lower().strip()
    stream_url = get_stream(username, force_refresh=False)
    
    if stream_url:
        return redirect(stream_url)
    else:
        return "Yayın bulunamadı veya korumaya takıldı.", 404

# --- RENDER'I ÖLDürmeden YENİLEME ROUTE'U ---
@app.route('/refresh/<username>')
def refresh_stream(username):
    username = username.lower().strip()
    
    # 1. Önce bu kullanıcının hafızadaki eski cache'ini tamamen siliyoruz
    if username in STREAM_CACHE:
        del STREAM_CACHE[username]
        
    # 2. Anında taze linki çekmeye zorluyoruz (force_refresh=True)
    stream_url = get_stream(username, force_refresh=True)
    
    if stream_url:
        # İstersen direkt yeni linke yönlendir, istersen başarılı mesajı ver
        return redirect(stream_url)
    else:
        return f"[{username}] için taze yayın adresi çekilemedi (Kanal kapalı olabilir).", 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
