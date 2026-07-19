import sys
from pathlib import Path
from PyQt6.QtCore import QSettings

def _get_app_command():
    """Возвращает список аргументов для запуска приложения в фоне."""
    if getattr(sys, 'frozen', False):
        # Собрано в exe
        return [sys.executable, '--minimized']
    else:
        # Режим разработки
        script_path = Path(__file__).resolve().parent.parent / 'main.py'
        return [sys.executable, str(script_path), '--minimized']

def enable_autostart():
    """Добавляет приложение в автозагрузку ОС."""
    if sys.platform == 'win32':
        _enable_windows()
    elif sys.platform.startswith('linux'):
        _enable_linux()
    # можно добавить elif для macOS

def disable_autostart():
    """Удаляет приложение из автозагрузки ОС."""
    if sys.platform == 'win32':
        _disable_windows()
    elif sys.platform.startswith('linux'):
        _disable_linux()

# ========== Windows ==========
import winreg

def _enable_windows():
    key = winreg.HKEY_CURRENT_USER
    subkey = r'Software\Microsoft\Windows\CurrentVersion\Run'
    try:
        with winreg.OpenKey(key, subkey, 0, winreg.KEY_SET_VALUE) as regkey:
            cmd = ' '.join(f'"{arg}"' for arg in _get_app_command())
            winreg.SetValueEx(regkey, 'CloudManager', 0, winreg.REG_SZ, cmd)
    except Exception as e:
        print(f"Ошибка добавления в автозагрузку: {e}")

def _disable_windows():
    key = winreg.HKEY_CURRENT_USER
    subkey = r'Software\Microsoft\Windows\CurrentVersion\Run'
    try:
        with winreg.OpenKey(key, subkey, 0, winreg.KEY_SET_VALUE) as regkey:
            winreg.DeleteValue(regkey, 'CloudManager')
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"Ошибка удаления из автозагрузки: {e}")

# ========== Linux ==========
def _enable_linux():
    desktop_file = _get_linux_autostart_path()
    desktop_file.parent.mkdir(parents=True, exist_ok=True)
    cmd = ' '.join(_get_app_command())
    content = f"""[Desktop Entry]
Type=Application
Name=Cloud Manager
Exec={cmd}
Terminal=false
X-GNOME-Autostart-enabled=true
"""
    desktop_file.write_text(content)

def _disable_linux():
    desktop_file = _get_linux_autostart_path()
    if desktop_file.exists():
        desktop_file.unlink()

def _get_linux_autostart_path():
    return Path.home() / '.config' / 'autostart' / 'cloud-manager.desktop'