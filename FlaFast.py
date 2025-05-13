#FlaFast.py

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.wsgi import WSGIMiddleware
from dotenv import load_dotenv
import withdart as flask_app  # 기존 Flask 앱

load_dotenv()

# FastAPI 인스턴스 생성
app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ 오디오 디렉토리 경로 지정
audio_dir = os.getenv("AUDIO_DIR")

# ✅ 없으면 더미 경로로 우회
if not audio_dir or not os.path.isdir(audio_dir):
    print(f"⚠️ 실제 오디오 파일은 로컬에서 제공되지 않습니다. 더미 디렉토리로 우회합니다.")
    audio_dir = "./dummy_audio_dir"
    os.makedirs(audio_dir, exist_ok=True)

print(f"📁 audio_dir 경로: {audio_dir}")

# ✅ /audio 경로는 StaticFiles로 처리
app.mount(
    "/audio",
    StaticFiles(directory=audio_dir, html=False),
    name="audio"
)

# ✅ 나머지 요청은 Flask 라우트에 위임
app.mount("/", WSGIMiddleware(flask_app.app))

# ✅ FastAPI 헬스체크
@app.get("/fastapi/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("FlaFast:app", host="0.0.0.0", port=5000, reload=True)
