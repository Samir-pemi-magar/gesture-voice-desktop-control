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

    _,pid = win32process.GetWindowThreadProcessId(hwnd)
    try:
        proc = psutil.Process(pid)
        