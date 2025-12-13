from __future__ import annotations

import importlib.util
import os
import subprocess
import sys


def is_llama_cpp_installed() -> bool:
    """Check if llama-cpp-python is already installed."""
    try:
        spec = importlib.util.find_spec("llama_cpp")
        return spec is not None
    except Exception:
        return False


def install_llama_cpp() -> int:

    print("[install_llama_cpp] Checking llama-cpp-python installation...")

    # 如果想強制重裝，請手動執行 `pip uninstall llama-cpp-python -y`
    if is_llama_cpp_installed():
        print("[install_llama_cpp] llama-cpp-python is already installed. Skipping.")
        return 0

    print("[install_llama_cpp] Installing llama-cpp-python (Pre-built CUDA 12.x Wheel)...")
    print("[install_llama_cpp] Note: You don't need VS Build Tools for this method.")

    env = os.environ.copy()
    
    
    env["LLAMA_CUDA"] = "1"
    wheel_url = "https://abetlen.github.io/llama-cpp-python/whl/128"

    cmd = [
        sys.executable, "-m", "pip", "install", "llama-cpp-python",
        "--extra-index-url", wheel_url,
        "--no-cache-dir"
    ]


    print(f"[install_llama_cpp] Running command: {' '.join(cmd)}")
    
    try:
        
        result = subprocess.run(cmd, check=False)
        
        if result.returncode == 0:
            print("="*60)
            print("[install_llama_cpp] SUCCESS! Installed CUDA-enabled llama-cpp-python.")
            print("="*60)
        else:
            print(f"[install_llama_cpp] Installation failed with return code {result.returncode}.")
            print("[install_llama_cpp] Hint: Check your internet connection or CUDA version compatibility.")
        
        return result.returncode

    except Exception as e:
        print(f"[install_llama_cpp] Exception during installation: {e}")
        return 1


if __name__ == "__main__":
    rc = install_llama_cpp()
    sys.exit(rc)