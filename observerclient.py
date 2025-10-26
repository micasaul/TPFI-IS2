import json, socket, time, argparse, uuid

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
RETRY_SECONDS = 30  # intervalo de reconexión fijo


def cpu_uuid():
    return str(uuid.UUID(int=uuid.getnode()))


def main():
    p = argparse.ArgumentParser(description="Cliente observador del TPFI")
    p.add_argument("-s", "--server", default=DEFAULT_HOST, help="Host del servidor (default: localhost)")
    p.add_argument("-p", "--port", type=int, default=DEFAULT_PORT, help="Puerto (default: 8080)")
    p.add_argument("-o", "--output", help="Archivo donde guardar notificaciones")
    p.add_argument("-v", "--verbose", action="store_true", help="Mostrar información de depuración")
    args = p.parse_args()

    payload = {"UUID": cpu_uuid(), "ACTION": "subscribe"}

    while True:
        try:
            if args.verbose:
                print(f"[OBSERVER] Conectando a {args.server}:{args.port}")

            with socket.create_connection((args.server, args.port)) as s:
                s.sendall((json.dumps(payload) + "\n").encode("utf-8"))
                if args.verbose:
                    print("[OBSERVER] Suscripto. Esperando actualizaciones...")

                buffer = b""
                while True:
                    chunk = s.recv(4096)
                    if not chunk:
                        if args.verbose:
                            print("[OBSERVER] Conexión cerrada por el servidor")
                        break
                    buffer += chunk
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        if not line.strip():
                            continue
                        try:
                            msg = json.loads(line.decode("utf-8"))
                        except Exception as e:
                            if args.verbose:
                                print("[OBSERVER] Error decodificando JSON:", e)
                            continue
                        text = json.dumps(msg, ensure_ascii=False, indent=2)
                        print(text)
                        if args.output:
                            with open(args.output, "a", encoding="utf-8") as f:
                                f.write(text + "\n")
        except Exception as e:
            if args.verbose:
                print(f"[OBSERVER] Error: {e}")

        if args.verbose:
            print(f"[OBSERVER] Reintentando en {RETRY_SECONDS} segundos...")
        time.sleep(RETRY_SECONDS)


if __name__ == "__main__":
    main()
