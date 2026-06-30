import keyboard

def show_all_windows():
    keyboard.press_and_release('windows+tab')
    
def select_choose_window(direction):
    keyboard.press_and_release(direction)
    
def open_selected_window():
    keyboard.press_and_release('enter')

def hide_all_windows():
    keyboard.press_and_release('esc')

def close_focused_window():
    keyboard.press_and_release('alt+f4')