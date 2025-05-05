from flask import Flask, jsonify
from flask_cors import CORS
import voicerecog

app = Flask(__name__)
CORS(app)

@app.route('/start', methods=['POST'])
def start_recognition():
    if voicerecog.is_listening:
        return jsonify({"status": "already_listening"})
    voicerecog.start_recognition()
    return jsonify({"status": "started"})

@app.route('/stop', methods=['POST'])
def stop_recognition():
    if not voicerecog.is_listening:
        return jsonify({"status": "not_listening"})
    voicerecog.stop_recognition()
    return jsonify({"status": "stopped"})

@app.route('/result', methods=['GET'])
def get_result():
    return jsonify({"texts": voicerecog.recognized_text_list})

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify({"is_listening": voicerecog.is_listening})

@app.route('/feedback', methods=['GET'])
def get_feedback():
    message = getattr(voicerecog, 'last_feedback_message', "")
    return jsonify({"message": message})

@app.route('/clear', methods=['POST'])
def clear_result():
    voicerecog.clear_results()
    return jsonify({"status": "cleared"})

if __name__ == '__main__':
    print("🚀 Flask 음성 인식 서버 실행 중... (http://0.0.0.0:5000)")
    app.run(host='0.0.0.0', port=5000)
