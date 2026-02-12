# Acquired Knowledge: IntelliVue MX750 Protocol

## 1. Physical Layer
- **Baud Rate**: 115200 bps
- **Parity**: None
- **Stop Bits**: 1
- **Flow Control**: None detected.

## 2. Framing & Transport
- **Protocol**: SLIP (Serial Line Internet Protocol)
- **Framing Bytes**: 
  - `0xC0` (END)
  - `0xDB` (ESC)
  - `0xDB 0xDC` -> `0xC0`
  - `0xDB 0xDD` -> `0xDB`

## 3. Session Layer (Handshake)
- **Wakeup Sequence**: `0x11 0x01` (Session Header)
- **Extended Poll**: `0x09 0x01`
- **Assoc Req**: `0x0D 0x01`

## 4. Application Layer (Semantics)
- **F13B Packet**: Contains numeric vital signs.
- **Waveforms**: Found in specific OID ranges.
- **Checksum**: CRC-16 (Modbus/X25 variant).

## 5. Security
- Use of specific association request frames to unlock extended data.


# Wireshark + USBPcap: Captura de tráfico serial por USB

## Contexto

En el proyecto **VitalParser**, la comunicación con el monitor Philips IntelliVue se realiza a través de un adaptador **ATEN USB-to-Serial (COM4)**. Wireshark, combinado con USBPcap, permite capturar y analizar los paquetes crudos que viajan por el bus USB entre el PC y el adaptador serial.

## ¿Qué es USBPcap?

USBPcap es un driver de captura de tráfico USB para Windows que se integra con Wireshark. Actúa como un **sniffer pasivo** sobre el bus USB, interceptando todos los paquetes sin interferir en la comunicación — funcionando efectivamente como un **man-in-the-middle** a nivel USB.

## ¿Qué se puede hacer?

- **Capturar paquetes crudos USB** entre el PC y el adaptador ATEN USB-to-Serial, incluyendo los datos serie que viajan encapsulados en el protocolo USB.
- **Inspeccionar el protocolo USB completo**: enumeración del dispositivo, descriptores, configuración de endpoints, control transfers, y los datos serie en interrupt/bulk transfers.
- **Filtrar por dispositivo** usando `usb.device_address` para aislar el tráfico del adaptador ATEN del resto de dispositivos USB.
- **Filtrar por tipo de transferencia** con `usb.transfer_type == 3` (interrupt) o `usb.transfer_type == 1` (bulk) para ver solo los datos serie, descartando el tráfico de control USB.
- **Exportar capturas a `.pcap`** para análisis posterior o para compartir con el equipo.
- **Analizar timing y latencias** entre paquetes, útil para debugging de problemas de comunicación con el IntelliVue.
- **Detectar errores de comunicación** como NAKs, STALLs, o timeouts a nivel USB.
- **Comparar sesiones de captura** para identificar diferencias en el comportamiento del protocolo.

## ¿Qué hemos descubierto?

1. **Wireshark no captura puertos COM directamente** — no existe una interfaz de captura para puertos serie nativos. La captura se hace a nivel USB subyacente.
2. **USBPcap ya está instalado** en el sistema y expone tres interfaces de captura: USBPcap1, USBPcap2 y USBPcap3, correspondientes a los distintos controladores USB del PC.
3. **com0com no es viable** en este sistema porque Secure Boot está activado y bloquea la instalación de drivers sin firma digital.
4. **Para testing sin hardware**, se puede simular la comunicación serial usando sockets TCP con `serial.serial_for_url('socket://localhost:12345')`, evitando la necesidad de puertos virtuales.

## Cómo usar (paso a paso)

1. Abrir Wireshark.
2. Dejar la barra de filtro de captura **vacía**.
3. Seleccionar las tres interfaces USBPcap (Ctrl+clic) o probar una por una.
4. Iniciar captura.
5. Identificar cuál interfaz muestra tráfico del adaptador ATEN.
6. Aplicar filtros de visualización:
   - `usb.device_address == X` → aislar el dispositivo ATEN.
   - `usb.transfer_type == 3` → ver solo datos serie (interrupt transfers).
   - `usb.data_len > 0` → mostrar solo paquetes con payload.
7. Inspeccionar el campo **"Leftover Capture Data"** o **"URB bulk/interrupt data"** en cada paquete para ver los bytes crudos del protocolo serie.

## Man-in-the-middle pasivo

USBPcap permite observar **toda la comunicación** entre el sistema operativo y el dispositivo USB sin que ninguno de los dos extremos lo detecte. Esto incluye:

- Datos serie enviados y recibidos por COM4.
- Comandos de configuración del puerto (baudrate, paridad, stop bits).
- Señales de control (DTR, RTS, CTS, DSR).
- Errores y retransmisiones a nivel USB.

Es un **man-in-the-middle pasivo**: solo observa, no modifica paquetes. Es útil para reverse engineering del protocolo del IntelliVue o para validar que VitalParser envía/recibe los datos correctos.

## Limitaciones

- Los datos serie aparecen **encapsulados en paquetes USB**, no como bytes serie directos — requiere interpretación manual.
- No se puede **modificar** paquetes en tránsito (es solo lectura).
- Para captura y logging simple de datos serie, un script Python con `pyserial` es más práctico y legible.
- La correspondencia entre interfaz USBPcap y controlador USB físico no siempre es obvia — hay que probar.