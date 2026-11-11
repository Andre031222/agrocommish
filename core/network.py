import socket
import urllib.parse

_LAN_PREFIXES = ("192.168.", "10.", "127.") + tuple(f"172.{n}." for n in range(16, 32))


def ip_local() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def puerto_abierto(host: str, puerto: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, puerto), timeout=timeout):
            return True
    except OSError:
        return False


def es_lan(host: str) -> bool:
    return host == "localhost" or host.startswith(_LAN_PREFIXES)


def api_base_local(server_url: str) -> str:
    parsed = urllib.parse.urlparse(server_url)
    if not parsed.scheme or not parsed.netloc:
        return "http://localhost:5000"
    puerto = parsed.port or (443 if parsed.scheme == "https" else 80)
    if es_lan(parsed.hostname or "") and puerto_abierto("localhost", puerto, timeout=1.0):
        return f"{parsed.scheme}://localhost:{puerto}"
    return f"{parsed.scheme}://{parsed.netloc}"


def clave_wifi_valida(clave: str, segura: "bool | None") -> bool:
    largo_wpa = 8 <= len(clave) <= 63
    if segura is None:
        return clave == "" or largo_wpa
    return largo_wpa if segura else clave == ""
