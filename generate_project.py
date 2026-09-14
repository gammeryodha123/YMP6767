import os

APP_PY_CONTENT = '''import os
import io
import json
import requests
from flask import Flask, render_template_string, request, jsonify, send_file
import firebase_admin
from firebase_admin import credentials, auth, firestore
from PIL import Image

app = Flask(__name__)
app.secret_key = "super-secret-key-change-this-in-production"

cred_json = os.environ.get('FIREBASE_CREDENTIALS')
cred_path = os.path.join(os.path.dirname(__file__), 'serviceAccountKey.json')

db = None
try:
    if cred_json:
        cred_dict = json.loads(cred_json)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
    elif os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
    else:
        print("Warning: No Firebase credentials found! Running in sample mode.")
except Exception as e:
    print(f"Firebase initialization error: {e}")

def create_square_thumbnail(image_bytes, size=(300, 300)):
    img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    width, height = img.size
    min_dim = min(width, height)
    img = img.crop((
        (width - min_dim) / 2,
        (height - min_dim) / 2,
        (width + min_dim) / 2,
        (height + min_dim) / 2
    ))
    img.thumbnail(size)
    out_buffer = io.BytesIO()
    img.save(out_buffer, format='JPEG', quality=85)
    out_buffer.seek(0)
    return out_buffer

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/tracks', methods=['GET'])
def get_tracks():
    if not db:
        return jsonify([
            {"id": "1", "title": "Acoustic Breeze", "artist": "Benjamin Tissot", "cover_url": "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=300", "audio_url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"},
            {"id": "2", "title": "Creative Minds", "artist": "Bensound", "cover_url": "https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=300", "audio_url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3"}
        ])
    try:
        tracks = [{"id": doc.id, **doc.to_dict()} for doc in db.collection('tracks').stream()]
        return jsonify(tracks)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/verify-token', methods=['POST'])
def verify_token():
    id_token = request.json.get('idToken')
    if not id_token or not db:
        return jsonify({"success": False, "error": "Invalid setup"}), 400
    try:
        decoded = auth.verify_id_token(id_token)
        uid, email, name = decoded['uid'], decoded.get('email', ''), decoded.get('name', 'User')
        db.collection('users').document(uid).set({'email': email, 'name': name, 'last_login': firestore.SERVER_TIMESTAMP}, merge=True)
        return jsonify({"success": True, "uid": uid, "name": name})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 401

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PySpotify Clone</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://www.gstatic.com/firebasejs/10.8.0/firebase-app-compat.js"></script>
    <script src="https://www.gstatic.com/firebasejs/10.8.0/firebase-auth-compat.js"></script>
</head>
<body class="bg-black text-white h-screen flex flex-col font-sans overflow-hidden">
    <div class="flex-1 flex overflow-hidden">
        <aside class="w-64 bg-zinc-950 p-6 flex flex-col justify-between hidden md:flex border-r border-zinc-900">
            <div>
                <div class="text-green-500 font-bold text-xl mb-6">PySpotify</div>
                <nav class="space-y-4 font-semibold text-zinc-400">
                    <a href="#" class="flex items-center text-white">🏠 Home</a>
                    <a href="#" class="flex items-center hover:text-white">🔍 Search</a>
                </nav>
            </div>
            <div id="auth-section" class="border-t border-zinc-800 pt-4">
                <button id="login-btn" onclick="loginWithGoogle()" class="w-full bg-white text-black font-bold py-2 rounded-full">Sign in</button>
                <div id="user-profile" class="hidden flex justify-between items-center">
                    <span id="user-name" class="truncate max-w-[120px]">User</span>
                    <button onclick="logout()" class="text-xs text-zinc-400 underline">Log out</button>
                </div>
            </div>
        </aside>
        <main class="flex-1 bg-gradient-to-b from-zinc-900 to-black p-8 overflow-y-auto">
            <h1 class="text-3xl font-extrabold mb-8">Good afternoon</h1>
            <div id="track-list" class="grid grid-cols-2 md:grid-cols-4 gap-6"></div>
        </main>
    </div>
    <footer class="h-24 bg-zinc-950 border-t border-zinc-900 px-4 flex items-center justify-between">
        <div class="flex items-center space-x-4 w-1/4">
            <img id="player-cover" src="https://via.placeholder.com/60" class="w-14 h-14 rounded object-cover" />
            <div>
                <p id="player-title" class="font-semibold text-sm">Select a song</p>
                <p id="player-artist" class="text-xs text-zinc-400">---</p>
            </div>
        </div>
        <div class="flex flex-col items-center w-2/4 max-w-xl">
            <button onclick="togglePlay()" id="play-btn" class="bg-white text-black p-2 rounded-full mb-2">▶</button>
            <div class="w-full flex items-center space-x-3 text-xs text-zinc-400">
                <span id="curr-time">0:00</span>
                <input type="range" id="seek-bar" value="0" max="100" class="w-full h-1 bg-zinc-700" onchange="seekAudio()">
                <span id="duration">0:00</span>
            </div>
        </div>
        <div class="w-1/4"></div>
    </footer>
    <audio id="audio-engine"></audio>

    <script>
        const firebaseConfig = {
          apiKey: "AIzaSyArZJxJ6N4YHh8-0fbyH8c-MQ1V3jzbP9k",
          authDomain: "python-music-app-67.firebaseapp.com",
          projectId: "python-music-app-67"
        };
        firebase.initializeApp(firebaseConfig);

        const audio = document.getElementById('audio-engine');
        let isPlaying = false;

        window.addEventListener('DOMContentLoaded', async () => {
            const res = await fetch('/api/tracks');
            const tracks = await res.json();
            const container = document.getElementById('track-list');
            tracks.forEach(track => {
                const card = document.createElement('div');
                card.className = "bg-zinc-900/60 p-4 rounded-lg cursor-pointer hover:bg-zinc-800/80";
                card.onclick = () => loadAndPlay(track);
                card.innerHTML = `<img src="${track.cover_url}" class="w-full aspect-square object-cover mb-4 rounded" /><h3 class="font-bold text-sm truncate">${track.title}</h3><p class="text-xs text-zinc-400 truncate">${track.artist}</p>`;
                container.appendChild(card);
            });
        });

        function loadAndPlay(t) {
            document.getElementById('player-cover').src = t.cover_url;
            document.getElementById('player-title').innerText = t.title;
            document.getElementById('player-artist').innerText = t.artist;
            audio.src = t.audio_url;
            audio.play();
            isPlaying = true;
            document.getElementById('play-btn').innerText = '⏸';
        }

        function togglePlay() {
            if(!audio.src) return;
            isPlaying ? audio.pause() : audio.play();
            isPlaying = !isPlaying;
            document.getElementById('play-btn').innerText = isPlaying ? '⏸' : '▶';
        }

        audio.ontimeupdate = () => {
            if(!audio.duration) return;
            document.getElementById('seek-bar').value = (audio.currentTime / audio.duration) * 100;
            document.getElementById('curr-time').innerText = Math.floor(audio.currentTime/60) + ":" + String(Math.floor(audio.currentTime%60)).padStart(2, '0');
        };

        function seekAudio() { audio.currentTime = (document.getElementById('seek-bar').value / 100) * audio.duration; }

        async function loginWithGoogle() {
            const provider = new firebase.auth.GoogleAuthProvider();
            try {
                const res = await firebase.auth().signInWithPopup(provider);
                const token = await res.user.getIdToken();
                const v = await fetch('/api/verify-token', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({idToken:token}) });
                const data = await v.json();
                if(data.success) {
                    document.getElementById('login-btn').classList.add('hidden');
                    document.getElementById('user-profile').classList.remove('hidden');
                    document.getElementById('user-name').innerText = data.name;
                }
            } catch(e) { console.error(e); }
        }
        function logout() {
            firebase.auth().signOut();
            document.getElementById('login-btn').classList.remove('hidden');
            document.getElementById('user-profile').classList.add('hidden');
        }
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
'''

REQUIREMENTS_CONTENT = """Flask==3.0.2
firebase-admin==6.5.0
Pillow==10.2.0
requests==2.31.0
gunicorn==21.2.0
"""

PROCFILE_CONTENT = "web: gunicorn app:app\n"

def generate_files():
    print("Generating files...")
    with open("app.py", "w", encoding="utf-8") as f:
        f.write(APP_PY_CONTENT.strip())
        print("✅ Created: app.py")
        
    with open("requirements.txt", "w", encoding="utf-8") as f:
        f.write(REQUIREMENTS_CONTENT.strip())
        print("✅ Created: requirements.txt")
        
    with open("Procfile", "w", encoding="utf-8") as f:
        f.write(PROCFILE_CONTENT.strip())
        print("✅ Created: Procfile")

    print("\nAll files generated successfully!")

if __name__ == "__main__":
    generate_files()
        
