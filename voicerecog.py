#voicerecog.py 

import pyaudio
import queue
import threading
import datetime
import os
import wave
import numpy as np
from google.cloud import speech
import mysql.connector
from dotenv import load_dotenv
import paramiko
import requests

load_dotenv()

# MySQL 설정
db_config = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "port": 3306
}

# AWS 접속 정보
AWS_HOST = os.getenv("AWS_HOST", "").strip()
AWS_USER = os.getenv("AWS_USER", "").strip()
AWS_PASSWORD = os.getenv("AWS_PASSWORD", "").strip()
REMOTE_DIR = "/home/ec2-user/voiceapi/recogaudio/"

client = speech.SpeechClient()
RATE = 16000
CHUNK = int(RATE / 10)

# 상태 변수
audio_queue = queue.Queue()
recorded_frames = []
is_listening = False
stream = None
p = None
last_feedback_message = ""
recognized_text_list = []
recognized_filenames = []

VOLUME_THRESHOLD = 0.01

def save_to_mysql(text, filename):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        query = """
            INSERT INTO stt_info (contents, date, score, star, title)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            text,
            datetime.datetime.now(),
            0,
            0,
            'TESTDATA'  # ← 여기만 수정됨
        ))
        conn.commit()
        print("✅ MYSQL 저장 완료:", text, "→ TESTDATA")
    except mysql.connector.Error as err:
        print("❌ MySQL 저장 오류:", err)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def save_wav(filename, frames):
    temp_dir = "/tmp"
    os.makedirs(temp_dir, exist_ok=True)
    local_path = os.path.join(temp_dir, filename)
    with wave.open(local_path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
    return local_path

def upload_to_aws(local_path, filename):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=AWS_HOST, username=AWS_USER, password=AWS_PASSWORD)
        sftp = ssh.open_sftp()
        remote_path = os.path.join(REMOTE_DIR, filename)
        sftp.put(local_path, remote_path)
        print(f"\U0001F680 업로드 성공: {remote_path}")
        sftp.close()
        ssh.close()
        os.remove(local_path)
    except Exception as e:
        print("❌ AWS 업로드 실패:", e)

def callback(in_data, frame_count, time_info, status):
    global last_feedback_message
    audio_data = np.frombuffer(in_data, dtype=np.int16)
    volume_norm = np.linalg.norm(audio_data) / len(audio_data)

    if volume_norm <= 0.02:
        last_feedback_message = "목소리가 너무 작아요. 😮‍💨"
    elif volume_norm >= 0.3:
        last_feedback_message = "목소리가 너무 커요. 😲"
    else:
        last_feedback_message = "Good! 잘 하고 있어요. 😄👌"

    if volume_norm > VOLUME_THRESHOLD:
        audio_queue.put(in_data)
        recorded_frames.append(in_data)
    return None, pyaudio.paContinue

def recognize_stream():
    global is_listening, stream, p
    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK,
        stream_callback=callback
    )
    print("\U0001F3A4 인식 중...")

    def generator():
        while is_listening:
            chunk = audio_queue.get()
            if chunk is None:
                break
            yield speech.StreamingRecognizeRequest(audio_content=chunk)

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code="en-US"
    )
    streaming_config = speech.StreamingRecognitionConfig(
        config=config,
        interim_results=False
    )
    responses = client.streaming_recognize(streaming_config, generator())

    try:
        for response in responses:
            for result in response.results:
                if result.is_final:
                    recognized_text = result.alternatives[0].transcript.strip()
                    if not recognized_text or len(recorded_frames) < 3:
                        recorded_frames.clear()
                        continue

                    lines = recognized_text.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line:
                            now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                            filename = f"voice_{now}.wav"
                            local_path = save_wav(filename, recorded_frames)
                            upload_to_aws(local_path, filename)

                            save_to_mysql(line, filename)
                            recognized_text_list.append(line)
                            recognized_filenames.append(filename)

                    recorded_frames.clear()

                if not is_listening:
                    return
    except Exception as e:
        print("❌ 오류:", e)

def start_recognition():
    global is_listening
    if not is_listening:
        is_listening = True
        threading.Thread(target=recognize_stream, daemon=True).start()
        print("🟢 인식 시작됨")

def stop_recognition():
    global is_listening, stream, p
    if is_listening:
        is_listening = False
        audio_queue.put(None)
        if stream:
            stream.stop_stream()
            stream.close()
        if p:
            p.terminate()
        print("🔴 인식 종료됨")
        # ✅ clear_results()는 더 이상 여기서 호출하지 않음

def clear_results():
    global recognized_text_list, recognized_filenames
    print("🧹 clear_results() 호출됨")

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=AWS_HOST, username=AWS_USER, password=AWS_PASSWORD)
        sftp = ssh.open_sftp()

        for filename in recognized_filenames:
            remote_path = os.path.join(REMOTE_DIR, filename)
            try:
                sftp.remove(remote_path)
                print(f"🗑️ EC2 삭제 성공: {remote_path}")
            except FileNotFoundError:
                print(f"🚫 파일 없음: {remote_path}")
            except Exception as e:
                print(f"❌ EC2 삭제 실패: {remote_path}, 에러: {e}")

        sftp.close()
        ssh.close()

    except Exception as e:
        print(f"❌ EC2 연결 실패: {e}")

    recognized_text_list.clear()
    recognized_filenames.clear()

def get_last_result():
    return '\n'.join(recognized_text_list)

def get_results_with_audio():
    return [
        {"text": t, "filename": f}
        for t, f in zip(recognized_text_list, recognized_filenames)
    ]
