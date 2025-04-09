import pyaudio
import queue
import threading
import keyboard
import datetime
import os
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

# AWS 접속 정보 설정
AWS_HOST = os.getenv("AWS_HOST")
AWS_USER = os.getenv("AWS_USER")
AWS_PASSWORD = os.getenv("AWS_PASSWORD")
REMOTE_DIR = "/home/ec2-user/recogaudio/"

# Google Speech-to-text API 
client = speech.SpeechClient()
RATE = 16000
CHUNK = int(RATE / 10)
audio_queue = queue.Queue()
is_listening = False
stream = None
p = None

# 마이쿼리 저장
def save_to_mysql(text, username):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        query = "INSERT INTO stt_info (content, username) VALUES (%s, %s)"
        cursor.execute(query, (text, username))
        conn.commit()
        print("💾 저장됨:", text)
    except mysql.connector.Error as err:
        print("❌ 마이쿼리 저장 에러 ❌ :", err)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ec2 서버에 업로드
def upload_to_aws(filename, audio_data):
    try:
        temp_dir = "/tmp" #임시 업로드 파일이라 로컬엔 저장 X
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        local_path = os.path.join(temp_dir, filename)
        with open(local_path, "wb") as f:
            f.write(audio_data)

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=AWS_HOST, username=AWS_USER, password=AWS_PASSWORD)

        sftp = ssh.open_sftp()
        remote_path = os.path.join(REMOTE_DIR, filename)
        sftp.put(local_path, remote_path)
        print(f"🚀 음성 파일 업로드 성공 ! : {remote_path}")

        sftp.close()
        ssh.close()
        os.remove(local_path)  # 로컬 파일 삭제
    except Exception as e:
        print("❌ EC2 업로드 실패 ! :", e)

# 오디오 콜백
def callback(in_data, frame_count, time_info, status):
    audio_queue.put(in_data)
    return None, pyaudio.paContinue

# 음성 인식
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

    print("🎤 음성 인식을 시작합니다.")

    def generator():
        while is_listening:
            chunk = audio_queue.get()
            if chunk is None:
                break
            yield speech.StreamingRecognizeRequest(audio_content=chunk)

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code="en-US" #영어 발음만 할 수 있음. 한국어 발음 원할 시 ko-KR
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
                    print("🎤 결과 텍스트:", recognized_text)
                    save_to_mysql(recognized_text, "test")

                    # 오디오 저장 후 EC2 업로드
                    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"voice_{now}.wav"
                    audio_data = b"".join(list(audio_queue.queue))
                    upload_to_aws(filename, audio_data)

                if not is_listening:
                    return
    except Exception as e:
        print("❌ 오류 발생:", e)

# 시작/종료 토글
def toggle_recognition(event=None):
    global is_listening, stream, p
    if not is_listening:
        is_listening = True
        threading.Thread(target=recognize_stream, daemon=True).start()
    else:
        is_listening = False
        audio_queue.put(None)
        if stream:
            stream.stop_stream()
            stream.close()
        if p:
            p.terminate()
        print("🛑 음성 인식을 종료합니다. ")

# 종료
def quit_program(event=None):
    global is_listening, stream, p
    print("👋 프로그램을 종료합니다. ")
    if is_listening:
        is_listening = False
        audio_queue.put(None)
        if stream:
            stream.stop_stream()
            stream.close()
        if p:
            p.terminate()
    exit(0)

# 실행
if __name__ == "__main__":
    print("✅ 'S' 키 → 음성 인식 시작/종료\n✅ 'Q' 키 → 프로그램 종료")

    keyboard.on_press_key("s", toggle_recognition)
    keyboard.on_press_key("q", quit_program)

    try:
        keyboard.wait()
    except KeyboardInterrupt:
        quit_program()
