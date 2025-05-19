# scorelogic.py
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class GPTScoringService:
    def __init__(self, model: str = "gpt-3.5-turbo"):
        self.model = model
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def generate_prompt(self, text: str, filename: str) -> str:
        return f"""
다음은 사용자의 음성 인식 결과입니다.

🎙️ 인식된 문장:
{text}

📁 음성 파일명:
{filename}

아래 기준에 따라 100점 만점으로 점수를 부여해줘:
- 정확도 (텍스트 내용이 완성도 있게 말해졌는지)
- 발음이 자연스럽고 끊김이 없었는지
- 음성에 잡음이나 방해 요소는 없었는지 (파일명만 제공됨)

점수만 숫자로 줘. 예: 82
"""

    def evaluate(self, text: str, filename: str) -> int:
        prompt = self.generate_prompt(text, filename)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.choices[0].message.content
            score = int(''.join(filter(str.isdigit, content)))
            print(f"🎯 GPT 점수: {score}")
            return score
        except Exception as e:
            print(f"❌ GPT 평가 실패: {e}")
            return 0
