import socket
import threading
import json
import uuid
import logging

class DynamoSingleton:
    _instance = None

    def __new__(cls, use_aws=False):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.use_aws = use_aws
            if use_aws:
                import boto3
                cls._instance.dynamodb = boto3.resource('dynamodb')
                cls._instance.corporate_data = cls._instance.dynamodb.Table('CorporateData')
                cls._instance.corporate_log = cls._instance.dynamodb.Table('CorporateLog')
            else:
                cls._instance.corporate_data = {}
                cls._instance.corporate_log = []
        return cls._instance

class DynamoProxy:
    def __init__(self, singleton_instance):
        self.db = singleton_instance
        self.observers = []

    def get(self, record_id, uuid_cliente=None):
        if isinstance(self.db.corporate_data, dict):
            record = self.db.corporate_data.get(record_id)
        else:
            response = self.db.corporate_data.get_item(Key={'id': record_id})
            record = response.get('Item')
        self.log_action('get', record_id, uuid_cliente)
        return record

    def list(self, uuid_cliente=None):
        if isinstance(self.db.corporate_data, dict):
            records = list(self.db.corporate_data.values())
        else:
            response = self.db.corporate_data.scan()
            records = response.get('Items', [])
        self.log_action('list', None, uuid_cliente)
        return records

    def set(self, record_id, data, uuid_cliente=None):
        if isinstance(self.db.corporate_data, dict):
            self.db.corporate_data[record_id] = data
        else:
            self.db.corporate_data.put_item(Item={'id': record_id, **data})
        self.log_action('set', record_id, uuid_cliente)
        self.notify_observers({'ACTION':'update','id':record_id,'data':data})
        return True

    def log_action(self, action, record_id, uuid_cliente=None):
        log_entry = {'idlog': str(uuid.uuid4()),'uuid': uuid_cliente,'accion': action,'record_id': record_id,'timestamp': str(uuid.uuid1())}
        if isinstance(self.db.corporate_log, list):
            self.db.corporate_log.append(log_entry)
        else:
            self.db.corporate_log.put_item(Item=log_entry)

        logging.info("Nuevo log registrado: acción=%s uuid=%s id=%s", action, uuid_cliente, record_id)

    def add_observer(self, conn):
        self.observers.append(conn)

    def remove_observer(self, conn):
        if conn in self.observers:
            self.observers.remove(conn)

    def notify_observers(self, message):
        data = (json.dumps(message)+"\n").encode("utf-8")
        for obs in self.observers[:]:
            try:
                obs.sendall(data)
            except:
                self.observers.remove(obs)

        logging.debug("Notificando a %d observadores: %s", len(self.observers), message)

def handle_client(conn, proxy):
    try:
        buffer = b""
        while True:
            try:
                chunk = conn.recv(4096)
            except ConnectionResetError:
                logging.info("Conexión cerrada abruptamente por el cliente")
                break
            if not chunk:
                break
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n",1)
                if not line.strip():
                    continue
                req = json.loads(line.decode('utf-8'))
                action = req.get('ACTION')
                uuid_cliente = req.get('UUID')
                logging.debug("Acción recibida: %s (UUID=%s)", action, uuid_cliente)

                if action == 'get':
                    record_id = req.get('id')
                    resp = proxy.get(record_id, uuid_cliente)
                elif action == 'list':
                    resp = proxy.list(uuid_cliente)
                elif action == 'set':
                    record_id = req.get('id')
                    data = req.get('data')
                    resp = proxy.set(record_id,data, uuid_cliente)
                elif action == 'subscribe':
                    proxy.add_observer(conn)
                    proxy.log_action('subscribe', None, uuid_cliente)
                    continue
                else:
                    resp = {'error':'acción desconocida'}
                conn.sendall((json.dumps(resp)+"\n").encode('utf-8'))
    finally:
        proxy.remove_observer(conn)
        conn.close()
        logging.info("Cliente desconectado")

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("-p", "--port", type=int, default=8080)
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='[%(levelname)s] %(message)s'
    )

    HOST = "127.0.0.1"
    PORT = args.port
    singleton = DynamoSingleton(use_aws=False)
    proxy = DynamoProxy(singleton)

    logging.info("Logs actuales al iniciar:")
    for log in proxy.db.corporate_log:
        logging.info(log)

    s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    s.bind((HOST,PORT))
    s.listen(5)
    logging.info("Servidor escuchando en %s:%d", HOST, PORT)

    while True:
        conn, addr = s.accept()
        logging.info("Nueva conexión desde %s", addr)
        t = threading.Thread(target=handle_client,args=(conn,proxy),daemon=True)
        t.start()

if __name__=="__main__":
    main()
