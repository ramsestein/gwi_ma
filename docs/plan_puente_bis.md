# Plan: puente BIS VISTA → Masimo con Raspberry Pi

## Objetivo

Hoy el BIS VISTA envía por su puerto serie el protocolo **ASCII** al concentrador
de Masimo, y el ASCII no lleva la curva de EEG. Queremos la curva sin perder lo
que recibe Masimo.

Solución: una Raspberry Pi que hace de traductor, con tres adaptadores USB-RS232.

```
BIS VISTA ⇄ [1: binario, la Pi es el host] ⇄ Raspberry Pi ⇄ [2: ASCII, la Pi emula al BIS] ⇄ Masimo
                                                    └──⇄ [3: Vista Binary, la Pi emula al BIS] ⇄ PC con VitalRecorder
```

- **Puerto 1, BIS:** la Pi mantiene su propia sesión binaria con el monitor, como
  hace VitalRecorder, y guarda los últimos valores y la EEG.
- **Puerto 2, Masimo:** la Pi se comporta exactamente como un BIS en modo ASCII,
  con el mismo formato, la misma cadencia y los mismos estados (sensor
  desconectado, artefacto, SQI bajo…).
- **Puerto 3, investigación:** la Pi se comporta como un BIS en Vista Binary, de
  modo que VitalRecorder se conecta a ella como si fuera el monitor y registra la
  curva. Responde a las peticiones de VitalRecorder con los datos de su propia
  sesión.
- Los tres lados están desacoplados. **La Pi es el único host del BIS.** Si
  VitalRecorder hablara con el BIS a través de la Pi, Masimo dependería de que el
  PC de investigación estuviera encendido.
- Si el BIS vuelve a ASCII (por ejemplo, tras un reinicio), la Pi lo detecta y lo
  pasa tal cual a Masimo.
- **Decidido:** el puerto 3 sale en Vista Binary, para mantener los drivers y
  formatos de los ordenadores que ya se usan.

Los protocolos no son públicos. Los aprendemos solo con el PC y el BIS:

- el **ASCII**, registrando lo que emite el BIS;
- el **binario**, observando a VitalRecorder, que ya sabe hablarlo, y usando sus
  ficheros `.vital` (valores ya decodificados) como referencia.

## Modelo de trabajo

- El código vive en `gwi_ma` y se sube a `main`.
- La Pi (Raspberry Pi 3 Model B, 64 bits, Python 3.13) se maneja por SSH desde el
  PC del equipo. No ejecuta Claude.
- En la Pi solo se instala lo necesario para el puente: Python, `pyserial` y git.
  Los análisis pesados (numpy, scipy, gráficas) se hacen en el PC.
- **El repositorio es público.** Ninguna captura, `.vital`, dato de paciente, IP
  ni nombre del hospital va al repo. Las capturas de banco se guardan en local o
  en un repositorio privado.

## Qué necesitamos

### Hardware

| Elemento | Para qué |
| :--- | :--- |
| Raspberry Pi 3B, tarjeta SD, fuente oficial | El traductor (ya la tenemos) |
| 3 adaptadores USB-RS232 para la Pi, mejor con chip FTDI y **aislamiento galvánico** | Puertos 1 (BIS), 2 (Masimo) y 3 (investigación) |
| 1 adaptador USB-RS232 para el PC de captura | Conectar VitalRecorder al BIS |
| Cables o adaptadores null-modem y de género DB-9 | Pi ⇄ Masimo y Pi ⇄ PC de investigación. Hay que comprobar con el polímetro si el puerto del BIS es como el de un PC (DTE) y elegir el cable según eso |
| Polímetro | Identificar qué patilla transmite cada equipo |
| PC con VitalRecorder y captura USB (ver más abajo) | Host de referencia que habla binario con el BIS |
| BIS VISTA con sensor de prueba o simulador (lo que tenga Electromedicina) | Sesiones de captura en banco |
| Concentrador Masimo, cuando llegue | Validación final del puerto 2 |

Siempre que el BIS esté conectado a una persona, todo lo que se enchufe a su
puerto serie tiene que ir aislado.

### Captura en el PC

**Decidido: PC con Windows**, con VitalRecorder y Wireshark + USBPcap.
`usbpcap_conversation` ya lee estas capturas. En ese PC también se puede usar
`serial_tap` (con Python y `pyserial`):

- para la ASCII de la fase 1a;
- en modo puente, con dos adaptadores físicos, para poner el PC entre dos
  equipos (no hacen falta puertos virtuales; com0com no funciona con Secure Boot).

### Software

**Ya disponible en `gwi_ma`:**

| Herramienta | Uso |
| :--- | :--- |
| `serial_tap` | Captura con marca de tiempo de uno o dos puertos, en Windows o en la Pi. Modo escucha (Y pasiva, nunca escribe) o modo puente (reenvía entre los dos puertos). Marcas de evento tecleadas. Mismo formato de `_timeline.csv` que `usbpcap_conversation` |
| `serial_loopback` | Prueba en bucle entre dos adaptadores unidos por null-modem: tramas perdidas o corruptas y retardo, a varias velocidades |
| `serial_ports` | Lista los adaptadores USB-serie y genera las reglas udev de nombres fijos |
| `pi/setup.sh` | Prepara la Pi: paquetes, grupo `dialout`, repo y venv con `pyserial` |
| `data_logger` | Registro simple de un puerto a fichero binario |
| `usbpcap_conversation` | Conversación ordenada VitalRecorder ⇄ BIS y configuración del puerto, a partir de una captura USBPcap |
| `baud_detector` | Velocidad del puerto |
| `framing_scanner`, `packet_finder`, `stat_analyzer` | Estructura de las tramas |
| `checksum_cracker` | Checksum o CRC |
| `entropy_analyzer`, `semantic_explorer`, `lut_detector`, `bit_analyzer` | Significado de los campos |
| `waveform_profiler`, `fft_analyzer` | Localizar y validar la EEG en las tramas |
| `differential_analyzer` | Comparar sesiones (estados distintos) |
| `handshake_replay` | Reproducir el arranque del protocolo desde la Pi |

**Por escribir en `gwi_ma`:**

| Herramienta | Fase | Qué hace |
| :--- | :--- | :--- |
| `vital_correlator` | 2 | Lee el `.vital` con la librería `vitaldb` y localiza en los bytes las muestras de EEG y los valores de BIS, SQI, EMG, SR, SEF… |
| Decodificador binario del BIS | 2 | Definición del protocolo y decodificador, validado contra los `.vital` |
| Cliente BIS (puerto 1) | 3 | La Pi hace de host del BIS en lugar de VitalRecorder |
| Emulador ASCII (puerto 2) | 3 | Genera la salida ASCII del BIS, validada contra las capturas reales |
| Emulador Vista Binary (puerto 3) | 3 | Responde a VitalRecorder como lo haría el BIS |
| Simulador de BIS | 3 | Reproduce sesiones grabadas para probar la Pi sin monitor |
| Servicio del traductor | 4 | systemd, watchdog, modo "pasar tal cual", registro e imagen de solo lectura |

**Externo:** VitalRecorder, Wireshark con USBPcap y la librería `vitaldb` (pip,
en el PC de análisis).

### Información y gestiones (empezar ya, tardan)

- Manual del BIS VISTA: apartados del protocolo serie y del menú de mantenimiento.
- Medtronic: especificación de los protocolos ASCII, Vista Binary y Legacy Binary,
  y qué sale por el USB tipo B.
- Masimo: qué espera su driver del BIS en ASCII (velocidad, formato, si envía
  peticiones).
- Electromedicina: préstamo de BIS y sensor de prueba para banco, y visto bueno
  para el montaje.
- Regulatorio: fabricación propia según el artículo 5.5 del MDR, análisis de
  riesgos y, si es investigación, el CEIm.

## Fases

El traductor se escribe en Python con `pyserial`, así que el mismo código funciona
en Windows (prototipo, fase 3) y en la Pi (fase 4).

### Fase 0: preparación

**PC Windows** (guía paso a paso en `docs/preparar_windows.md`):
- [ ] Python, git y el repo, con las dependencias.
- [ ] Wireshark con USBPcap.
- [ ] VitalRecorder.
- [ ] Adaptador USB-RS232 reconocido como puerto COM, sin suspensión USB, y si es
      FTDI, con latencia de 1 ms.
- [ ] `check_setup` sin fallos.
- [ ] Ensayo sin BIS: prueba en bucle con captura USBPcap, y
      `usbpcap_conversation` reconstruye las dos direcciones.

**Pi:**
- [x] Accesible por SSH con clave (`ssh bisbridge`).
- [ ] `pi/setup.sh` (git, venv, `pyserial`, grupo `dialout`, repo).
- [ ] Reglas udev con `serial_ports` (`/dev/ttyBIS`, `/dev/ttyMASIMO`, `/dev/ttyRESEARCH`).
- [ ] `serial_loopback` entre dos adaptadores, a varias velocidades.

**Material y gestiones:** comprar lo que falte y lanzar las consultas a Medtronic,
Masimo y Electromedicina.

### Fase 1: el BIS conectado al PC, en cada modo

Montaje: BIS ⇄ cable ⇄ adaptador USB-RS232 ⇄ PC Windows. Una sesión por modo del
puerto serie del BIS: **ASCII**, **Vista Binary** y **Legacy Binary**.

- **Arrancar Wireshark antes de abrir el puerto en VitalRecorder**, para tener la
  configuración del puerto y el arranque del protocolo.
- Si VitalRecorder no recibe datos en ASCII, capturar el ASCII con `serial_tap`.
  Un puerto COM no se puede abrir desde dos programas a la vez.
- Preguntas a responder:
  - ¿el BIS emite ASCII por sí solo o espera una petición?
  - ¿en qué modo binario recibe VitalRecorder la curva de EEG?

**Estados a recorrer en cada modo** (sesiones de 30 minutos o más):
- el BIS arranca con el PC ya conectado;
- el PC se conecta con el BIS ya en marcha;
- sensor desconectado, chequeo de impedancias, buena señal y artefactos;
- el PC se desconecta y se vuelve a conectar;
- el BIS se reinicia (¿conserva el modo del puerto?).

**Guardar de cada sesión:** el `.pcapng`, el `.vital` y notas con las horas de cada
evento. Si la exportación USB del BIS funciona a la vez que el puerto serie,
exportar también los `.spa`/`.r2a`: dan los valores procesados en paralelo y
sirven para cruzar el ASCII con el binario.

**Sale cuando** tenemos sesiones completas de los tres modos en todos los estados.

### Fase 2: sacar los protocolos, en el PC

1. `usbpcap_conversation`: la conversación ordenada y la configuración del puerto
   de cada sesión.
2. ASCII: campos, separadores, cadencia y cómo marca cada estado. Si la
   exportación USB funcionó en paralelo, el `.spa` dice qué es cada columna.
3. Binario:
   - `framing_scanner`, `packet_finder` y `checksum_cracker` dan las tramas y el
     checksum;
   - comandos del host: qué envía VitalRecorder, en qué orden y con qué cadencia;
   - tipos de trama del BIS: procesados, EEG, estados y errores;
   - `vital_correlator`: dónde va cada valor y su escala, usando el `.vital` como
     referencia.
4. Definición de los protocolos y decodificador.

**Sale cuando** el decodificador reproduce las muestras de EEG y los valores
procesados del `.vital` en todas las sesiones, y entendemos todos los mensajes
de los dos lados.

### Fase 3: prototipo del traductor en el PC Windows (BIS ⇄ PC ⇄ Masimo)

Necesita un Masimo. Mientras no llegue, en su lugar va otro puerto que registra
lo que le enviamos, comparado con el ASCII real de la fase 1.

1. **Primero, escuchar.** `serial_tap` con la Y (dos adaptadores solo-RX) sobre el
   cable BIS ⇄ Masimo, con el BIS en ASCII. ¿Masimo envía algo?, ¿qué velocidad y
   formato usa?
2. **Después, el traductor.** El BIS va en binario y el PC hace de host. Hacia
   Masimo, el PC emula el ASCII. Comprobamos qué capturamos del BIS y qué
   devolvemos a Masimo.

**Sale cuando** Masimo muestra y registra el BIS igual que con conexión directa,
en todos los estados.

### Fase 4: el traductor en la Pi, con el tercer puerto

- Mismo código que en la fase 3, en la Pi: puerto 1 al BIS y puerto 2 a Masimo.
- **Puerto 3 al PC con VitalRecorder:** la Pi emula al BIS en modo binario y
  VitalRecorder captura la curva como si estuviera conectado al monitor.
- Servicio systemd, watchdog, modo "pasar tal cual" si llega ASCII desde el BIS.

**Sale cuando** Masimo y VitalRecorder reciben a la vez lo mismo que con conexión
directa.

### Fase 5: pruebas en banco

- Pruebas de duración: 72 horas.
- Fallos provocados:
  - desconectar el BIS, el sensor, Masimo o el PC de VitalRecorder;
  - reiniciar la Pi y el BIS;
  - que el BIS vuelva a ASCII.
- Medir el retardo extremo a extremo.
- Imagen de la Pi con sistema de ficheros de solo lectura y sin internet.
- Procedimiento de vuelta atrás: cable directo y BIS a ASCII.

### Fase 6: validación y paso a clínica

- Electromedicina: sistema electromédico según IEC 60601-1 (aislamiento, fugas).
- Análisis de riesgos y gestión de la red con Informática (IEC 80001-1).
- Documentación de fabricación propia (artículo 5.5 del MDR) y, si aplica, el CEIm.
- Protección de datos de la EEG en el PC de investigación.
- Piloto controlado.

## Decisiones tomadas

- El puerto 3 emula el modo binario que ya usan los ordenadores de investigación
  con VitalRecorder, para no cambiar nada en ellos.
- PC de captura y de prototipo con Windows (VitalRecorder + Wireshark con USBPcap).
- El traductor se prototipa en Windows y luego pasa a la Pi, con el mismo código.

## Decisiones abiertas

| Decisión | Se resuelve en |
| :--- | :--- |
| ¿El BIS emite ASCII por sí solo o espera una petición? | Fase 1 |
| ¿En qué modo binario recibe VitalRecorder la curva? | Fase 1 |
| Modo binario del puerto 1 (BIS) y del puerto 3 (VitalRecorder): Vista Binary o Legacy Binary | Fase 1 |
| ¿Acepta el driver de Masimo el ASCII emulado? | Fase 3 |
| Modelo de adaptador aislado | Fase 0 |
| ¿El USB tipo B del BIS da algo útil en paralelo? | Respuesta de Medtronic |
