import os
from flask import Flask, jsonify, send_from_directory, abort, request
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# 오디오 저장 경로
AUDIO_DIR = "/home/ec2-user/voiceapi/recogaudio"

# 누적된 텍스트와 파일명 리스트
recognized_text_list = []
recognized_filenames = []

@app.route("/upload_text", methods=["POST"])
def upload_text():
    data = request.get_json()
    text = data.get("text")
    filename = data.get("filename")
    if text and filename:
        # 여러 문장일 경우 \n 단위로 분리하여 저장
        lines = text.splitlines()
        for line in lines:
            line = line.strip()
            if line:
                recognized_text_list.append(line)
                recognized_filenames.append(filename)
                print(f"✅ 저장된 문장: '{line}' → {filename}")
        return jsonify({"status": "ok"}), 200
    return jsonify({"error": "Missing text or filename"}), 400

@app.route("/result_with_audio", methods=["GET"])
def get_results_with_audio():
    items = [
        {"text": t, "filename": f}
        for t, f in zip(recognized_text_list, recognized_filenames)
    ]
    return jsonify(items), 200

@app.route("/audio/<filename>", methods=["GET"])
def serve_audio(filename):
    full_path = os.path.join(AUDIO_DIR, filename)
    if not os.path.exists(full_path):
        abort(404, description="File not found")

    mime = "audio/wav"
    if filename.lower().endswith(".mp3"):
        mime = "audio/mpeg"

    return send_from_directory(
        directory=AUDIO_DIR,
        path=filename,
        mimetype=mime,
        as_attachment=False
    )

if __name__ == "__main__":
    print("🚀 EC2 Flask 서버 실행 중... (http://0.0.0.0:8000)")
    app.run(host="0.0.0.0", port=8000, debug=True)
