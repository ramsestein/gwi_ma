# Plan: puente BIS VISTA → Masimo con Raspberry Pi

## Objetivo

Hoy el BIS VISTA envía por su puerto serie el protocolo **ASCII** al concentrador
de Masimo, y el ASCII no lleva la curva de EEG. Queremos la curva sin perder lo
que recibe Masimo.

Solución: una Raspberry Pi entre los dos equipos.

```
BIS VISTA ⇄ (protocolo binario, con EEG) ⇄ Raspberry Pi ⇄ (ASCII, emulando al BIS) ⇄ Masimo
                                                └──→ EEG + variables → PC de investigación
```

- **Lado BIS:** la Pi mantiene su propia sesión binaria con el monitor, como hace
  VitalRecorder, y guarda los últimos valores y la EEG.
- **Lado Masimo:** la Pi se comporta exactamente como un BIS en modo ASCII, con el
  mismo formato, la misma cadencia y los mismos estados (sensor desconectado,
  artefacto, SQI bajo…).
- Los dos lados están desacoplados. **No se traduce petición a petición.**
- Si el BIS vuelve a ASCII (por ejemplo, tras un reinicio), la Pi lo detecta y lo
  pasa tal cual.

El protocolo binario no es público. Lo aprendemos observando a VitalRecorder, que
ya sabe hablarlo, y usando como referencia sus ficheros `.vital` (valores ya
decodificados).

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
| Raspberry Pi 3B, tarjeta SD, fuente oficial | Escucha pasiva en las fases 1-2 y puente en las fases 4-5 (ya la tenemos) |
| 3 adaptadores USB-RS232, mejor con chip FTDI y **aislamiento galvánico** | 2 para escuchar (uno por dirección) y 1 para pruebas en bucle; en el puente final, 1 hacia el BIS y 1 hacia Masimo |
| Adaptador null-modem y adaptadores de género DB-9 | Pruebas en bucle y conexiones |
| 1-2 conectores DB-9 con bornes | Montar la Y de solo escucha (RX y masa) |
| Polímetro | Identificar qué patilla transmite cada equipo |
| PC Windows con VitalRecorder, Wireshark + USBPcap y un adaptador USB-RS232 | Host de referencia que habla binario con el BIS |
| BIS VISTA con sensor de prueba o simulador (lo que tenga Electromedicina) | Sesiones de captura en banco |

Siempre que el BIS esté conectado a una persona, todo lo que se enchufe a su
puerto serie tiene que ir aislado.

### Software

**Ya disponible en `gwi_ma`:**

| Herramienta | Uso |
| :--- | :--- |
| `usbpcap_conversation` | Conversación ordenada VitalRecorder ⇄ BIS y configuración del puerto, a partir de una captura USBPcap |
| `baud_detector` | Velocidad del puerto en escucha pasiva |
| `framing_scanner`, `packet_finder`, `stat_analyzer` | Estructura de las tramas |
| `checksum_cracker` | Checksum o CRC |
| `entropy_analyzer`, `semantic_explorer`, `lut_detector`, `bit_analyzer` | Significado de los campos |
| `waveform_profiler`, `fft_analyzer` | Localizar y validar la EEG en las tramas |
| `differential_analyzer` | Comparar sesiones (estados distintos) |
| `handshake_replay` | Reproducir el arranque del protocolo desde la Pi |

**Por escribir en `gwi_ma`:**

| Herramienta | Fase | Qué hace |
| :--- | :--- | :--- |
| `serial_tap` | 0 | Registrador de escucha pasiva en la Pi: dos puertos solo-RX con marca de tiempo y dirección en un único fichero, y marcas de evento tecleadas. Formato compatible con el `_timeline.csv` de `usbpcap_conversation` |
| `serial_bridge` v2 | 0 | Puente activo con registro a fichero y ajustes distintos por lado. Alternativa a la escucha pasiva |
| `vital_correlator` | 3 | Lee el `.vital` con la librería `vitaldb` y localiza en los bytes las muestras de EEG y los valores de BIS, SQI, EMG, SR, SEF… |
| Decodificador binario del BIS | 3 | Definición del protocolo y decodificador, validado contra los `.vital` |
| Cliente BIS en la Pi | 4 | La Pi sustituye a VitalRecorder como host |
| Generador ASCII | 4 | Emula la salida ASCII del BIS, validado contra las capturas reales |
| Simuladores de BIS y de Masimo | 4-5 | Reproducen sesiones grabadas para probar la Pi sin equipos |
| Servicio del puente | 5 | systemd, watchdog, modo "pasar tal cual", registro e imagen de solo lectura |

**Externo:** VitalRecorder, Wireshark + USBPcap (en el PC Windows) y la librería
`vitaldb` (pip, en el PC de análisis).

### Información y gestiones (empezar ya, tardan)

- Manual del BIS VISTA: apartados del protocolo serie y del menú de mantenimiento.
- Medtronic: especificación de Vista Binary y Legacy Binary, y qué sale por el USB tipo B.
- Masimo: qué espera su driver del BIS en ASCII y si admite el modo binario.
- Electromedicina: visto bueno para la escucha en quirófano, préstamo de BIS y
  sensor de prueba para banco, y si es posible, de un concentrador Masimo de banco.
- Regulatorio: fabricación propia según el artículo 5.5 del MDR, análisis de
  riesgos y, si es investigación, el CEIm.

## Fases

### Fase 0: preparación, sin BIS

- [x] Pi accesible por SSH con clave (`ssh bisbridge`).
- [ ] En la Pi: git, venv, `pyserial`, grupo `dialout`, repo clonado.
- [ ] Reglas udev para nombres fijos de los adaptadores según su número de serie
      (`/dev/ttyBIS`, `/dev/ttyMASIMO`, `/dev/ttyTAP_A`, `/dev/ttyTAP_B`).
- [ ] Escribir `serial_tap` y probarlo con puertos virtuales.
- [ ] Prueba en bucle: dos adaptadores unidos por null-modem y un tercero
      escuchando, a varias velocidades. Medir retardos.
- [ ] PC Windows con VitalRecorder y USBPcap listo.
- [ ] Comprar el material que falte y lanzar las gestiones.

**Sale cuando** `serial_tap` registra correctamente las dos direcciones del
bucle a la velocidad que toque.

### Fase 1: referencia ASCII (BIS ⇄ Masimo, sin tocar nada)

Es escucha pasiva en el cableado actual: dos adaptadores solo-RX en la Pi, con el
TX al aire, de modo que **la Pi no puede inyectar nada**.

1. Con el cable desconectado, mide con el polímetro en el puerto del BIS. La
   patilla que da unos -5 a -12 V respecto a la masa (patilla 5) es su TX.
   Repite en el lado de Masimo.
2. Velocidad: con `baud_detector` sobre el puerto de escucha.
3. Grabar varias horas y anotar eventos: arranque, sensor desconectado,
   impedancias, artefactos, fin de caso.

**Queremos saber:**
- ¿Masimo envía algo (peticiones) o solo escucha?
- Formato exacto: cabecera, campos, separadores, finales de línea, cadencia,
  marcas de "valor no válido".
- Qué se envía en cada estado del BIS.

**Sale cuando** tenemos un corpus ASCII de referencia que cubre todos los estados.

### Fase 2: captura binaria con VitalRecorder (banco)

Montaje: BIS ⇄ cable ⇄ PC con VitalRecorder, con la Y pasiva hacia la Pi
(`serial_tap`) y, en paralelo, USBPcap en el PC Windows. Mientras el BIS esté en
modo binario, Masimo no recibe nada: hacedlo en banco o fuera de uso clínico.

- **Arrancad las capturas antes de abrir el puerto en VitalRecorder**, para tener
  la configuración del puerto y el arranque del protocolo.
- Probad los dos modos binarios del menú (**Vista Binary** y **Legacy Binary**) y
  ved en cuál recibe VitalRecorder la curva de EEG.
- Sesiones de 30 minutos o más, con estos estados:
  - el BIS arranca con el host ya conectado;
  - el host se conecta con el BIS ya en marcha;
  - sensor desconectado, chequeo de impedancias, buena señal y artefactos;
  - el host se desconecta y se vuelve a conectar;
  - el BIS se reinicia (¿conserva el modo binario?).
- Guardar de cada sesión: `.pcapng`, captura de la Pi, `.vital` y notas con las
  horas de cada evento.
- Si la exportación USB funciona a la vez que el puerto serie, exportar también
  los `.spa`/`.r2a`. Sirven de verdad de referencia adicional.

**Sale cuando** sabemos qué modo binario usar y tenemos sesiones completas de
todos los estados.

### Fase 3: ingeniería inversa del protocolo binario

1. `usbpcap_conversation` y `serial_tap` dan la conversación.
2. `framing_scanner`, `packet_finder` y `checksum_cracker` dan las tramas y el
   checksum.
3. Comandos del host: qué envía VitalRecorder, en qué orden y con qué cadencia.
4. Tipos de trama del BIS: procesados, EEG, estados y errores.
5. `vital_correlator`: dónde va cada valor y su escala, usando el `.vital` como
   referencia.
6. Definición del protocolo y decodificador.

**Sale cuando** el decodificador reproduce las muestras de EEG y los valores
procesados del `.vital` en todas las sesiones, y entendemos todos los mensajes
que envía VitalRecorder.

### Fase 4: emulación en banco

- **La Pi hace de host del BIS** en lugar de VitalRecorder y recibe los mismos datos.
- **Generador ASCII:** construye la salida ASCII a partir de los valores
  decodificados. Se valida contra el corpus de la fase 1, estado por estado y
  byte a byte en el formato. Los valores se cruzan con los `.spa` exportados por
  USB, si están.
- **Simuladores:** BIS (respondiendo a peticiones) y Masimo (reproduciendo lo
  observado en la fase 1), para probar sin equipos.

**Sale cuando** el ASCII generado no se distingue del real en todos los estados.

### Fase 5: puente completo en banco

- Montaje: BIS ⇄ Pi ⇄ Masimo (concentrador de banco si se consigue; si no, el
  simulador).
- Servicio systemd, watchdog hardware, sistema de ficheros de solo lectura, sin
  internet.
- Modo "pasar tal cual" si llega ASCII desde el BIS.
- Pruebas de duración: 72 horas.
- Fallos provocados:
  - desconectar el BIS, el sensor o Masimo;
  - reiniciar la Pi y el BIS;
  - que el BIS vuelva a ASCII.
- Medir el retardo extremo a extremo.
- Procedimiento de vuelta atrás: cable directo y BIS a ASCII.

**Sale cuando** Masimo muestra y registra el BIS igual que con conexión directa,
en todas las pruebas.

### Fase 6: validación y paso a clínica

- Electromedicina: sistema electromédico según IEC 60601-1 (aislamiento, fugas).
- Análisis de riesgos y gestión de la red con Informática (IEC 80001-1).
- Documentación de fabricación propia (artículo 5.5 del MDR) y, si aplica, el CEIm.
- Protección de datos de la EEG en el PC de investigación.
- Piloto controlado.

## Decisiones abiertas

| Decisión | Se resuelve en |
| :--- | :--- |
| Vista Binary o Legacy Binary (cuál lleva la EEG y cuál decodificamos) | Fase 2 |
| ¿Masimo hace peticiones o solo escucha? | Fase 1 |
| Destino y formato de la EEG (CSV/EDF, envío en tiempo real) | Antes de la fase 5 |
| Modelo de adaptador aislado | Fase 0 |
| ¿El USB tipo B del BIS da algo útil en paralelo? | Respuesta de Medtronic |
