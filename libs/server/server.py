#-*- coding: utf-8 -*-

"""
Server runtime module.

This module contains the Server class, which manages the game state and handles
client connections, disconnections, and message processing.
"""

# Import built-in modules
from __future__ import annotations
from asyncio import StreamReader, StreamWriter
from os.path import exists
from datetime import datetime, timedelta, timezone as UTC
from contextlib import suppress
import asyncio
import ipaddress
import platform
import subprocess
import ssl
from typing import TYPE_CHECKING, Optional

# Import Third-party modules
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

# Import local modules
from .session import ClientSession
from .handlers import handle_auth
from .handlers import (
    handle_message,
    heartbeat_loop
)
from ..net.protocol import (
    NetworkMessage,
    ErrorMessage,
    CommandMessage
)
from ..net.protocol import decode, ErrorType

try:
    import miniupnpc as _miniupnpc_mod
    _MINIUPNPC_AVAILABLE = True
except ImportError:
    _MINIUPNPC_AVAILABLE = False

if TYPE_CHECKING:
    try:
        import miniupnpc as _miniupnpc_type
    except ImportError:
        pass


# Create Server class
class Server:
    """
    Server class.

    This class manages the game state and handles client connections,
    disconnections, and message processing.
    """
    def __init__(self, host: str, port: int, password: str) -> None:
        self.host = host
        self.port = port
        self.password = password
        self.server = None
        self.heartbeat_task = None

        # clients management
        self.connected_clients: dict[str, ClientSession] = {}

        # tls context
        self.tls_cert: str = "certs/server.crt"
        self.tls_key: str = "certs/server.key"

        # heartbeat management
        self.heartbeat_interval: float = 30.0
        self.heartbeat_timeout: float = 90.0

        # rate limiting
        self.rate_limit_interval: float = 1.0
        self.rate_limit_threshold: int = 5

        # UPnP state
        self._upnp: Optional["_miniupnpc_type.UPnP"] = None  # miniupnpc.UPnP instance if active
        self._upnp_mapped: bool = False

        # server state
        self.is_running: bool = False

    def is_authenticated(self, client_infos: tuple[str, int]) -> bool:
        """
        Check if a client is authenticated.
        """
        return any(session.connection == client_infos for session in self.connected_clients.values())

    def _build_ssl_context(self) -> ssl.SSLContext:
        """
        Build the SSL context for the server.
        This method initializes the SSL context, loads certificates, and prepares
        the server for secure communication.
        """
        if not exists(self.tls_cert) or not exists(self.tls_key):
            self._create_certificates()

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=self.tls_cert, keyfile=self.tls_key)
        return context

    def _create_certificates(self) -> None:
        """
        generate self-signed certificates for the server.
        This method creates a new RSA private key and a self-signed certificate,
        then saves them to the specified file paths.
        """
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COMMON_NAME, "jdr-server"),
            ]
        )

        now = datetime.now(UTC.utc)
        certificate = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=3650))
            .add_extension(
                x509.SubjectAlternativeName(
                    [
                        x509.DNSName("jdr-server"),
                        x509.DNSName("localhost"),
                        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                    ]
                ),
                critical=False,
            )
            .sign(private_key, hashes.SHA256())
        )

        key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
        cert_bytes = certificate.public_bytes(serialization.Encoding.PEM)

        with open(self.tls_key, "wb") as key_path:
            key_path.write(key_bytes)
        with open(self.tls_cert, "wb") as cert_path:
            cert_path.write(cert_bytes)

    def _ensure_firewall_rule(self) -> None:
        """
        Vérifie qu'une règle de pare-feu Windows autorise les connexions entrantes
        sur le port du serveur. Si la règle est absente, tente de la créer.
        N'a aucun effet sur les systèmes non-Windows.
        """
        if platform.system() != "Windows":
            return

        port = str(self.port)
        rule_name = f"JDR-To-Aru Server {port}"

        # Vérifie si notre règle existe déjà (Get-NetFirewallRule ne nécessite pas les droits admin)
        check = subprocess.run(
            [
                "powershell", "-NonInteractive", "-Command",
                f"Get-NetFirewallRule -DisplayName '{rule_name}' -ErrorAction Stop; exit 0"
            ],
            capture_output=True, text=True, check=False
        )
        if check.returncode == 0:
            print(f"[firewall] Règle '{rule_name}' déjà présente.")
            return

        print(f"[firewall] Règle absente pour TCP:{port} — tentative de création...")
        # Tentative directe (si déjà admin)
        result = subprocess.run(
            [
                "powershell", "-NonInteractive", "-Command",
                f"New-NetFirewallRule "
                f"-DisplayName '{rule_name}' "
                f"-Direction Inbound "
                f"-Protocol TCP "
                f"-LocalPort {port} "
                f"-Action Allow "
                f"-Profile Any"
            ],
            capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            print(f"[firewall] Règle '{rule_name}' créée avec succès.")
            return

        # Pas admin : demande d'élévation UAC (Start-Process -Verb RunAs affiche la boîte UAC)
        print("[firewall] Droits insuffisants — demande d'élévation UAC...")
        fw_cmd = (
            f"New-NetFirewallRule "
            f"-DisplayName '{rule_name}' "
            f"-Direction Inbound "
            f"-Protocol TCP "
            f"-LocalPort {port} "
            f"-Action Allow "
            f"-Profile Any"
        )
        # Pas de -NonInteractive ici : nécessaire pour que la boîte UAC s'affiche
        elevated = subprocess.run(
            [
                "powershell", "-Command",
                f"Start-Process powershell -Verb RunAs -Wait "
                f"-ArgumentList '-NonInteractive', '-Command', \"{fw_cmd}\""
            ],
            check=False
        )
        if elevated.returncode == 0:
            print(f"[firewall] Règle '{rule_name}' créée via élévation UAC.")
        else:
            # L'utilisateur a refusé l'UAC ou l'élévation a échoué
            print(
                f"[firewall] Élévation refusée ou échouée. La règle n'a pas été créée.\n"
                f"  Pour l'ajouter manuellement, lance PowerShell en administrateur :\n"
                f"  New-NetFirewallRule -DisplayName '{rule_name}' "
                f"-Direction Inbound -Protocol TCP -LocalPort {port} -Action Allow -Profile Any"
            )

    def _setup_upnp(self) -> None:
        """
        Tente de configurer la redirection de port UPnP sur la box.
        Détecte le CGNAT et avertit si la redirection ne sera pas joignable
        depuis Internet.
        """
        if not _MINIUPNPC_AVAILABLE:
            print("[upnp] miniupnpc non disponible — redirection UPnP ignorée.")
            return

        try:
            import miniupnpc
            u = miniupnpc.UPnP()
            u.discoverdelay = 2000
            found = u.discover()
            if not found:
                print("[upnp] Aucun appareil UPnP/IGD trouvé — redirection ignorée.")
                return

            u.selectigd()
            upnp_ext_ip = u.externalipaddress()

            # Détection CGNAT : l'IP externe de la box est dans un espace privé
            cgnat_ranges = [
                ipaddress.ip_network("10.0.0.0/8"),
                ipaddress.ip_network("100.64.0.0/10"),  # RFC 6598 (CGNAT)
                ipaddress.ip_network("172.16.0.0/12"),
                ipaddress.ip_network("192.168.0.0/16"),
            ]
            try:
                ext_addr = ipaddress.ip_address(upnp_ext_ip)
                behind_cgnat = any(ext_addr in r for r in cgnat_ranges)
            except ValueError:
                behind_cgnat = True

            result = u.addportmapping(
                self.port, "TCP", u.lanaddr, self.port,
                "JDR-To-Aru", ""
            )
            if result:
                self._upnp = u
                self._upnp_mapped = True
                if behind_cgnat:
                    print(
                        f"[upnp] Mapping TCP:{self.port} ajouté sur la box ({u.lanaddr} → {self.port}).\n"
                        f"[upnp] ATTENTION : ton FAI utilise le CGNAT "
                        f"(IP box={upnp_ext_ip}, non joignable depuis Internet).\n"
                        f"[upnp] Les joueurs externes ne pourront probablement pas se connecter "
                        f"sans un serveur relay."
                    )
                else:
                    print(
                        f"[upnp] Mapping TCP:{self.port} ajouté → joignable sur {upnp_ext_ip}:{self.port}"
                    )
            else:
                print("[upnp] La box a refusé le mapping UPnP.")

        except (OSError, RuntimeError, ValueError) as exc:
            print(f"[upnp] Erreur lors de la configuration UPnP : {exc}")

    def _teardown_upnp(self) -> None:
        """
        Supprime le mapping UPnP créé au démarrage.
        """
        if not self._upnp_mapped or self._upnp is None:
            return
        try:
            self._upnp.deleteportmapping(self.port, "TCP")
            print(f"[upnp] Mapping TCP:{self.port} supprimé.")
        except (OSError, RuntimeError) as exc:
            print(f"[upnp] Erreur lors de la suppression du mapping : {exc}")
        finally:
            self._upnp_mapped = False

    async def setup(self) -> None:
        """
        Setup the server.
        This method initializes the server state and prepares it to accept client connections.
        """
        self.is_running = True
        # Vérifie / crée la règle de pare-feu Windows
        self._ensure_firewall_rule()
        # Tente la redirection de port UPnP
        self._setup_upnp()
        # Create TLS context, load certificates, etc...
        ssl_context = self._build_ssl_context()

        # Start the server
        self.server = await asyncio.start_server(
            self.handle_connection,
            self.host,
            self.port,
            ssl=ssl_context
        )
        print(f"Server started on {self.host}:{self.port}")
        # Start the heartbeat loop
        self.heartbeat_task = asyncio.create_task(heartbeat_loop(self))

    async def handle_connection(self, reader: StreamReader, writer: StreamWriter) -> None:
        """
        Handle an incoming client connection.
        This method is called for each new client connection and manages the authentication
        and message processing for that client.
        """
        client_infos = writer.get_extra_info("peername")
        print(f"[connect] peer={client_infos} stage=connected")

        while self.is_running:
            try:
                raw_message = await reader.readline()
                if not raw_message:
                    break  # Client disconnected
                try:
                    message = decode(raw_message)
                except ValueError as exc:
                    await self.send_error(writer, ErrorType.ENCODING, str(exc))
                    continue

                if isinstance(message, CommandMessage) and message.command == "AUTH":
                    auth_username = str(message.args.get("username", ""))
                    result = await handle_auth(self, client_infos, reader, writer, **message.args)
                    if not result:
                        continue  # Authentication failed, wait for next message
                    else:
                        print(
                            f"[connect] peer={client_infos} username={auth_username!r} "
                            f"stage=authenticated"
                        )
                        read_task = asyncio.create_task(
                            handle_message(
                                self,
                                self.connected_clients[auth_username]
                            )
                        )

                        pending, done = await asyncio.wait(
                            [read_task],
                            return_when=asyncio.FIRST_EXCEPTION
                        )
                        for task in done:
                            if task.exception():
                                print(
                                    f"[connect] peer={client_infos} username={auth_username!r} "
                                    f"stage=session-error detail={task.exception()}"
                                )
                                self.connected_clients.pop(auth_username, None)

                        for task in pending:
                            task.cancel()
                            with suppress(asyncio.CancelledError):
                                await task

                        writer.close()
                        with suppress(Exception):
                            await writer.wait_closed()

                        self.connected_clients.pop(auth_username, None)
                        print(
                            f"[connect] peer={client_infos} username={auth_username!r} "
                            f"stage=closed active_clients={len(self.connected_clients)}"
                        )

                        break  # Exit the loop to start handling authenticated messages

            except (ConnectionError, OSError, RuntimeError) as exc:
                print(f"[connect] peer={client_infos} stage=error detail={exc}")
                break

    async def send_error(
            self,
            writer: asyncio.StreamWriter,
            error_type: ErrorType,
            reason: str
        ) -> None:
        """
        Send an error message to the specified client.
        This method constructs an error message based on the provided error type and reason,
        and sends it to the client identified by `writer`.
        """
        error_message = ErrorMessage(error_type=error_type, reason=reason)
        try:
            writer.write(error_message.encode() + b"\n")
            await writer.drain()
        except (ConnectionError, OSError, RuntimeError) as exc:
            print(f"Error sending error message: {exc}")
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()

    async def send_message(self, writer: asyncio.StreamWriter, message: NetworkMessage) -> None:
        """
        Send a message to the specified client.
        This method encodes the provided `message` and sends
        it to the client identified by `writer`.
        """
        try:
            writer.write(message.encode() + b"\n")
            await writer.drain()
        except (ConnectionError, OSError, RuntimeError) as exc:
            print(f"Error sending error message: {exc}")
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()

    async def shutdown(self) -> None:
        """
        Shutdown the server.
        This method gracefully shuts down the server, closing all client connections
        and releasing resources.
        """
        self.is_running = False
        self._teardown_upnp()
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
            print("Server shutdown complete")
        if self.heartbeat_task is not None:
            self.heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.heartbeat_task
