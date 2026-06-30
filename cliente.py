import socket
import getpass
import requests
import time

# CONFIGURAÇÃO CRÍTICA: Insira aqui o IP do computador que está rodando o servidor.py
URL_SERVIDOR = "http://172.30.0.250:5000/api/logon"

def interceptar_e_transmitir():
    try:
        nome_notebook = socket.gethostname().upper()
        usuario_atual = getpass.getuser()
    except Exception:
        return

    payload = {
        "notebook": nome_notebook,
        "usuario": usuario_atual
    }
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "GENI-Core-Secure-Heartbeat/3.0"
    }

    try:
        # Envia de forma silenciosa com timeout curto
        requests.post(URL_SERVIDOR, json=payload, headers=headers, timeout=5)
    except Exception:
        pass

if __name__ == "__main__":
    # Roda o monitoramento infinitamente a cada 5 minutos
    while True:
        interceptar_e_transmitir()
        time.sleep(300)