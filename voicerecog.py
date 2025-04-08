import pyaudio
import queue
import threading
import keyboard
from google.cloud import speech
import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv() #env 파일 불러오기

# ✅ MySQL 접속 정보 설정
db_config = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "port": 3306
}

# 🎯 음성 인식 텍스트 MySQL에 저장
def save_to_mysql(text, username):
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        query = "INSERT INTO stt_info (content, username) VALUES (%s, %s)"
        cursor.execute(query, (text, username))
        conn.commit()

        print("💾 저장됨:", text)
    except mysql.connector.Error as err:
        print("❌ MySQL 에러:", err)
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


# 🎤 구글 STT
client = speech.SpeechClient()

# 오디오 설정
RATE = 16000
CHUNK = int(RATE / 10)
audio_queue = queue.Queue()

# 인식 상태 저장
is_listening = False
stream = None
p = None

def callback(in_data, frame_count, time_info, status):
    audio_queue.put(in_data)
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

    print("🎤 음성 인식 시작")

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
                    print("🎤 인식 텍스트 :", recognized_text)
                    save_to_mysql(recognized_text, "test") #MySQL 저장, test는 임시사용자명
                if not is_listening:
                    return
    except Exception as e:
        print("❌ 오류 발생:", e)

def toggle_recognition(event=None):
    global is_listening, stream, p

    if not is_listening:
        is_listening = True
        threading.Thread(target=recognize_stream, daemon=True).start()
    else:
        is_listening = False
        audio_queue.put(None)
        if stream is not None:
            stream.stop_stream()
            stream.close()
        if p is not None:
            p.terminate()
        print("🛑 음성 인식 종료")

def quit_program(event=None):
    global is_listening, stream, p

    print("👋 프로그램 종료.")
    if is_listening:
        is_listening = False
        audio_queue.put(None)
        if stream is not None:
            stream.stop_stream()
            stream.close()
        if p is not None:
            p.terminate()
    exit(0)

# 실행
if __name__ == "__main__":
    print("✅ 'S' 키 → 음성 인식 시작/종료 | 'Q' 키 → 프로그램 종료")

    keyboard.on_press_key("s", toggle_recognition)
    keyboard.on_press_key("q", quit_program)

    try:
        keyboard.wait()
    except KeyboardInterrupt:
        quit_program()