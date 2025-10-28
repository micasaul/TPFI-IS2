import json, socket, argparse, uuid, logging

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080


def cpu_uuid():
    return str(uuid.UUID(int=uuid.getnode()))


def main():
    p = argparse.ArgumentParser(description="Cliente principal del TPFI")
    p.add_argument("-s", "--server", default=DEFAULT_HOST, help="Host del servidor (default: localhost)")
    p.add_argument("-p", "--port", type=int, default=DEFAULT_PORT, help="Puerto (default: 8080)")
    p.add_argument("-i", "--input", required=True, help="Archivo JSON de entrada (get/set/list)")
    p.add_argument("-o", "--output", help="Archivo JSON de salida")
    p.add_argument("-v", "--verbose", action="store_true", help="Mostrar información de depuración")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='[%(levelname)s] %(message)s'
    )

    with open(args.input, "r", encoding="utf-8") as f:
        req = json.load(f)

    req.setdefault("UUID", cpu_uuid())

    logging.info("Conectando a %s:%d", args.server, args.port)
    with socket.create_connection((args.server, args.port)) as s:
        s.sendall((json.dumps(req) + "\n").encode("utf-8"))
        data = s.recv(65535).decode("utf-8").strip()

    resp = json.loads(data)
    logging.info("Respuesta recibida del servidor")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(resp, f, ensure_ascii=False, indent=2)
        logging.info("Respuesta guardada en %s", args.output)
    else:
        print(json.dumps(resp, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
