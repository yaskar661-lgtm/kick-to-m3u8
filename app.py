from flask import Flask, redirect
from curl_cffi import requests
import re
import time
import os

app = Flask(__name__)

# Gelişmiş Cache Yapısı: { username: { "url": ..., "time": ..., "playback_id": ... } }
STREAM_CACHE = {}
CACHE_TTL = 30  # IVS token süresine göre optimize edildi

def get_chromium_headers():
    """Streamlink mantığıyla tam uyumlu tarayıcı header setini üretir"""
    return {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://kick.com/",
        "Origin": "https://kick.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    }

def extract_playback_id(url):
    """M3U8 URL'sinden benzersiz playback/channel ID'sini ayıklar"""
    match = re.search(r'/channel/([^/\?]+)', url)
    return match.group(1) if match else None

def get_stream(username, force_refresh=False):
    current_time = time.time()
    
    # 1. Önbellek (Cache) Kontrolü
    if not force_refresh and username in STREAM_CACHE:
        cached_data = STREAM_CACHE[username]
        if current_time - cached_data["time"] < CACHE_TTL:
            return cached_data["url"]

    try:
        # Streamlink'in kullandığı direkt livestream API endpoint'i
        api_url = f"https://kick.com/api/v2/channels/{username}/livestream"
        headers = get_chromium_headers()
        
        # curl_cffi ile tarayıcı parmak izini taklit ederek istek atıyoruz
        response = requests.get(api_url, headers=headers, impersonate="chrome", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # API yanıtından 'playback_url' alanını direkt çekiyoruz (Regex ile aramaya gerek kalmaz)
            livestream_data = data.get("data")
            if livestream_data and livestream_data.get("playback_url"):
                m3u8_url = livestream_data["playback_url"]
                
                playback_id = extract_playback_id(m3u8_url)
                
                # Yeni veriyi cache'e işle
                STREAM_CACHE[username] = {
                    "url": m3u8_url,
                    "time": current_time,
                    "playback_id": playback_id
                }
                return m3u8_url
                            
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
        return "Yayın bulunamadı veya kanal kapalı.", 404

@app.route('/refresh/<username>')
def refresh_stream(username):
    username = username.lower().strip()
    
    if username in STREAM_CACHE:
        del STREAM_CACHE[username]
        
    stream_url = get_stream(username, force_refresh=True)
    
    if stream_url:
        return redirect(stream_url)
    else:
        return f"[{username}] için taze yayın adresi çekilemedi.", 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
