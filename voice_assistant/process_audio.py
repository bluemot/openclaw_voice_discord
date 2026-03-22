#!/usr/bin/env python3
"""
處理音訊檔案：STT -> 顯示文字 -> TTS -> 輸出音訊
"""

import subprocess
import os
import sys
import tempfile

# 路徑設定
INPUT_AUDIO = "/home/ubuntu/.openclaw/media/inbound/output.wav"
WORK_DIR = "/home/ubuntu/.openclaw/workspace/voice_assistant"

def run_stt():
    """使用 Whisper 進行語音轉文字"""
    print("=" * 50)
    print("🎙️ STEP 1: 語音轉文字 (STT)")
    print("=" * 50)
    
    # 由於 Ollama Whisper 模型可能有問題，我們先用一個示範文字
    # 實際上這裡應該使用 openai-whisper 或其他 STT 工具
    
    # 嘗試使用系統的 whisper (如果已安裝)
    try:
        result = subprocess.run(
            ["whisper", INPUT_AUDIO, "--model", "tiny", "--language", "zh", "--output_format", "txt"],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            # 讀取輸出的文字檔
            txt_file = INPUT_AUDIO.replace(".wav", ".txt")
            if os.path.exists(txt_file):
                with open(txt_file, 'r') as f:
                    text = f.read().strip()
                return text
    except:
        pass
    
    # 如果上面失敗，嘗試使用 ollama
    try:
        # 讀取音訊檔案並傳給 ollama (這可能需要特殊處理)
        cmd = f'cat {INPUT_AUDIO} | ollama run dimavz/whisper-tiny 2>/dev/null'
        result = subprocess.run(cmd, shell=True, capture_output=True, timeout=30)
        if result.returncode == 0 and result.stdout:
            return result.stdout.decode().strip()
    except:
        pass
    
    # 備用：返回一個模擬結果用於測試流程
    return "[這是一個測試，模擬語音轉文字的結果。實際部署時需要正確安裝和配置 Whisper 模型]"

def run_llm(text):
    """使用 LLM 處理文字"""
    print("\n" + "=" * 50)
    print("🤖 STEP 2: LLM 處理")
    print("=" * 50)
    
    try:
        prompt = f"請回應這句話：{text}"
        result = subprocess.run(
            ["ollama", "run", "llama3.2", prompt],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        print(f"LLM 錯誤: {e}")
    
    return f"收到你的訊息：{text}"

def run_tts(text, output_path):
    """使用 Orpheus 進行文字轉語音"""
    print("\n" + "=" * 50)
    print("🔊 STEP 3: 文字轉語音 (TTS)")
    print("=" * 50)
    
    try:
        # 使用 ollama 執行 Orpheus
        # 注意：輸出格式可能需要調整
        result = subprocess.run(
            ["ollama", "run", "sematre/orpheus", text],
            capture_output=True,
            timeout=60
        )
        
        if result.returncode == 0:
            # 儲存音訊輸出
            with open(output_path, 'wb') as f:
                f.write(result.stdout)
            return True
        else:
            print(f"TTS 錯誤: {result.stderr.decode()}")
    except Exception as e:
        print(f"TTS 錯誤: {e}")
    
    return False

def main():
    """主流程"""
    print("\n" + "=" * 50)
    print("🎯 語音助手完整流程")
    print("=" * 50)
    
    # Step 1: STT
    transcribed_text = run_stt()
    print(f"\n📝 辨識結果：\n{transcribed_text}\n")
    
    # Step 2: LLM
    response = run_llm(transcribed_text)
    print(f"\n💬 AI 回應：\n{response}\n")
    
    # Step 3: TTS
    output_audio = os.path.join(WORK_DIR, "response.wav")
    success = run_tts(response, output_audio)
    
    if success and os.path.exists(output_audio):
        print(f"\n✅ TTS 完成！音訊已儲存至：{output_audio}")
        print(f"檔案大小：{os.path.getsize(output_audio)} bytes")
    else:
        print("\n❌ TTS 失敗")
    
    print("\n" + "=" * 50)
    print("流程完成！")
    print("=" * 50)

if __name__ == "__main__":
    main()
