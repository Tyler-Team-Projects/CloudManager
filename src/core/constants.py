from pathlib import Path

class App:
    ORGANIZATION = "TeamTyler"
    NAME = "DiscoHack"

class Paths:
    HOME = Path.home()
    TOKEN_FILE = HOME / '.core-disko' / 'yandex.token'
    CACHE_DB = HOME / '.cloudmanager_cache.db'
    YANDEX_ROOT = HOME / 'YandexDisk'
    DOWNLOADS = YANDEX_ROOT / 'Downloads'
    DOWNLOAD_METADATA = YANDEX_ROOT / '.download_metadata.json'

class Settings:
    NOTIFICATIONS = "show_notifications"
    AUTOSTART = "autostart"
    CLOSE_BEHAVIOR = "close_behavior"
    VIEW_MODE = "default_view_mode"
    HIDDEN_FILES = "show_hidden_files"
    TOAST_DURATION = "toast_duration"
    DOWNLOAD_FOLDER = "download_folder"
    SYNC_ENABLED = "sync_enabled"
    SYNC_INTERVAL = "sync_interval"


class Timeouts:
    HTTP = 30
    SYNC_DEFAULT = 30
    TOAST_DEFAULT = 10
    TOAST_DURATION = 10
    DEBOUNCE = 2.0
    CACHE_TTL = 30
    PRELOAD = 300
    DISK_INFO_INTERVAL = 30000
    SYNC_RETRY_DELAY = 10
    NETWORK_CHECK = 2


class Providers:
    LOCAL = "local"
    CLOUD = "cloud"
    MOUNTS_ROOT = "mounts://"

class Views:
    ICONS = "icons"
    TABLE = "table"

class CloseBehavior:
    TRAY = "tray"
    EXIT = "exit"
    ASK = "ask"

class Urls:
    YANDEX_API_BASE = 'https://cloud-api.yandex.net'

class Auth:
    TOKEN_KEY = "yandex_token"
