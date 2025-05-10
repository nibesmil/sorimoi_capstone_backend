import os
from flask import Flask, jsonify, send_from_directory, abort
from flask_cors import CORS
import voicerecog  # 음성 인식 모듈

app = Flask(__name__)
CORS(app)  # 모든 엔드포인트에 CORS 허용

@app.route('/start', methods=['POST'])
def start_recognition():
    if voicerecog.is_listening:
        return jsonify({"status": "already_listening"}), 200
    voicerecog.start_recognition()
    return jsonify({"status": "started"}), 200

@app.route('/stop', methods=['POST'])
def stop_recognition():
    if not voicerecog.is_listening:
        return jsonify({"status": "not_listening"}), 200
    voicerecog.stop_recognition()
    return jsonify({"status": "stopped"}), 200

@app.route('/result', methods=['GET'])
def get_result():
    return jsonify({"texts": voicerecog.recognized_text_list}), 200

@app.route('/result_with_audio', methods=['GET'])
def get_results_with_audio():
    items = [
        {"text": t, "filename": f}
        for t, f in zip(voicerecog.recognized_text_list, voicerecog.recognized_filenames)
    ]
    return jsonify(items), 200

@app.route('/audio/<filename>', methods=['GET'])
def serve_audio(filename):
    # 실제 파일 경로 계산
    full_path = os.path.join(voicerecog.REMOTE_DIR, filename)
    app.logger.debug(f"[serve_audio] 요청된 파일 경로: {full_path}")

    # 파일이 없으면 404 에러
    if not os.path.exists(full_path):
        app.logger.error(f"[serve_audio] 파일을 찾을 수 없습니다: {full_path}")
        abort(404, description="File not found")

    # .mp3 지원 (선택) 및 MIME 타입 설정
    if filename.lower().endswith('.mp3'):
        mime = 'audio/mpeg'
    else:
        mime = 'audio/wav'

    return send_from_directory(
        directory=voicerecog.REMOTE_DIR,
        path=filename,
        mimetype=mime,
        as_attachment=False
    )

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify({"is_listening": voicerecog.is_listening}), 200

@app.route('/feedback', methods=['GET'])
def get_feedback():
    return jsonify({"feedback": voicerecog.last_feedback_message}), 200

@app.route('/clear', methods=['POST'])
def clear_result():
    voicerecog.clear_results()
    return jsonify({"status": "cleared"}), 200

if __name__ == '__main__':
    # 디버그 모드로 실행: 디버그 로그를 터미널에 출력합니다.
    app.logger.setLevel("DEBUG")
    print("🚀 Flask 음성 인식 서버 실행 중... (http://0.0.0.0:5001)")
    app.run(host='0.0.0.0', port=5001, debug=True)
