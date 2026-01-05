import os
import google.genai as genai
from google.genai import types

def check():
    key_path = 'go-ai-commentator/api_key.txt'
    with open(key_path, 'r') as f:
        api_key = f.read().strip()
    
    client = genai.Client(api_key=api_key)
    
    # White wedges at P15, splitting Black's Q16 and Q14
    history = [['B', 'Q16'], ['W', 'D4'], ['B', 'Q14'], ['W', 'Q4'], ['B', 'O17'], ['W', 'P15']]
    
    prompt = f"I am at move 6. History: {history}. Please analyze the situation around P15."
    
    response = client.models.generate_content(
        model='gemini-3-flash-preview',
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction='あなたはプロの囲碁棋士です。盤面を分析し日本語で解説してください。特に白がP15に打ったことで生じた「サカレ形（裂かれ形）」という状態に言及し、黒がなぜ苦しいのかを詳しく説明してください。'
        )
    )
    print(response.text)

if __name__ == "__main__":
    check()
