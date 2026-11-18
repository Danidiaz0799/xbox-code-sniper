# 🚀 Xbox Code Sniper (100% Dinámico con OCR Nativo de Windows)

Script todo-en-uno ([sniper_canje.py](sniper_canje.py)) para detectar en tiempo real cualquier código de **Xbox de 25 caracteres** (`XXXXX-XXXXX-XXXXX-XXXXX-XXXXX`) que aparezca en pantalla (YouTube, Twitch, Kick, TikTok, WhatsApp, Discord) y canjearlo automáticamente en milisegundos sin necesidad de calibrar coordenadas manualmente.

---

## ⚡ Cómo funciona

1. **Cero calibración:** Localiza automáticamente en vivo dónde está la casilla *"Escribe el código de 25 caracteres"* y los botones **SIGUIENTE** y **CONFIRMAR** de Xbox usando cajas delimitadoras (`bounding_rect`) del motor OCR nativo de Windows.
2. **Auto-instalable:** La primera vez que lo ejecutas, instala automáticamente sus únicas dependencias (`mss` y `winocr`).
3. **Inyección por hardware (`SendInput`):** Hace clic y escribe los 25 caracteres directamente a nivel de kernel de Windows (`< 1 ms` por tecla) sin depender del portapapeles.
4. **Filtro inteligente del alfabeto de Xbox:** Ignora enlaces web y texto normal, y corrige confusiones ópticas del OCR basándose en el alfabeto oficial sin vocales de Microsoft (`BCDFGHJKMPQRTVWXYZ2346789`).

---

## 🤖 Instrucciones Rápidas para cualquier Agente de IA

Si eres un **Agente de IA** ayudando al usuario a clonar y ejecutar este repositorio, sigue exactamente estos pasos:

1. **Verificar Python:** Comprueba que Python 3.10+ esté instalado en Windows (`python --version`).
2. **Instalar dependencias:** Ejecuta:
   ```powershell
   python -m pip install mss winocr
   ```
3. **Regla crítica de ejecución en Windows (UIPI / `SendInput`):**
   - **NO ejecutes** `sniper_canje.py` dentro de la terminal interna/sandbox del agente de IA, ya que el aislamiento de procesos de Windows bloquea `SendInput` (`eventos=0`) e impide mover el mouse físico sobre el navegador.
   - El script debe ejecutarse directamente en una consola **CMD o PowerShell abierta por el usuario en su escritorio** (o mediante doble clic).
4. **Comando para iniciar:**
   ```powershell
   python sniper_canje.py
   ```

---

## 👤 Instrucciones de Uso (Paso a Paso)

1. Abre `https://www.xbox.com/es-CO/redeem` (o `https://redeem.microsoft.com`), inicia sesión y deja visible la ventana donde dice **"Escribe el código de 25 caracteres"**.
2. Pon tu pantalla dividida (mitad y mitad):
   - **Mitad izquierda:** El directo, video o chat de WhatsApp donde saldrá el código.
   - **Mitad derecha:** La ventana de canje de Xbox.
3. Abre **PowerShell** o **CMD** en esta carpeta y ejecuta:
   ```powershell
   python sniper_canje.py
   ```
4. ¡Listo! Apenas aparezca un código de 25 caracteres en pantalla, el bot moverá el mouse solo a la casilla de Xbox, escribirá el código y pulsará **SIGUIENTE** y **CONFIRMAR** automáticamente.
