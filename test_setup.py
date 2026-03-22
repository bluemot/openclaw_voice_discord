#!/usr/bin/env python3
"""
Setup Test - 檢查環境是否就緒
"""

import subprocess
import sys

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

def check_command(cmd, name):
    """檢查指令是否存在"""
    try:
        result = subprocess.run([cmd, "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"{GREEN}✓{RESET} {name} is installed")
            return True
    except:
        pass
    print(f"{RED}✗{RESET} {name} is NOT installed")
    return False

def check_python_module(module, name):
    """檢查 Python 模組"""
    try:
        __import__(module)
        print(f"{GREEN}✓{RESET} Python module: {name}")
        return True
    except ImportError:
        print(f"{RED}✗{RESET} Python module missing: {name}")
        return False

def check_ollama_models():
    """檢查 Ollama 模型"""
    print(f"\n{YELLOW}Checking Ollama models...{RESET}")
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        if result.returncode == 0:
            print("Installed models:")
            print(result.stdout)
            
            models = result.stdout
            required = ["whisper", "orpheus"]
            for r in required:
                if r in models.lower():
                    print(f"{GREEN}✓{RESET} Found: {r}")
                else:
                    print(f"{YELLOW}⚠{RESET} Missing: {r}")
    except:
        print(f"{RED}✗ Cannot check Ollama models{RESET}")

def main():
    print(f"{YELLOW}Voice Assistant Setup Check{RESET}")
    print("=" * 40)
    
    # Check Python version
    print(f"\nPython version: {sys.version}")
    
    # Check commands
    print(f"\n{YELLOW}System dependencies:{RESET}")
    check_command("python3", "Python 3")
    check_command("pip3", "pip3")
    check_command("ollama", "Ollama")
    
    # Check Python modules
    print(f"\n{YELLOW}Python modules:{RESET}")
    check_python_module("pyaudio", "pyaudio")
    check_python_module("soundfile", "soundfile")
    check_python_module("numpy", "numpy")
    check_python_module("requests", "requests")
    
    # Check Ollama
    check_ollama_models()
    
    print(f"\n{YELLOW}Next steps:{RESET}")
    print("1. Install missing dependencies")
    print("2. Run: python3 voice_assistant.py --install")
    print("3. Run: python3 voice_assistant.py")

if __name__ == "__main__":
    main()
