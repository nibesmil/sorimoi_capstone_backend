import os
import glob
from flask import Flask, jsonify, send_from_directory, abort, request
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

AUDIO_DIR = "/home/ec2-user/voiceapi/recogaudio"
recognized_text_list = []
recognized_filenames = []

@app.route("/upload_text", methods=["POST"])
def upload_text():
    data = request.get_json()
    text = data.get("text")
    filename = data.get("filename")
    if text and filename:
        if text in recognized_text_list and filename in recognized_filenames:
            print(f"⚠️ 중복 무시: '{text}' / {filename}")
            return jsonify({"status": "duplicated"}), 200

        recognized_text_list.append(text)
        recognized_filenames.append(filename)
        print(f"✅ 저장된 문장: '{text}' → {filename}")
        return jsonify({"status": "ok"}), 200
    return jsonify({"error": "Missing text or filename"}), 400

@app.route("/result_with_audio", methods=["GET"])
def get_results_with_audio():
    return jsonify([
        {"text": t, "filename": f}
        for t, f in zip(recognized_text_list, recognized_filenames)
    ])

@app.route("/audio/<filename>", methods=["GET"])
def serve_audio(filename):
    full_path = os.path.join(AUDIO_DIR, filename)
    if not os.path.exists(full_path):
        print(f"🚫 파일 없음: {full_path}")
        abort(404, description="File not found")
    mime = "audio/wav" if filename.endswith(".wav") else "audio/mpeg"
    return send_from_directory(directory=AUDIO_DIR, path=filename, mimetype=mime)

@app.route("/clear_text", methods=["POST"])
def clear_text_only():
    recognized_text_list.clear()
    recognized_filenames.clear()
    print("🧹 텍스트만 초기화 완료")
    return jsonify({"status": "text_cleared"}), 200

@app.route("/clear_results", methods=["POST"])
def clear_results():
    recognized_text_list.clear()
    recognized_filenames.clear()
    print("🧹 전체 초기화 및 파일 삭제")
    try:
        for filepath in glob.glob(os.path.join(AUDIO_DIR, "voice_*.wav")):
            os.remove(filepath)
    except Exception as e:
        print(f"❌ 삭제 실패: {e}")
    return jsonify({"status": "cleared"}), 200

if __name__ == "__main__":
    print("🚀 EC2 서버 실행 중 (http://0.0.0.0:8000)")
    app.run(host="0.0.0.0", port=8000, debug=True)
