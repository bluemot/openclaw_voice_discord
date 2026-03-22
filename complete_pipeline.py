#!/usr/bin/env python3
"""
完整語音流程：
1. STT (Whisper Python) -> 2. 文字傳回這裡 -> 3. LLM -> 4. TTS -> 5. 音訊傳回
"""

import subprocess
import os
import sys

# 設定
INPUT_AUDIO = "/home/ubuntu/.openclaw/media/inbound/output.wav"
WORK_DIR = "/home/ubuntu/.openclaw/workspace/voice_assistant"

def check_whisper():
    """檢查 whisper 是否已安裝"""
    try:
        result = subprocess.run(["whisper", "--version"], capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

def install_whisper():
    """安裝 openai-whisper"""
    print("📦 安裝 openai-whisper...")
    subprocess.run(["pip", "install", "-q", "openai-whisper", "ffmpeg-python"], check=False)

def run_stt():
    """語音轉文字"""
    print("=" * 60)
    print("🎙️ STEP 1: 語音轉文字 (STT)")
    print("=" * 60)
    
    if not check_whisper():
        print("正在安裝 whisper...")
        install_whisper()
    
    try:
        # 使用 whisper 轉錄
        result = subprocess.run(
            ["whisper", INPUT_AUDIO, "--model", "tiny", "--language", "zh", 
             "--output_format", "txt", "--output_dir", WORK_DIR],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        # 讀取轉錄結果
        base_name = os.path.basename(INPUT_AUDIO).replace(".wav", "")
        txt_file = os.path.join(WORK_DIR, base_name + ".txt")
        
        if os.path.exists(txt_file):
            with open(txt_file, 'r') as f:
                text = f.read().strip()
            print(f"✅ 轉錄成功！")
            return text
        else:
            # 從 stderr 找結果
            print(f"輸出：{result.stdout}")
            print(f"錯誤：{result.stderr}")
            return "[轉錄失敗，請檢查音訊檔案]"
            
    except Exception as e:
        print(f"❌ STT 錯誤：{e}")
        return "[STT 錯誤]"

def run_llm(text):
    """使用 LLM 處理"""
    print("\n" + "=" * 60)
    print("🤖 STEP 2: LLM 處理")
    print("=" * 60)
    print(f"輸入：{text}")
    
    # 使用可用的雲端模型
    models = ["kimi-k2.5:cloud", "qwen3-coder-next:cloud", "deepseek-v3.2:cloud"]
    
    for model in models:
        try:
            print(f"嘗試使用 {model}...")
            result = subprocess.run(
                ["ollama", "run", model, text],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                response = result.stdout.strip()
                print(f"✅ LLM 回應成功！")
                return response
        except Exception as e:
            print(f"{model} 失敗：{e}")
            continue
    
    return f"收到訊息：{text}"

def run_tts(text):
    """文字轉語音 - 使用替代方案"""
    print("\n" + "=" * 60)
    print("🔊 STEP 3: 文字轉語音 (TTS)")
    print("=" * 60)
    print(f"輸入文字：{text[:100]}...")
    
    output_path = os.path.join(WORK_DIR, "response.wav")
    
    # 方案 1：嘗試使用 gTTS (Google TTS，需要網路)
    try:
        subprocess.run(["pip", "install", "-q", "gtts"], check=False)
        from gtts import gTTS
        tts = gTTS(text=text, lang='zh-tw')
        tts.save(output_path)
        if os.path.exists(output_path):
            print(f"✅ TTS 完成！使用 gTTS")
            return output_path
    except:
        pass
    
    # 方案 2：使用 espeak (離線)
    try:
        subprocess.run(["sudo", "apt-get", "install", "-y", "espeak"], check=False)
        subprocess.run(
            ["espeak", "-v", "zh", "-w", output_path, text],
            timeout=30
        )
        if os.path.exists(output_path):
            print(f"✅ TTS 完成！使用 espeak")
            return output_path
    except:
        pass
    
    print("❌ TTS 失敗")
    return None

def main():
    """主流程"""
    print("\n" + "=" * 60)
    print("🎯 語音助手完整流程")
    print("=" * 60)
    
    # Step 1: STT
    text = run_stt()
    print(f"\n📝 STT 結果：\n{text}\n")
    
    # Step 2: 在這裡傳回文字給你
    print("\n" + "=" * 60)
    print("📤 STEP 2.5: 將文字傳回給你")
    print("=" * 60)
    print(f"「{text}」")
    
    # Step 3: LLM
    response = run_llm(text)
    print(f"\n💬 AI 回應：\n{response}\n")
    
    # Step 4: TTS
    audio_path = run_tts(response)
    
    if audio_path and os.path.exists(audio_path):
        size = os.path.getsize(audio_path)
        print(f"\n✅ 流程完成！")
        print(f"📁 回應音訊：{audio_path}")
        print(f"📊 檔案大小：{size} bytes")
        print(f"\n現在可以將這個音訊檔案傳給你了！")
    else:
        print("\n⚠️ TTS 失敗，但 STT 和 LLM 已完成")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
