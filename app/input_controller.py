import ctypes
from dataclasses import dataclass
from typing import Dict, List


user32 = ctypes.WinDLL("user32", use_last_error=True)

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_MOVE = 0x0001


@dataclass(frozen=True)
class KeyDefinition:
    label: str
    vk_code: int


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_short),
        ("wParamH", ctypes.c_ushort),
    ]


class INPUTUNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("union", INPUTUNION),
    ]


KEY_LAYOUT: List[List[str]] = [
    ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"],
    ["F13", "F14", "F15", "F16", "Insert", "Delete", "Home", "End", "PgUp", "PgDn"],
    ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "=", "Backspace"],
    ["Tab", "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "[", "]", "\\"],
    ["CapsLock", "A", "S", "D", "F", "G", "H", "J", "K", "L", ";", "'", "Enter"],
    ["Shift", "Z", "X", "C", "V", "B", "N", "M", ",", ".", "/", "Up"],
    ["Ctrl", "Alt", "Space", "Left", "Down", "Right"],
]


KEY_DEFINITIONS: Dict[str, KeyDefinition] = {}


def _register(label: str, vk_code: int) -> None:
    KEY_DEFINITIONS[label] = KeyDefinition(label=label, vk_code=vk_code)


for digit in "0123456789":
    _register(digit, ord(digit))

for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    _register(letter, ord(letter))

for offset in range(1, 17):
    _register(f"F{offset}", 0x6F + offset)

SPECIAL_KEYS = {
    "Backspace": 0x08,
    "Tab": 0x09,
    "Enter": 0x0D,
    "Shift": 0x10,
    "Ctrl": 0x11,
    "Alt": 0x12,
    "CapsLock": 0x14,
    "Space": 0x20,
    "PgUp": 0x21,
    "PgDn": 0x22,
    "End": 0x23,
    "Home": 0x24,
    "Left": 0x25,
    "Up": 0x26,
    "Right": 0x27,
    "Down": 0x28,
    "Insert": 0x2D,
    "Delete": 0x2E,
    ";": 0xBA,
    "=": 0xBB,
    ",": 0xBC,
    "-": 0xBD,
    ".": 0xBE,
    "/": 0xBF,
    "`": 0xC0,
    "[": 0xDB,
    "\\": 0xDC,
    "]": 0xDD,
    "'": 0xDE,
}

for label, vk_code in SPECIAL_KEYS.items():
    _register(label, vk_code)


def available_key_labels() -> List[str]:
    return [label for row in KEY_LAYOUT for label in row if label in KEY_DEFINITIONS]


def get_key_definition(label: str) -> KeyDefinition:
    return KEY_DEFINITIONS[label]


def send_keypress(label: str) -> None:
    key = get_key_definition(label)
    extra = ctypes.c_ulong(0)
    press = INPUT(
        type=INPUT_KEYBOARD,
        union=INPUTUNION(
            ki=KEYBDINPUT(
                wVk=key.vk_code,
                wScan=0,
                dwFlags=0,
                time=0,
                dwExtraInfo=ctypes.pointer(extra),
            )
        ),
    )
    release = INPUT(
        type=INPUT_KEYBOARD,
        union=INPUTUNION(
            ki=KEYBDINPUT(
                wVk=key.vk_code,
                wScan=0,
                dwFlags=KEYEVENTF_KEYUP,
                time=0,
                dwExtraInfo=ctypes.pointer(extra),
            )
        ),
    )
    _send_inputs([press, release])


def nudge_mouse(distance: int = 1) -> None:
    extra = ctypes.c_ulong(0)
    move_out = INPUT(
        type=INPUT_MOUSE,
        union=INPUTUNION(
            mi=MOUSEINPUT(
                dx=distance,
                dy=0,
                mouseData=0,
                dwFlags=MOUSEEVENTF_MOVE,
                time=0,
                dwExtraInfo=ctypes.pointer(extra),
            )
        ),
    )
    move_back = INPUT(
        type=INPUT_MOUSE,
        union=INPUTUNION(
            mi=MOUSEINPUT(
                dx=-distance,
                dy=0,
                mouseData=0,
                dwFlags=MOUSEEVENTF_MOVE,
                time=0,
                dwExtraInfo=ctypes.pointer(extra),
            )
        ),
    )
    _send_inputs([move_out, move_back])


def _send_inputs(inputs: List[INPUT]) -> None:
    array_type = INPUT * len(inputs)
    sent = user32.SendInput(len(inputs), array_type(*inputs), ctypes.sizeof(INPUT))
    if sent != len(inputs):
        raise ctypes.WinError(ctypes.get_last_error())
