#!/usr/bin/env python3
"""
完整語音助手流程：
1. STT (faster-whisper) -> 2. LLM (Ollama) -> 3. TTS (gTTS)

Requirements:
    pip install faster-whisper ollama gtts
"""

import os
import sys
from faster_whisper import WhisperModel
import ollama
from gtts import gTTS

# 設定
INPUT_AUDIO = "/home/ubuntu/.openclaw/media/inbound/output.wav"
WORK_DIR = "/home/ubuntu/.openclaw/workspace/voice_assistant"

def step1_stt(audio_file):
    """Step 1: 語音轉文字 (STT)"""
    print("=" * 60)
    print("🎙️ STEP 1: 語音轉文字 (faster-whisper)")
    print("=" * 60)
    
    # 檢查檔案是否存在
    if not os.path.exists(audio_file):
        print(f"❌ 錯誤：找不到音訊檔案 {audio_file}")
        return None
    
    print(f"📁 處理檔案: {audio_file}")
    print(f"📊 檔案大小: {os.path.getsize(audio_file)} bytes")
    
    # 載入 Whisper 模型
    # 可用模型: tiny, base, small, medium, large-v3
    # device="cuda" 使用 GPU, device="cpu" 使用 CPU
    # compute_type="float16" 或 "int8" (int8 在 CPU 上更快)
    model_size = "tiny"  # 用 tiny 比較快
    
    print(f"\n🔄 載入 Whisper 模型: {model_size}...")
    try:
        # 檢查是否有 GPU，如果沒有就用 CPU
        import torch
        has_gpu = torch.cuda.is_available()
        device = "cuda" if has_gpu else "cpu"
        compute_type = "float16" if has_gpu else "int8"
        
        print(f"   使用裝置: {device}, 計算類型: {compute_type}")
        
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
        print(f"✅ 模型載入完成！")
        
    except Exception as e:
        print(f"⚠️ 無法使用 GPU，改用 CPU: {e}")
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
    
    # 進行轉錄
    print(f"\n📝 開始轉錄...")
    try:
        segments, info = model.transcribe(audio_file, beam_size=5, language="zh")
        
        print(f"   偵測語言: {info.language}, 機率: {info.language_probability:.2f}")
        
        # 收集轉錄文字
        transcript = ""
        for segment in segments:
            print(f"   [{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")
            transcript += segment.text + " "
        
        transcript = transcript.strip()
        print(f"\n✅ STT 完成！")
        return transcript
        
    except Exception as e:
        print(f"❌ 轉錄失敗: {e}")
        return None

def step2_send_to_chat(text):
    """Step 2: 傳回 Discord"""
    print("\n" + "=" * 60)
    print("📤 STEP 2: 將文字傳回給你")
    print("=" * 60)
    print(f"\n📝 辨識結果：\n{text}\n")
    return text

def step3_llm(text):
    """Step 3: LLM 處理 (Ollama)"""
    print("=" * 60)
    print("🤖 STEP 3: LLM 處理 (Ollama)")
    print("=" * 60)
    
    # 可用的 Cloud 模型
    models = ["kimi-k2.5:cloud", "qwen3-coder-next:cloud", "deepseek-v3.2:cloud"]
    
    prompt = f"請簡短回應這句話：{text}"
    
    for model_name in models:
        try:
            print(f"\n🔄 嘗試使用 {model_name}...")
            response = ollama.chat(
                model=model_name,
                messages=[{
                    'role': 'user',
                    'content': prompt
                }]
            )
            
            result = response['message']['content'].strip()
            print(f"✅ LLM 回應成功！")
            return result
            
        except Exception as e:
            print(f"   {model_name} 失敗: {e}")
            continue
    
    print("❌ 所有模型都失敗，使用預設回應")
    return f"收到訊息：{text}"

def step4_tts(text):
    """Step 4: 文字轉語音 (TTS)"""
    print("\n" + "=" * 60)
    print("🔊 STEP 4: 文字轉語音 (gTTS)")
    print("=" * 60)
    
    output_file = os.path.join(WORK_DIR, "response.mp3")
    
    try:
        print(f"🔄 生成語音...")
        print(f"   文字: {text[:100]}...")
        
        # 使用 gTTS (Google TTS)
        tts = gTTS(text=text, lang='zh-tw', slow=False)
        tts.save(output_file)
        
        if os.path.exists(output_file):
            size = os.path.getsize(output_file)
            print(f"✅ TTS 完成！")
            print(f"   檔案: {output_file}")
            print(f"   大小: {size} bytes")
            return output_file
        else:
            print("❌ 檔案未生成")
            return None
            
    except Exception as e:
        print(f"❌ TTS 失敗: {e}")
        return None

def main():
    """主流程"""
    print("\n" + "=" * 60)
    print("🎯 語音助手完整流程")
    print("=" * 60)
    
    # Step 1: STT
    transcript = step1_stt(INPUT_AUDIO)
    if not transcript:
        print("❌ STT 失敗，結束流程")
        return
    
    # Step 2: 傳回 Discord
    step2_send_to_chat(transcript)
    
    # Step 3: LLM
    response = step3_llm(transcript)
    print(f"\n💬 AI 回應：\n{response}\n")
    
    # Step 4: TTS
    audio_file = step4_tts(response)
    
    # 完成
    print("\n" + "=" * 60)
    print("✅ 流程完成！")
    print("=" * 60)
    
    if audio_file:
        print(f"\n📁 回應音訊：{audio_file}")
        print(f"現在可以傳送這個音訊檔案給你！")
    
    print("\n摘要：")
    print(f"  📝 STT 輸入：{transcript[:50]}...")
    print(f"  💬 LLM 回應：{response[:50]}...")
    print(f"  🔊 TTS 輸出：{audio_file if audio_file else '失敗'}")

if __name__ == "__main__":
    main()
