import asyncio
import atexit
import ctypes
from ctypes import wintypes
import re
import subprocess
import sys
import time
import winsound

# Auto-instalador automático en el primer arranque (solo necesitas este único archivo)
try:
    import mss
    import mss.windows.gdi as mss_gdi
    from winrt.windows.globalization import Language
    from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage.streams import DataWriter
except ImportError:
    print("[⚙] Instalando librerías necesarias por única vez...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "mss", "winocr"])
    import mss
    import mss.windows.gdi as mss_gdi
    from winrt.windows.globalization import Language
    from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage.streams import DataWriter

# Evita bloqueo "BitBlt: Acceso denegado" cuando la ventana de Xbox está abierta
mss_gdi.CAPTUREBLT = 0

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

# Precisión DPI para que las coordenadas coincidan en cualquier pantalla (100%, 125%, 150%)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# ==============================================================================
# 1. CLIC Y TECLEO DIRECTO POR HARDWARE WIN32 (Sin usar portapapeles, < 1 ms)
# ==============================================================================
user32 = ctypes.windll.user32

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000
KEYEVENTF_KEYUP = 0x0002

VK_BACK = 0x08
VK_RETURN = 0x0D
VK_CONTROL = 0x11
VK_A = 0x41

ULONG_PTR = wintypes.WPARAM


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", _INPUT_UNION),
    ]


def _key_event(vk: int, up: bool = False) -> INPUT:
    scan = user32.MapVirtualKeyW(vk, 0)
    inp = INPUT(type=INPUT_KEYBOARD)
    inp.union.ki = KEYBDINPUT(vk, scan, KEYEVENTF_KEYUP if up else 0, 0, 0)
    return inp


def _enviar_inputs(*eventos: INPUT) -> int:
    arr = (INPUT * len(eventos))(*eventos)
    return user32.SendInput(len(eventos), ctypes.byref(arr), ctypes.sizeof(INPUT))


def clic_nativo(x: int, y: int) -> int:
    screen_w = max(user32.GetSystemMetrics(0), 1920)
    screen_h = max(user32.GetSystemMetrics(1), 1200)
    abs_x = int(int(x) * 65535 / (screen_w - 1))
    abs_y = int(int(y) * 65535 / (screen_h - 1))

    user32.SetCursorPos(int(x), int(y))

    move = INPUT(type=INPUT_MOUSE)
    move.union.mi = MOUSEINPUT(abs_x, abs_y, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, 0, 0)
    down = INPUT(type=INPUT_MOUSE)
    down.union.mi = MOUSEINPUT(abs_x, abs_y, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_LEFTDOWN, 0, 0)
    up = INPUT(type=INPUT_MOUSE)
    up.union.mi = MOUSEINPUT(abs_x, abs_y, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_LEFTUP, 0, 0)

    return _enviar_inputs(move, down, up)


def escribir_codigo_directo(coord, codigo_25: str) -> int:
    if not coord:
        return 0

    clic_nativo(coord[0], coord[1])
    time.sleep(0.020)
    clic_nativo(coord[0], coord[1])
    time.sleep(0.020)

    # Limpiar texto anterior (Ctrl+A + Backspace)
    _enviar_inputs(
        _key_event(VK_CONTROL, False),
        _key_event(VK_A, False),
        _key_event(VK_A, True),
        _key_event(VK_CONTROL, True),
        _key_event(VK_BACK, False),
        _key_event(VK_BACK, True),
    )
    time.sleep(0.008)

    # Escribir los 25 caracteres directamente por hardware
    enviados = 0
    for ch in codigo_25.upper():
        if ch.isalnum():
            vk = ord(ch)
            enviados += _enviar_inputs(_key_event(vk, False), _key_event(vk, True))
            time.sleep(0.002)

    time.sleep(0.015)
    enviados += _enviar_inputs(_key_event(VK_RETURN, False), _key_event(VK_RETURN, True))
    return enviados


def presionar_enter_nativo():
    return _enviar_inputs(_key_event(VK_RETURN, False), _key_event(VK_RETURN, True))


# ==============================================================================
# 2. MOTOR OCR NATIVO DE WINDOWS CON COORDENADAS EN TIEMPO REAL
# ==============================================================================
class FastWindowsOCR:
    def __init__(self, lang_tag: str = "es"):
        lang = Language(lang_tag)
        if OcrEngine.is_language_supported(lang):
            self.engine = OcrEngine.try_create_from_language(lang)
        else:
            self.engine = OcrEngine.try_create_from_user_profile_languages()
        self.loop = asyncio.new_event_loop()
        atexit.register(self.close)

    def close(self):
        if getattr(self, "loop", None) and not self.loop.is_closed():
            self.loop.close()
        self.engine = None

    async def _recognize_async(self, bgra_bytes: bytes, width: int, height: int):
        writer = DataWriter()
        writer.write_bytes(bgra_bytes)
        sb = SoftwareBitmap.create_copy_from_buffer(
            writer.detach_buffer(), BitmapPixelFormat.BGRA8, width, height
        )
        return await self.engine.recognize_async(sb)

    def recognize_with_boxes(self, bgra_bytes: bytes, width: int, height: int, offset_x: int = 0, offset_y: int = 0):
        res = self.loop.run_until_complete(self._recognize_async(bgra_bytes, width, height))
        if not res:
            return []
        lineas = []
        for line in res.lines:
            words = line.words
            if not words:
                continue
            x0 = min(w.bounding_rect.x for w in words)
            y0 = min(w.bounding_rect.y for w in words)
            x1 = max(w.bounding_rect.x + w.bounding_rect.width for w in words)
            y1 = max(w.bounding_rect.y + w.bounding_rect.height for w in words)
            lineas.append({
                "text": line.text.strip(),
                "cx": int(offset_x + (x0 + x1) / 2),
                "cy": int(offset_y + (y0 + y1) / 2),
                "x": int(offset_x + x0),
                "y": int(offset_y + y0),
                "w": int(x1 - x0),
                "h": int(y1 - y0),
            })
        return lineas


# ==============================================================================
# 3. INTELIGENCIA DE CÓDIGOS XBOX + DETECCIÓN DINÁMICA DE CASILLA Y BOTONES
# ==============================================================================
XBOX_VALID_CHARS = set("BCDFGHJKMPQRTVWXYZ2346789")
TABLA_CORRECCION_XBOX = str.maketrans({
    "0": "Q", "O": "D", "1": "7", "I": "J", "L": "T",
    "5": "6", "S": "9", "A": "4", "E": "F", "U": "V", "N": "M",
})

PATRON_XBOX_5X5 = re.compile(
    r"(?<![A-Z0-9])([A-Z0-9]{5})[\s\-–—._•:;|/\\]+([A-Z0-9]{5})[\s\-–—._•:;|/\\]+([A-Z0-9]{5})[\s\-–—._•:;|/\\]+([A-Z0-9]{5})[\s\-–—._•:;|/\\]+([A-Z0-9]{5})(?![A-Z0-9])",
    re.IGNORECASE,
)

RE_PLACEHOLDER_INPUT = re.compile(r"(escrib[ea]\s+el\s+c\S*digo\s+de\s+25|enter\s+.*25-character)", re.IGNORECASE)
RE_COMO_ESTE_BAJO_INPUT = re.compile(r"^(como\s+este|like\s+this)\s*:", re.IGNORECASE)
RE_ETIQUETA_ARRIBA_INPUT = re.compile(r"^se\s+agregar\S*\s+a\s+\S+@", re.IGNORECASE)
RE_BOTON_SIGUIENTE = re.compile(r"^(siguiente|sibuien\S*|siguien\S*|next)$", re.IGNORECASE)
RE_BOTON_CANCELAR = re.compile(r"^(cancelar|cancel)$", re.IGNORECASE)
RE_BOTON_CONFIRMAR = re.compile(r"^(confirmar|confirm|canjear\s+ahora|redeem\s+now)$", re.IGNORECASE)


def _validar_codigo_25(raw25: str, tiene_guiones: bool):
    raw25 = raw25.upper()
    if len(raw25) != 25 or not raw25.isalnum() or raw25 == "X" * 25:
        return None

    digit_count = sum(1 for c in raw25 if c.isdigit())
    valid_xbox_count = sum(1 for c in raw25 if c in XBOX_VALID_CHARS)

    if tiene_guiones and digit_count >= 3:
        return raw25, "-".join(raw25[i : i + 5] for i in range(0, 25, 5))

    if valid_xbox_count >= 21 and digit_count >= 2:
        corregido = raw25.translate(TABLA_CORRECCION_XBOX)
        return corregido, "-".join(corregido[i : i + 5] for i in range(0, 25, 5))

    return None


def detectar_codigos_en_lineas(lineas, casilla_xbox_coord=None):
    encontrados = []
    vistos = set()

    for item in lineas:
        txt = item["text"].upper()
        cx, cy = item["cx"], item["cy"]

        if any(m in txt for m in ("HTTP", "WWW.", ".COM", "UTM_", "=", "&", "?", "COPY-LINK")):
            continue

        if casilla_xbox_coord and abs(cx - casilla_xbox_coord[0]) < 240 and abs(cy - casilla_xbox_coord[1]) < 42:
            continue

        for m in PATRON_XBOX_5X5.finditer(txt):
            raw25 = "".join(m.groups())
            tiene_guion = any(c in txt[m.start() : m.end()] for c in "-–—._")
            res = _validar_codigo_25(raw25, tiene_guiones=tiene_guion)
            if res and res[0] not in vistos:
                vistos.add(res[0])
                encontrados.append((res[0], res[1], (cx, cy)))

        palabras = [(m.group(0), m.start(), m.end()) for m in re.finditer(r"[A-Z0-9]+", txt)]
        n = len(palabras)
        for i in range(n):
            if len(palabras[i][0]) % 5 != 0:
                continue
            acum = ""
            tiene_guion = False
            for j in range(i, min(i + 5, n)):
                if len(palabras[j][0]) % 5 != 0:
                    break
                if j > i:
                    sep = txt[palabras[j - 1][2] : palabras[j][1]]
                    if len(sep) > 4 or any(c.isalnum() for c in sep):
                        break
                    if any(c in sep for c in "-–—._"):
                        tiene_guion = True
                acum += palabras[j][0]
                if len(acum) == 25:
                    res = _validar_codigo_25(acum, tiene_guiones=tiene_guion)
                    if res and res[0] not in vistos:
                        vistos.add(res[0])
                        encontrados.append((res[0], res[1], (cx, cy)))
                    break
                elif len(acum) > 25:
                    break

    return encontrados


def localizar_ui_xbox_dinamica(lineas):
    coord_input = None
    coord_siguiente = None
    coord_confirmar = None
    linea_cancelar = None

    for item in lineas:
        if RE_PLACEHOLDER_INPUT.search(item["text"]):
            coord_input = (item["cx"], item["cy"])
            break

    if not coord_input:
        for item in lineas:
            if RE_COMO_ESTE_BAJO_INPUT.search(item["text"]):
                coord_input = (item["x"] + 150, item["y"] - 48)
                break
            if RE_ETIQUETA_ARRIBA_INPUT.search(item["text"]):
                coord_input = (item["x"] + 150, item["y"] + item["h"] + 42)

    for item in lineas:
        limpio = re.sub(r"[^A-Za-zÁÉÍÓÚáéíóúñÑ\s]", "", item["text"]).strip()
        if not limpio or item["w"] > 400 or item["h"] > 100:
            continue
        if RE_BOTON_CONFIRMAR.match(limpio):
            coord_confirmar = (item["cx"], item["cy"])
        elif RE_BOTON_SIGUIENTE.match(limpio):
            coord_siguiente = (item["cx"], item["cy"])
        elif RE_BOTON_CANCELAR.match(limpio):
            linea_cancelar = item

    if not coord_siguiente and linea_cancelar:
        coord_siguiente = (linea_cancelar["cx"] + int(linea_cancelar["w"] * 3.8), linea_cancelar["cy"])

    return coord_input, coord_siguiente, coord_confirmar


# ==============================================================================
# 4. BUCLE PRINCIPAL (UN SOLO ARCHIVO, 100% AUTOMÁTICO)
# ==============================================================================
def main():
    print("=" * 72)
    print("  🚀 SNIPER XBOX 100% DINÁMICO (ARCHIVO ÚNICO - CERO CALIBRACIÓN)")
    print("=" * 72)
    print("  1. Pon en pantalla dividida el directo/WhatsApp y xbox.com/redeem.")
    print("  2. El bot localiza solo la casilla de Xbox y escribe el código al instante.")
    print("=" * 72)

    ocr = FastWindowsOCR(lang_tag="es")
    ocr.recognize_with_boxes(bytes(64 * 64 * 4), 64, 64)

    sct = mss.MSS()
    monitor = sct.monitors[1]
    codigos_procesados = set()
    ultima_coord_xbox = None
    ultimo_btn_siguiente = None
    ultimo_raw = None

    print("[✔] Vigilando pantalla en vivo...\n")

    while True:
        try:
            s = sct.grab(monitor)
            if s.raw == ultimo_raw:
                time.sleep(0.005)
                continue
            ultimo_raw = s.raw
            t_frame = time.perf_counter()

            lineas = ocr.recognize_with_boxes(s.raw, s.width, s.height, monitor["left"], monitor["top"])
            dyn_input, dyn_sig, _ = localizar_ui_xbox_dinamica(lineas)

            if dyn_input:
                if not ultima_coord_xbox or (
                    abs(dyn_input[0] - ultima_coord_xbox[0]) > 12 or abs(dyn_input[1] - ultima_coord_xbox[1]) > 12
                ):
                    print(f"[🎯 CASILLA XBOX LOCALIZADA] Posición: {dyn_input} | Botón Siguiente: {dyn_sig}")
                ultima_coord_xbox = dyn_input
            if dyn_sig:
                ultimo_btn_siguiente = dyn_sig

            codigos = detectar_codigos_en_lineas(lineas, casilla_xbox_coord=ultima_coord_xbox)
            for c25, cfmt, pos_codigo in reversed(codigos):
                if c25 not in codigos_procesados and ultima_coord_xbox:
                    codigos_procesados.add(c25)
                    n_ev = escribir_codigo_directo(ultima_coord_xbox, c25)
                    ms = (time.perf_counter() - t_frame) * 1000.0
                    print(f"\n⚡ [CÓDIGO DETECTADO EN {pos_codigo} -> CANJEADO EN {ms:.1f} ms (eventos={n_ev})]: {cfmt}")

                    # Vigilar y pulsar SIGUIENTE y CONFIRMAR automáticamente
                    for _ in range(20):
                        time.sleep(0.14)
                        s2 = sct.grab(monitor)
                        lin2 = ocr.recognize_with_boxes(s2.raw, s2.width, s2.height, monitor["left"], monitor["top"])
                        _, sig2, conf2 = localizar_ui_xbox_dinamica(lin2)
                        if conf2:
                            clic_nativo(conf2[0], conf2[1])
                            presionar_enter_nativo()
                            print(f"   [✔ AUTO-CONFIRMAR] Botón 'CONFIRMAR' pulsado en {conf2}!")
                            break
                        target_sig = sig2 or ultimo_btn_siguiente
                        if target_sig:
                            clic_nativo(target_sig[0], target_sig[1])

                    try:
                        winsound.MessageBeep(winsound.MB_ICONASTERISK)
                    except Exception:
                        pass
                    ultimo_raw = None
                    break

            time.sleep(0.005)
        except KeyboardInterrupt:
            print("\n[⏹] Detenido.")
            break
        except Exception:
            time.sleep(0.02)


if __name__ == "__main__":
    main()
