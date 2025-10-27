import socket
import threading
import json
import uuid

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

    def get(self, record_id):
        if isinstance(self.db.corporate_data, dict):
            record = self.db.corporate_data.get(record_id)
        else:
            response = self.db.corporate_data.get_item(Key={'id': record_id})
            record = response.get('Item')
        self.log_action('get', record_id)
        return record

    def list(self):
        if isinstance(self.db.corporate_data, dict):
            records = list(self.db.corporate_data.values())
        else:
            response = self.db.corporate_data.scan()
            records = response.get('Items', [])
        self.log_action('list', None)
        return records

    def set(self, record_id, data):
        if isinstance(self.db.corporate_data, dict):
            self.db.corporate_data[record_id] = data
        else:
            self.db.corporate_data.put_item(Item={'id': record_id, **data})
        self.log_action('set', record_id)
        self.notify_observers({'ACTION':'update','id':record_id,'data':data})
        return True

    def log_action(self, action, record_id):
        log_entry = {'idlog': str(uuid.uuid4()),'accion': action,'record_id': record_id,'timestamp': str(uuid.uuid1())}
        if isinstance(self.db.corporate_log, list):
            self.db.corporate_log.append(log_entry)
        else:
            self.db.corporate_log.put_item(Item=log_entry)

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

def handle_client(conn, proxy):
    try:
        buffer = b""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n",1)
                if not line.strip():
                    continue
                req = json.loads(line.decode('utf-8'))
                action = req.get('ACTION')
                if action == 'get':
                    record_id = req.get('id')
                    resp = proxy.get(record_id)
                elif action == 'list':
                    resp = proxy.list()
                elif action == 'set':
                    record_id = req.get('id')
                    data = req.get('data')
                    resp = proxy.set(record_id,data)
                elif action == 'subscribe':
                    proxy.add_observer(conn)
                    continue
                else:
                    resp = {'error':'acción desconocida'}
                conn.sendall((json.dumps(resp)+"\n").encode('utf-8'))
    finally:
        proxy.remove_observer(conn)
        conn.close()

def main():
    HOST = "127.0.0.1"
    PORT = 8080
    singleton = DynamoSingleton(use_aws=True)
    proxy = DynamoProxy(singleton)

    print("Logs actuales al iniciar:")
    for log in proxy.db.corporate_log:
        print(log)

    s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    s.bind((HOST,PORT))
    s.listen(5)
    while True:
        conn, addr = s.accept()
        t = threading.Thread(target=handle_client,args=(conn,proxy),daemon=True)
        t.start()

if __name__=="__main__":
    main()
