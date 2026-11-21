"""
Cliente WebSocket de prueba para la API coordinadora.

Verifica que el canal en tiempo real cumple el RFC 6455: realiza el
handshake, recibe el mensaje de bienvenida y escucha las predicciones que
la API difunde mientras se generan en paralelo.

Implementado sobre la biblioteca estándar de Python, sin dependencias.

Uso:
    python scripts/prueba_websocket.py [host] [puerto]
"""
import base64
import json
import os
import socket
import struct
import sys
import threading
import time
import urllib.request

HOST = sys.argv[1] if len(sys.argv) > 1 else "localhost"
PUERTO = int(sys.argv[2]) if len(sys.argv) > 2 else 8090


def leer_trama(sock):
    """Lee una trama WebSocket del servidor (sin máscara)."""
    cab = sock.recv(2)
    if len(cab) < 2:
        return None
    largo = cab[1] & 0x7F
    if largo == 126:
        largo = struct.unpack(">H", sock.recv(2))[0]
    elif largo == 127:
        largo = struct.unpack(">Q", sock.recv(8))[0]
    datos = b""
    while len(datos) < largo:
        trozo = sock.recv(largo - len(datos))
        if not trozo:
            break
        datos += trozo
    return datos.decode("utf-8", errors="replace")


def generar_trafico(token):
    """Lanza predicciones para que el servidor tenga algo que difundir."""
    time.sleep(1.5)
    deptos = ["CUSCO", "LIMA", "PUNO", "LORETO", "AREQUIPA"]
    for i in range(5):
        cuerpo = json.dumps({
            "edad": 10 + i * 15,
            "sexo": "MASCULINO" if i % 2 else "FEMENINO",
            "departamento": deptos[i],
            "fabricante": "PFIZER",
            "dias_desde_primera_dosis": 300 + i * 37,
            "intervalo_entre_dosis": 20 + i * 53,
        }).encode()
        req = urllib.request.Request(
            f"http://{HOST}:{PUERTO}/api/predecir", data=cuerpo,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {token}"})
        try:
            urllib.request.urlopen(req, timeout=5).read()
        except Exception as e:
            print(f"  (error al generar tráfico: {e})")
        time.sleep(0.7)


def main():
    print("=" * 62)
    print("PRUEBA DEL CANAL WEBSOCKET EN TIEMPO REAL")
    print("=" * 62)
    print(f"  destino : ws://{HOST}:{PUERTO}/ws")
    print()

    # Token para poder generar tráfico mientras se escucha.
    req = urllib.request.Request(
        f"http://{HOST}:{PUERTO}/api/login",
        data=json.dumps({"usuario": "admin", "contrasena": "minsa2026"}).encode(),
        headers={"Content-Type": "application/json"})
    token = json.loads(urllib.request.urlopen(req, timeout=5).read())["token"]
    print(f"  token obtenido ({len(token)} caracteres)")

    # Handshake WebSocket.
    clave = base64.b64encode(os.urandom(16)).decode()
    s = socket.create_connection((HOST, PUERTO), timeout=30)
    s.sendall((
        f"GET /ws HTTP/1.1\r\n"
        f"Host: {HOST}:{PUERTO}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {clave}\r\n"
        f"Sec-WebSocket-Version: 13\r\n\r\n"
    ).encode())

    resp = b""
    while b"\r\n\r\n" not in resp:
        resp += s.recv(1024)
    primera = resp.split(b"\r\n")[0].decode()
    print(f"  handshake: {primera}")
    if "101" not in primera:
        print("  ERROR: el servidor no promovió la conexión")
        return
    print("  conexión establecida (RFC 6455)")
    print()

    threading.Thread(target=generar_trafico, args=(token,), daemon=True).start()

    print("  MENSAJES RECIBIDOS")
    print("  " + "-" * 58)
    recibidos = 0
    inicio = time.time()
    s.settimeout(12)
    while recibidos < 7 and time.time() - inicio < 25:
        try:
            msg = leer_trama(s)
        except socket.timeout:
            break
        if msg is None:
            break
        recibidos += 1
        try:
            d = json.loads(msg)
            tipo = d.get("tipo", "?")
            if tipo == "bienvenida":
                print(f"  [{recibidos}] bienvenida: {d.get('predicciones')} predicciones "
                      f"acumuladas, latencia media {d.get('latencia_media_ms')} ms")
            elif tipo == "prediccion":
                print(f"  [{recibidos}] predicción: {d.get('departamento'):<10} "
                      f"edad {d.get('edad'):<3} p={d.get('probabilidad'):.4f} "
                      f"riesgo {d.get('riesgo')}")
            elif tipo == "latido":
                print(f"  [{recibidos}] latido: {d.get('predicciones')} predicciones, "
                      f"{d.get('clientes')} cliente(s) conectado(s)")
            else:
                print(f"  [{recibidos}] {msg[:90]}")
        except json.JSONDecodeError:
            print(f"  [{recibidos}] (no JSON) {msg[:90]}")

    s.close()
    print()
    print("  " + "-" * 58)
    print(f"  total de mensajes recibidos: {recibidos}")
    print(f"  RESULTADO: {'canal operativo' if recibidos >= 2 else 'sin mensajes'}")
    print("=" * 62)


if __name__ == "__main__":
    main()
