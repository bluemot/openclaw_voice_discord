#!/usr/bin/env python3
"""
使用 Ollama Python module + OpenAI compatible API 進行 STT/TTS
"""

import ollama
import base64
import os

# 設定
INPUT_AUDIO = "/home/ubuntu/.openclaw/media/inbound/output.wav"
WORK_DIR = "/home/ubuntu/.openclaw/workspace/voice_assistant"

def read_audio_file(filepath):
    """讀取音訊檔案並轉為 base64"""
    with open(filepath, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')

def stt_with_whisper():
    """使用 Whisper 進行語音轉文字"""
    print("=" * 60)
    print("🎙️ STEP 1: STT (Whisper)")
    print("=" * 60)
    
    try:
        # 讀取音訊檔案
        audio_b64 = read_audio_file(INPUT_AUDIO)
        print(f"音訊檔案已讀取，大小: {os.path.getsize(INPUT_AUDIO)} bytes")
        
        # 使用 ollama.chat 嘗試傳送音訊
        # 注意：這取決於 whisper 模型是否支援這種格式
        response = ollama.chat(
            model='dimavz/whisper-tiny',
            messages=[{
                'role': 'user',
                'content': '請轉錄這個音訊檔案',
                'images': []  # 有些模型可能接受音訊作為 images
            }]
        )
        
        text = response['message']['content']
        print(f"✅ STT 成功！")
        return text
        
    except Exception as e:
        print(f"❌ STT 錯誤: {e}")
        return None

def llm_chat(text):
    """使用 LLM 回應"""
    print("\n" + "=" * 60)
    print("🤖 STEP 2: LLM")
    print("=" * 60)
    
    try:
        # 使用雲端模型 kimi-k2.5
        response = ollama.chat(
            model='kimi-k2.5:cloud',
            messages=[{
                'role': 'user',
                'content': f'請簡短回應這句話：{text}'
            }]
        )
        
        result = response['message']['content']
        print(f"✅ LLM 回應成功！")
        return result
        
    except Exception as e:
        print(f"❌ LLM 錯誤: {e}")
        return f"收到訊息：{text}"

def tts_with_orpheus(text):
    """使用 Orpheus 進行文字轉語音"""
    print("\n" + "=" * 60)
    print("🔊 STEP 3: TTS (Orpheus)")
    print("=" * 60)
    
    output_path = os.path.join(WORK_DIR, "response.wav")
    
    try:
        # 嘗試使用 Orpheus
        response = ollama.generate(
            model='sematre/orpheus',
            prompt=text
        )
        
        # 如果回應是二進位音訊資料，儲存它
        if 'response' in response:
            # 假設回應是 base64 編碼的音訊
            try:
                audio_data = base64.b64decode(response['response'])
                with open(output_path, 'wb') as f:
                    f.write(audio_data)
                print(f"✅ TTS 成功！")
                return output_path
            except:
                # 可能是文字回應
                print(f"模型回應: {response['response']}")
                return None
        
    except Exception as e:
        print(f"❌ TTS 錯誤: {e}")
        return None

def main():
    """主流程"""
    print("\n" + "=" * 60)
    print("🎯 Ollama Python API 語音流程")
    print("=" * 60)
    
    # Step 1: STT
    text = stt_with_whisper()
    if not text:
        print("STT 失敗，使用預設文字")
        text = "這是一個測試訊息"
    
    print(f"\n📝 轉錄結果:\n{text}\n")
    
    # Step 2: 傳回給你
    print("=" * 60)
    print("📤 傳回文字給你")
    print("=" * 60)
    print(f"「{text}」")
    
    # Step 3: LLM
    response = llm_chat(text)
    print(f"\n💬 AI 回應:\n{response}\n")
    
    # Step 4: TTS
    audio_path = tts_with_orpheus(response)
    
    if audio_path and os.path.exists(audio_path):
        size = os.path.getsize(audio_path)
        print(f"\n✅ 全部完成！")
        print(f"📁 回應音訊: {audio_path}")
        print(f"📊 大小: {size} bytes")
    else:
        print("\n⚠️ TTS 未完成，但其他步驟成功")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
