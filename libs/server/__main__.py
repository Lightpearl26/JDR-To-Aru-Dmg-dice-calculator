# -*- coding: utf-8 -*-

"""
Entry point for the libs/server module.

Usage (depuis le dossier v2/) :
    python -m libs.server --host 0.0.0.0 --port 7799 --password ROOM42
"""

import argparse
import asyncio
from asyncio.subprocess import Process as AsyncioProcess
import os
from pathlib import Path
from typing import Optional

from .server import Server

# Dossier racine du projet (parent de v2/)
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


async def _relay_log_loop(process: AsyncioProcess) -> None:
    """
    Affiche la sortie du tunnel relay VPS tant que le process tourne.
    """
    if process.stdout is None:
        return

    while True:
        line = await process.stdout.readline()
        if not line:
            break
        message = line.decode(errors="replace").rstrip()
        if message:
            print(f"[relay] {message}")


async def start_vps_relay(args: argparse.Namespace) -> tuple[Optional[AsyncioProcess], Optional[asyncio.Task[None]]]:
    """
    Démarre un tunnel SSH inverse vers un VPS et exécute socat à distance.

    Prérequis:
    - accès SSH non interactif (clé SSH ou agent)
    - socat installé sur le VPS
    """
    if not args.relay_host:
        return None, None

    # Phase 1: Pré-nettoyage des vieux processus sur le VPS
    print("[relay] Nettoyage préalable des vieux processus sur le VPS...")
    cleanup_cmd = [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-p", str(args.relay_ssh_port),
    ]
    if args.relay_key_file:
        cleanup_cmd.extend(["-i", args.relay_key_file])
    
    cleanup_cmd.extend([
        f"{args.relay_user}@{args.relay_host}",
        f"pkill -f 'socat.*{args.relay_public_port}' 2>/dev/null || true; sleep 1",
    ])
    
    try:
        cleanup_proc = await asyncio.create_subprocess_exec(
            *cleanup_cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await cleanup_proc.wait()
    except Exception as exc:
        print(f"[relay] ⚠ Avertissement lors du pré-nettoyage: {exc}")
        # On continue même en cas d'erreur

    # Phase 2: Lancer le tunnel SSH inverse + socat
    ssh_command = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "ServerAliveInterval=30",
        "-o",
        "ServerAliveCountMax=3",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-p",
        str(args.relay_ssh_port),
    ]

    if args.relay_key_file:
        ssh_command.extend(["-i", args.relay_key_file])

    ssh_command.extend(
        [
            "-R",
            f"127.0.0.1:{args.relay_tunnel_port}:127.0.0.1:{args.port}",
            f"{args.relay_user}@{args.relay_host}",
            (
                "sh -lc "
                f"\"command -v socat >/dev/null 2>&1 || {{ echo socat manquant sur le VPS; exit 127; }}; "
                f"exec socat TCP-LISTEN:{args.relay_public_port},fork,reuseaddr TCP:127.0.0.1:{args.relay_tunnel_port}\""
            ),
        ]
    )

    print(
        f"[relay] Démarrage du relay VPS sur {args.relay_user}@{args.relay_host} "
        f"(public:{args.relay_public_port} -> local:{args.port})"
    )

    process = await asyncio.create_subprocess_exec(
        *ssh_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    log_task = asyncio.create_task(_relay_log_loop(process))

    await asyncio.sleep(2.0)
    if process.returncode is not None:
        await log_task
        raise RuntimeError(
            "Le relay VPS a échoué au démarrage. Vérifie la clé SSH et la présence de socat sur le VPS."
        )

    print(f"[relay] VPS exposé sur {args.relay_host}:{args.relay_public_port}")
    return process, log_task


async def stop_vps_relay(
    process: Optional[AsyncioProcess],
    log_task: Optional[asyncio.Task[None]],
    args: Optional[argparse.Namespace] = None,
) -> None:
    """
    Arrête proprement le relay VPS lancé par start_vps_relay.
    - d'abord tue les processus socat sur le VPS
    - puis ferme le tunnel SSH local
    """
    if process is None:
        return

    # Étape 1: Nettoyage du socat sur le VPS
    if args and args.relay_host:
        print("[relay] Nettoyage des processus socat sur le VPS...")
        kill_socat_cmd = [
            "ssh",
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=accept-new",
            "-p", str(args.relay_ssh_port),
        ]
        if args.relay_key_file:
            kill_socat_cmd.extend(["-i", args.relay_key_file])
        
        # Tue les socat écoutant sur le port public du relay
        kill_socat_cmd.extend([
            f"{args.relay_user}@{args.relay_host}",
            f"pkill -f 'socat.*{args.relay_public_port}' || true",
        ])
        
        try:
            kill_proc = await asyncio.create_subprocess_exec(
                *kill_socat_cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await kill_proc.wait()
            print("[relay] Processus socat arrêtés sur le VPS")
        except Exception as exc:
            print(f"[relay] ⚠ Erreur lors du nettoyage du socat: {exc}")

    # Étape 2: Fermeture du tunnel SSH local
    if process.returncode is None:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()

    if log_task is not None:
        try:
            await log_task
        except asyncio.CancelledError:
            pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="JDR-To-Aru – libs server")
    parser.add_argument("--host", default="0.0.0.0", help="Adresse d'écoute (défaut: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=7799, help="Port TCP (défaut: 7799)")
    parser.add_argument("--password", default="ROOM42", help="Code secret de session (room code)")
    parser.add_argument("--relay-host", default="", help="Hôte VPS pour exposer le serveur publiquement")
    parser.add_argument("--relay-user", default="root", help="Utilisateur SSH du VPS")
    parser.add_argument("--relay-ssh-port", type=int, default=22, help="Port SSH du VPS")
    parser.add_argument("--relay-public-port", type=int, default=7799, help="Port public exposé sur le VPS")
    parser.add_argument("--relay-tunnel-port", type=int, default=17799, help="Port loopback utilisé sur le VPS pour le tunnel inverse")
    parser.add_argument("--relay-key-file", default="", help="Chemin vers la clé SSH privée à utiliser pour le relay")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    # S'assure que les chemins relatifs (certs/) pointent toujours vers la racine du projet
    os.chdir(_PROJECT_ROOT)
    server = Server(host=args.host, port=args.port, password=args.password)
    await server.setup()
    print(f"[libs.server] En écoute sur {args.host}:{args.port} | password={args.password!r}")

    relay_process: Optional[AsyncioProcess] = None
    relay_log_task: Optional[asyncio.Task[None]] = None

    if args.relay_host:
        try:
            relay_process, relay_log_task = await start_vps_relay(args)
        except RuntimeError as exc:
            print(f"[relay] {exc}")
    
    try:
        await asyncio.get_running_loop().create_future()  # attend indéfiniment
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await stop_vps_relay(relay_process, relay_log_task, args)
        await server.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
