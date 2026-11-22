# Path resolution for both development and PyInstaller/cx_Freeze bundled modes
import sys
import os
from pathlib import Path


def get_base_path() -> Path:
    '''Get the base path for the application.

    In development mode, returns the project root.
    In PyInstaller bundled mode, returns sys._MEIPASS (bundle directory).
    In cx_Freeze bundled mode, returns sys.executable directory.
    '''
    if getattr(sys, 'frozen', False):
        # Running in a bundled mode (PyInstaller or cx_Freeze)
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller
            return Path(sys._MEIPASS)
        else:
            # cx_Freeze - executable directory
            return Path(sys.executable).parent
    else:
        # Running in development mode
        return Path(__file__).parent.parent


def get_app_data_dir() -> Path:
    '''Get the writable application data directory.

    On Windows: %LOCALAPPDATA%\\JARVIS
    On Linux: ~/.local/share/JARVIS
    On macOS: ~/Library/Application Support/JARVIS
    '''
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share'))

    app_data = base / 'JARVIS'
    app_data.mkdir(parents=True, exist_ok=True)
    return app_data


def get_database_path() -> str:
    '''Get the database URL with proper writable path.'''
    app_data = get_app_data_dir()
    db_path = app_data / 'jarvis.db'
    return f'sqlite:///{db_path}'


def get_llama_server_path() -> Path:
    '''Get the llama-server.exe path.'''
    base = get_base_path()
    # Check common locations
    candidates = [
        base / 'llama-server.exe',
        base / 'bin' / 'llama-server.exe',
        Path('C:/JARVIS 1.2/jarvis/llama-server.exe'),
        Path('C:/JARVIS 1.2/llama-server.exe'),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    # Fallback to bundled or system path
    return Path('llama-server.exe')


def get_model_path() -> Path:
    '''Get the GGUF model path.'''
    base = get_base_path()
    candidates = [
        base / 'Qwen3-1.7B-Q4_K_M.gguf',
        Path('C:/JARVIS 1.2/Qwen3-1.7B-Q4_K_M.gguf'),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path('Qwen3-1.7B-Q4_K_M.gguf')


def get_vosk_model_path() -> Path:
    '''Get the Vosk model directory.'''
    base = get_base_path()
    candidates = [
        base / 'vosk-model-small-en-us-0.15',
        Path('C:/JARVIS 1.2/vosk-model-small-en-us-0.15'),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path('vosk-model-small-en-us-0.15')


def get_data_dir() -> Path:
    '''Get the writable data directory.'''
    return get_app_data_dir()


def get_log_dir() -> Path:
    '''Get the writable log directory.'''
    log_dir = get_app_data_dir() / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_voice_cache_dir() -> Path:
    '''Get the writable voice cache directory.'''
    cache_dir = get_app_data_dir() / 'voice_cache'
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_webengine_cache_dir() -> Path:
    '''Get the writable webengine cache directory.'''
    cache_dir = get_app_data_dir() / 'webengine_cache'
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


# For backwards compatibility
BASE_DIR = get_base_path()
DATA_DIR = get_data_dir()
LOG_DIR = get_log_dir()
VOICE_CACHE_DIR = get_voice_cache_dir()
WEBENGINE_CACHE_DIR = get_webengine_cache_dir()
