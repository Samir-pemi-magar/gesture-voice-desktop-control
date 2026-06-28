import win32gui
import win32process
import win32api
import win32con
import psutil
import subprocess
import pygetwindow as gw
import keyboard

def get_focused_window():
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return None,None,None
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    try:
        proc = psutil.Process(pid)
        exe = proc.name()
        title = win32gui.GetWindowText(hwnd)
        return hwnd, exe, title
    except:
        return None,None,None

def close_focused_app():
    hwnd,exe, title = get_focused_window()
    if not exe:
        return
    PROTECTED = ['explorer.exe', 'python.exe', 'pythonw.exe']
    if exe.lower() in PROTECTED:
        print(f"protected process, Skipping: {exe}")
        return
    print(f"closing focused app: {exe} - {title}")
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    try:
        psutil.Process(pid).kill()
    except Exception as e:
        print(f"Failed to close: {e}")

def show_all_windows():
    keyboard.press_and_release('windows+tab')

def get_all_open_windows():
    windows = []
    def callbacks(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return
        _,pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            exe = psutil.Process(pid).name()
            SKIP = ['python.exe', 'pythonw.exe', 'TextInputHost.exe']
            if exe not in SKIP:
                windows.append((hwnd,title, exe))
        except:
            pass
    win32gui.EnumWindows(callbacks, None)
    return windows

def focus_window(hwnd):
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        print(f"Focused window: {win32gui.GetWindowText(hwnd)}")
    except Exception as e:
        print(f"failed to focus: {e}")