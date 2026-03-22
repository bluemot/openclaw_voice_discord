#!/usr/bin/env python3
"""
STT + TTS 測試腳本 for RTX 5060
使用 Ollama 運行 Whisper (STT) 和 Orpheus (TTS)
"""

import subprocess
import json
import os
import sys

# 顏色輸出
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

def run_command(cmd, description):
    """執行 shell 指令並顯示結果"""
    print(f"\n{YELLOW}>>> {description}{RESET}")
    print(f"執行: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"{GREEN}✓ 成功{RESET}")
        return result.stdout
    else:
        print(f"{RED}✗ 失敗: {result.stderr}{RESET}")
        return None

def check_gpu():
    """檢查 GPU 狀態"""
    print(f"\n{'='*50}")
    print("🎮 GPU 狀態檢查")
    print(f"{'='*50}")
    
    # 檢查 nvidia-smi
    result = run_command("nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free --format=csv,noheader", "檢查 GPU 資訊")
    if result:
        print(f"GPU 資訊: {result.strip()}")
    else:
        print(f"{YELLOW}⚠ 無法檢測 GPU，繼續執行...{RESET}")

def install_models():
    """安裝所需的 Ollama 模型"""
    print(f"\n{'='*50}")
    print("📦 安裝模型")
    print(f"{'='*50}")
    
    models = [
        ("dimavz/whisper-tiny", "Whisper Tiny (STT)"),
        ("sematre/orpheus", "Orpheus (TTS)")
    ]
    
    for model, desc in models:
        print(f"\n安裝 {desc}...")
        run_command(f"ollama pull {model}", f"下載 {model}")

def test_stt():
    """測試語音轉文字 (STT)"""
    print(f"\n{'='*50}")
    print("🎙️ 測試 STT (語音轉文字)")
    print(f"{'='*50}")
    
    # 創建一個測試音訊檔案 (假設使用者已經有一個)
    test_audio = "test_audio.wav"
    
    if not os.path.exists(test_audio):
        print(f"{YELLOW}⚠ 找不到測試音訊檔案: {test_audio}{RESET}")
        print("請準備一個 WAV 格式的音訊檔案，命名為 test_audio.wav")
        print("或者修改腳本中的 test_audio 變數指向你的音訊檔案")
        return False
    
    print(f"使用音訊檔案: {test_audio}")
    
    # 使用 Ollama 執行 Whisper
    cmd = f'ollama run dimavz/whisper-tiny -- "{test_audio}"'
    result = run_command(cmd, "執行語音辨識")
    
    if result:
        print(f"{GREEN}辨識結果: {result}{RESET}")
        return True
    return False

def test_tts():
    """測試文字轉語音 (TTS)"""
    print(f"\n{'='*50}")
    print("🔊 測試 TTS (文字轉語音)")
    print(f"{'='*50}")
    
    test_text = "你好，這是一個測試。Hello, this is a test."
    output_file = "output_speech.wav"
    
    print(f"輸入文字: {test_text}")
    print(f"輸出檔案: {output_file}")
    
    # 注意: Orpheus 可能需要特定的輸入格式
    # 這裡使用簡單的文字輸入方式
    cmd = f'echo "{test_text}" | ollama run sematre/orpheus > {output_file}'
    result = run_command(cmd, "生成語音")
    
    if result is not None:
        if os.path.exists(output_file):
            size = os.path.getsize(output_file)
            print(f"{GREEN}✓ 語音檔案已生成: {output_file} ({size} bytes){RESET}")
            return True
    
    return False

def list_models():
    """列出已安裝的模型"""
    print(f"\n{'='*50}")
    print("📋 已安裝的 Ollama 模型")
    print(f"{'='*50}")
    run_command("ollama list", "列出所有模型")

def show_usage():
    """顯示使用說明"""
    print(f"""
{GREEN}使用方法:{RESET}

1. 安裝模型:
   python3 test_stt_tts.py install

2. 列出已安裝模型:
   python3 test_stt_tts.py list

3. 測試 STT (需要 test_audio.wav):
   python3 test_stt_tts.py stt

4. 測試 TTS:
   python3 test_stt_tts.py tts

5. 完整測試 (全部跑一遍):
   python3 test_stt_tts.py all

{YELLOW}注意:{RESET}
- 測試 STT 前請準備一個名為 test_audio.wav 的音訊檔案
- Orpheus TTS 的輸出格式可能需要額外處理
""")

def main():
    """主程式"""
    if len(sys.argv) < 2:
        show_usage()
        return
    
    command = sys.argv[1].lower()
    
    if command == "install":
        check_gpu()
        install_models()
        list_models()
    
    elif command == "list":
        list_models()
    
    elif command == "stt":
        check_gpu()
        test_stt()
    
    elif command == "tts":
        check_gpu()
        test_tts()
    
    elif command == "all":
        check_gpu()
        list_models()
        test_stt()
        test_tts()
        print(f"\n{'='*50}")
        print(f"{GREEN}🎉 測試完成！{RESET}")
        print(f"{'='*50}")
    
    else:
        show_usage()

if __name__ == "__main__":
    main()
