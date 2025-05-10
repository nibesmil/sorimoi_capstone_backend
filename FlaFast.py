# FlaFast.py

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.wsgi import WSGIMiddleware
import voicerecog   # 음성 인식 모듈에서 REMOTE_DIR 설정을 가져옵니다
import withdart as flask_app  # 기존 Flask 앱

# FastAPI 인스턴스 생성
app = FastAPI()

# CORS 설정: 모든 오리진에서 GET, POST, OPTIONS 요청 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# 오디오 파일 디렉터리 설정 (환경변수 AUDIO_DIR 우선, 없으면 voicerecog.REMOTE_DIR 사용)
audio_dir = os.getenv("AUDIO_DIR", voicerecog.REMOTE_DIR)
# 디렉터리가 실제로 있어야 StaticFiles가 동작합니다
if not os.path.isdir(audio_dir):
    raise RuntimeError(f"Audio directory not found: {audio_dir}")
print(f"Serving audio files from: {audio_dir}")

# /audio 경로는 StaticFiles로 처리
app.mount(
    "/audio",
    StaticFiles(directory=audio_dir, html=False),
    name="audio"
)

# 나머지 요청은 Flask 라우트에 위임
app.mount("/", WSGIMiddleware(flask_app.app))

# FastAPI 전용 헬스체크 엔드포인트
@app.get("/fastapi/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    # reload 모드 사용 시 문자열 import 방식을 권장합니다
    uvicorn.run("FlaFast:app", host="0.0.0.0", port=5001, reload=True)
