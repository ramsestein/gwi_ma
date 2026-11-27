# Preparar el PC Windows

Este PC se usa para capturar los protocolos (BIS ⇄ VitalRecorder), analizarlos y
probar el prototipo del traductor (BIS ⇄ PC ⇄ Masimo). Los comandos son para
PowerShell.

## 1. Python y git

1. Descarga Python 3.12 o 3.13 de 64 bits desde python.org e instálalo. En la
   primera pantalla marca **"Add python.exe to PATH"**.
2. Descarga e instala Git for Windows desde git-scm.com, con las opciones por defecto.
3. Comprueba en una PowerShell nueva:

```powershell
py --version
git --version
```

## 2. El repositorio y sus dependencias

```powershell
cd ~
git clone https://github.com/ramsestein/gwi_ma.git
cd gwi_ma
py -m pip install -r requirements.txt vitaldb
```

Todos los comandos de las herramientas se lanzan desde la carpeta `gwi_ma`, con
`py -m src.<capa>.<herramienta>`. Para actualizar el código más adelante, usa
`git pull`.

## 3. Wireshark con USBPcap

1. Descarga el instalador de Windows x64 desde wireshark.org.
2. Durante la instalación, cuando ofrezca componentes adicionales, marca **USBPcap**.
3. **Reinicia el PC.**
4. Abre Wireshark: en la lista de interfaces deben aparecer `USBPcap1`, `USBPcap2`…
   Al empezar una captura USB, Windows pedirá permiso de administrador: acéptalo.

USBPcap tiene el driver firmado y funciona con Secure Boot activado.

## 4. VitalRecorder

Descárgalo de vitaldb.net e instálalo. El dispositivo BIS se añade en
VitalRecorder sobre el puerto COM del adaptador (paso 5).

## 5. El adaptador USB-RS232

1. Enchúfalo y abre el Administrador de dispositivos → **Puertos (COM y LPT)**.
   Apunta su número (por ejemplo, `COM3`). No debe tener un aviso amarillo.
   - Con un adaptador Prolific, un aviso amarillo suele indicar un chip antiguo
     o falsificado que los drivers actuales rechazan. Cámbialo por uno FTDI.
2. **Si es FTDI:** abre Propiedades → Configuración de puerto → Opciones avanzadas
   y pon **Temporizador de latencia: 1 ms**. Así las marcas de tiempo de las
   capturas son más precisas.
3. **Que Windows no lo duerma durante las capturas:**
   - Opciones de energía → Cambiar la configuración del plan → Cambiar la
     configuración avanzada → Configuración de USB → **Suspensión selectiva de
     USB: Deshabilitada**.
   - En el mismo plan, que el equipo no entre en suspensión mientras capturas.
4. Si vas a conectar el BIS con el sensor puesto a una persona, usa un adaptador
   con aislamiento galvánico. Con un sensor de prueba en banco, no hace falta.

## 6. Comprobación

Desde la carpeta `gwi_ma`, con el adaptador enchufado:

```powershell
py -m src.utils.check_setup
```

Todo tiene que salir `[OK]`, salvo quizá algún `[WARN]`. Si sale algún `[FAIL]`,
el propio mensaje dice cómo arreglarlo. Pega la salida en el chat.

## 7. Ensayo sin BIS

Comprueba toda la cadena de captura antes de ir al monitor.

1. **Prepara un bucle:**
   - con un solo adaptador, une las patillas 2 y 3 de su conector DB-9 con un
     cable o un clip;
   - con dos adaptadores, únelos con un cable null-modem.
2. En Wireshark, empieza a capturar en el `USBPcapN` donde está el adaptador. Si
   no sabes cuál es, prueba uno a uno: es el que muestra tráfico en el paso 3.
3. Lanza la prueba en bucle. Con un adaptador, se pone el mismo puerto dos veces:

```powershell
py -m src.utils.serial_loopback COM3 COM3 --sweep 9600,57600 --frames 50
```

   Con dos adaptadores: `py -m src.utils.serial_loopback COM3 COM4 --sweep 9600,57600 --frames 50 --both`

4. Detén la captura en Wireshark y guárdala como `dumps\ensayo.pcapng`, dentro de
   la carpeta `gwi_ma`. La carpeta `dumps` no se sube nunca al repositorio.
5. Reconstruye la conversación:

```powershell
py -m src.acquisition.usbpcap_conversation dumps\ensayo.pcapng dumps\ensayo
```

**Qué debe salir:**
- la prueba en bucle termina en `RESULT: OK`;
- el extractor muestra la configuración del puerto (9600 y 57600, 8N1);
- con un solo adaptador, los bytes enviados (H2D) y recibidos (D2H) coinciden.

Pega las dos salidas en el chat. Con esto sabemos que la captura de tu adaptador
se reconstruye bien antes de ponerla delante del BIS.

## Recordatorio

El repositorio es público. Capturas, ficheros `.vital` y cualquier dato del
hospital se quedan en `dumps\` o fuera del repositorio, y nunca se suben.
