import sys
import os
import subprocess
import logging
import platform
import shutil
import importlib.util

# --- 設定日誌 ---
logging.basicConfig(
    level=logging.INFO,
    format="[Installer] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("LlamaInstaller")

def get_nvcc_status():
    """
    核心邏輯：執行 nvcc --version 來檢查是否具備 CUDA 編譯/執行環境
    回傳: True (有 NVCC) / False (無 NVCC)
    """
    try:
        # 嘗試執行 nvcc --version
        result = subprocess.run(
            ["nvcc", "--version"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True, 
            shell=False # 在 Windows 上有時設為 True 比較好找，但 False 比較安全
        )
        if result.returncode == 0:
            logger.info("✅ NVCC detected! CUDA Toolkit is available.")
            # 可以在這裡解析版本號，但目前我們預設鎖定 12.x
            return True
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning(f"Error checking nvcc: {e}")

    # 如果直接呼叫失敗，嘗試在 Windows shell 中呼叫
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                "nvcc --version", 
                shell=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
            if result.returncode == 0:
                logger.info("✅ NVCC detected via Shell!")
                return True
        except:
            pass

    logger.warning("⚠️ NVCC not found. Assuming CPU-only or Metal environment.")
    return False

def is_uv_active():
    """檢查是否正在使用 uv 且處於虛擬環境中"""
    has_uv = shutil.which("uv") is not None
    # 簡單檢查是否在 venv 中
    in_venv = sys.prefix != sys.base_prefix
    return has_uv and in_venv

def run_pip_install(packages, index_url=None, extra_args=None):
    """
    統一安裝函式：支援 uv pip 與標準 pip 切換
    """
    if isinstance(packages, str): packages = [packages]
    if extra_args is None: extra_args = []

    cmd = []
    use_uv = is_uv_active()

    if use_uv:
        logger.info(f"⚡ Using uv pip to install: {packages[0]}...")
        cmd = ["uv", "pip", "install"]
    else:
        logger.info(f"Using standard pip to install: {packages[0]}...")
        cmd = [sys.executable, "-m", "pip", "install"]
        if "--prefer-binary" not in extra_args:
            cmd.append("--prefer-binary")

    cmd.extend(packages)

    if index_url:
        # 針對 PyTorch，uv 和 pip 對 index-url 的處理略有不同，但基本相容
        cmd.append(f"--index-url={index_url}")
    
    # 過濾 uv 不支援的參數
    for arg in extra_args:
        if use_uv and arg == "--prefer-binary": continue
        cmd.append(arg)
        
    try:
        # 複製當前環境變數 (確保能抓到 CUDA 路徑)
        env = os.environ.copy()
        subprocess.run(cmd, check=True, env=env)
        return True
    except subprocess.CalledProcessError:
        logger.error(f"Failed to install {packages}")
        return False

def install_process():
    logger.info("="*50)
    logger.info("   Smart Installer (NVCC Check First)")
    logger.info("="*50)

    # 1. 先做硬體偵測 (NVCC check)
    has_cuda_toolkit = False
    system_os = platform.system().lower()
    
    if system_os == "darwin":
        # Mac 不用檢查 nvcc，直接看是不是 Apple Silicon
        if platform.machine() == "arm64":
            logger.info("Detected macOS (Apple Silicon). Mode: Metal")
            target_mode = "metal"
        else:
            target_mode = "cpu"
    else:
        # Windows / Linux -> 檢查 NVCC
        has_cuda_toolkit = get_nvcc_status()
        target_mode = "cuda" if has_cuda_toolkit else "cpu"

    # 2. 決定 PyTorch 安裝策略
    # 如果已安裝就不重裝，除非你想強制檢查更新 (這裡先設為已安裝則跳過)
    if not importlib.util.find_spec("torch"):
        logger.info(f"Installing PyTorch for mode: {target_mode.upper()}...")
        
        torch_pkgs = ["torch", "torchvision", "torchaudio"]
        torch_index = None
        
        if target_mode == "cuda":
            # 強制鎖定 CUDA 12.4
            torch_index = "https://download.pytorch.org/whl/cu124"
        elif target_mode == "cpu" and system_os == "windows":
            # Windows 預設 pip install torch 就是 CPU 版，但為了保險不設 index
            pass 
        
        if torch_index:
            run_pip_install(torch_pkgs, index_url=torch_index)
        else:
            run_pip_install(torch_pkgs)
    else:
        logger.info("PyTorch is already installed. Skipping.")

    # 3. 決定 Llama-cpp-python 安裝策略
    
    # --- 新增檢查邏輯：如果已安裝則跳過 ---
    # 注意：import 名稱是 llama_cpp，但安裝包名稱是 llama-cpp-python
    if importlib.util.find_spec("llama_cpp"):
        logger.info("="*50)
        logger.info("✅ llama-cpp-python is already installed. Skipping installation.")
        logger.info(f"   Current Mode Check: {target_mode.upper()}") 
        logger.info("="*50)
        # 如果你希望強制檢查更新，可以把這裡的 return 拿掉，或者加個參數控制
        return 
    # -----------------------------------

    logger.info(f"Installing llama-cpp-python for mode: {target_mode.upper()}...")
    
    llama_pkg = "llama-cpp-python"
    llama_index = ""
    
    if target_mode == "cuda":
        # 官方 Wheel 庫
        llama_index = "https://abetlen.github.io/llama-cpp-python/whl/cu124"
    elif target_mode == "metal":
        llama_index = "https://abetlen.github.io/llama-cpp-python/whl/metal"
    else: # cpu
        llama_index = "https://abetlen.github.io/llama-cpp-python/whl/cpu"
    
    # 執行安裝
    # 加上 --no-cache-dir 避免快取到錯誤版本
    # 加上 --upgrade 確保更新到支援 Qwen3 的版本
    success = run_pip_install(
        [llama_pkg], 
        extra_args=[f"--extra-index-url={llama_index}", "--upgrade", "--no-cache-dir"]
    )

    if success:
        logger.info("="*50)
        logger.info(f"✅ Installation Complete! Mode: {target_mode.upper()}")
        logger.info("="*50)
    else:
        logger.error("❌ Installation Failed.")
        sys.exit(1)

if __name__ == "__main__":
    try:
        install_process()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        logger.critical(f"Unexpected error: {e}")
        sys.exit(1)