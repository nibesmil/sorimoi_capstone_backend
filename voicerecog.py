import pyaudio
import queue
import threading
import datetime
import os
import wave
from google.cloud import speech
import mysql.connector
from dotenv import load_dotenv
import paramiko

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
AWS_HOST = os.getenv("AWS_HOST")
AWS_USER = os.getenv("AWS_USER")
AWS_PASSWORD = os.getenv("AWS_PASSWORD")
REMOTE_DIR = "/home/ec2-user/recogaudio/"

# 음성 인식 설정
client = speech.SpeechClient()
RATE = 16000
CHUNK = int(RATE / 10)

# 상태 변수
audio_queue = queue.Queue()
recorded_frames = []  # 🔥 녹음 데이터 저장용
is_listening = False
stream = None
p = None
last_recognized_text = ""

def save_to_mysql(text, username):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        query = "INSERT INTO stt_info (content, username) VALUES (%s, %s)"
        cursor.execute(query, (text, username))
        conn.commit()
        print("💾 저장됨:", text)
    except mysql.connector.Error as err:
        print("❌ MySQL 저장 오류:", err)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def save_wav(filename, frames):
    """녹음된 데이터로 정상적인 WAV 파일 저장"""
    temp_dir = "/tmp"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    local_path = os.path.join(temp_dir, filename)

    with wave.open(local_path, 'wb') as wf:
        wf.setnchannels(1)  # Mono
        wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))  # 샘플 사이즈: 2바이트
        wf.setframerate(RATE)  # 샘플링 레이트
        wf.writeframes(b''.join(frames))  # 데이터 기록

    return local_path

def upload_to_aws(local_path, filename):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=AWS_HOST, username=AWS_USER, password=AWS_PASSWORD)

        sftp = ssh.open_sftp()
        remote_path = os.path.join(REMOTE_DIR, filename)
        sftp.put(local_path, remote_path)
        print(f"🚀 업로드 성공: {remote_path}")

        sftp.close()
        ssh.close()
        os.remove(local_path)
    except Exception as e:
        print("❌ AWS 업로드 실패:", e)

def callback(in_data, frame_count, time_info, status):
    audio_queue.put(in_data)
    recorded_frames.append(in_data)  # 🔥 녹음 데이터 따로 모음
    return None, pyaudio.paContinue

def recognize_stream():
    global is_listening, stream, p, last_recognized_text, recorded_frames

    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK,
        stream_callback=callback
    )

    print("🎤 인식 중...")

    def generator():
        while is_listening:
            chunk = audio_queue.get()
            if chunk is None:
                break
            yield speech.StreamingRecognizeRequest(audio_content=chunk)

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code="en-US"  # 언어 설정
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
                    print("🎤 인식 결과:", recognized_text)
                    last_recognized_text = recognized_text
                    save_to_mysql(recognized_text, "test")

                    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"voice_{now}.wav"

                    # 🔥 녹음 데이터 WAV로 저장
                    local_path = save_wav(filename, recorded_frames)

                    # 🔥 저장한 파일 AWS로 업로드
                    upload_to_aws(local_path, filename)

                    # 🔥 frames 초기화
                    recorded_frames = []

                if not is_listening:
                    return
    except Exception as e:
        print("❌ 오류:", e)

# 🔹 외부 제어용 API 함수
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

def get_last_result():
    return last_recognized_text
