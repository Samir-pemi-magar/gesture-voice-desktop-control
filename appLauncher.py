import os
import glob
import subprocess
import win32com.client
import win32gui
import win32con
import win32ui
from PIL import Image

EXCLUDE_KEYWORDS = [
    'uninstall', 'documentation', 'manual', 'release notes',
    'help', 'readme', 'website', 'telemetry', 'module docs',
    'report a problem', 'what is new', 'language preferences',
    'recording manager', 'database compare', 'spreadsheet compare',
    'configuration', 'gluon', 'policy tool',
    'odbc', 'iscsi', 'dfrgui', 'recovery', 'disk cleanup',
    'event viewer', 'resource monitor', 'performance monitor',
    'memory diagnostics', 'computer management', 'task scheduler',
    'registry editor', 'component services', 'system configuration',
    'system information', 'services', 'firewall', 'steps recorder',
    'character map', 'remote desktop', 'skinned', 'reset preferences',
    'cmd', 'command prompt', 'ise', '(x86)', 'photos',
    'install additional', 'node prompt', 'plastic scm',
    'idle', 'manuals', '(64-bit)', '32-bit', '64-bit',
    'git cmd', 'git gui', 'git bash'
]

def get_installed_apps():
    paths = [
        "C:/ProgramData/Microsoft/Windows/Start Menu/Programs/**/*.lnk",
        "C:/ProgramData/Microsoft/Windows/Start Menu/Programs/*.lnk",
        f"C:/Users/{os.getlogin()}/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/**/*.lnk",
        f"C:/Users/{os.getlogin()}/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/*.lnk"
    ]
    apps = []
    for path in paths:
        found = glob.glob(path, recursive=True)
        apps.extend(found)
    apps = list(set(apps))
    clean_apps = []
    for app in apps:
        name = os.path.basename(app).replace('.lnk', '').lower()
        if not any(keyword in name for keyword in EXCLUDE_KEYWORDS):
            clean_apps.append(app)
    clean_apps.sort(key=lambda x: os.path.basename(x).lower())
    return clean_apps

def get_app_icon(lnk_path, size=64):
    try:
        name = os.path.basename(lnk_path).replace('.lnk', '')
        # get exe path from shortcut
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(lnk_path)
        exe_path = shortcut.Targetpath

        if not exe_path or not os.path.exists(exe_path):
            return None, None

        # extract icon from exe
        large, small = win32gui.ExtractIconEx(exe_path, 0)
        if not large:
            return None, None

        # convert icon to image
        hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
        hbmp = win32ui.CreateBitmap()
        hbmp.CreateCompatibleBitmap(hdc, size, size)
        hdc = hdc.CreateCompatibleDC()
        hdc.SelectObject(hbmp)
        
        hdc.DrawIcon((0, 0), large[0])

        # convert to PIL image
        bmpinfo = hbmp.GetInfo()
        bmpstr = hbmp.GetBitmapBits(True)
        icon = Image.frombuffer('RGBA',(bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, 'raw', 'BGRA', 0, 1)
        icon = icon.resize((size, size))
        win32gui.DestroyIcon(large[0])
        return icon, name

    except Exception as e:
        print(f"Error getting icon: {e}")
        return None, None

def launch_app(lnk_path):
    subprocess.Popen(['cmd', '/c', 'start', '', lnk_path], shell= True)