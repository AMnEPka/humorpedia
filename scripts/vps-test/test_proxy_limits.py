#!/usr/bin/env python3
"""Exercise VPS nginx body limits with isolated local Docker fixtures."""

import argparse
import http.client
import re
import secrets
import ssl
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NGINX_IMAGE = "nginx:1.28-alpine"
PREVIEW_PATH = "/api/page-packages/preview"
OTHER_API_PATH = "/api/limits-probe"
SERVER_SOURCE = r'''from http.server import BaseHTTPRequestHandler, HTTPServer

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        remaining = int(self.headers.get("Content-Length", "0"))
        received = remaining
        while remaining:
            chunk = self.rfile.read(min(1024 * 1024, remaining))
            if not chunk:
                return
            remaining -= len(chunk)
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.send_header("X-Fixture-Received", str(received))
        self.end_headers()

    def log_message(self, *_args):
        pass

HTTPServer(("0.0.0.0", 8001), Handler).serve_forever()
'''


def docker(args, *, check=True):
    result = subprocess.run(["docker", *map(str, args)], capture_output=True, text=True)
    if check and result.returncode:
        details = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"docker {' '.join(map(str, args[:4]))} failed: {details}")
    return result


def write_zip_of_exact_size(path, size):
    def write_zip(destination, payload_size):
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
            info = zipfile.ZipInfo("payload.bin", date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.file_size = payload_size
            with archive.open(info, "w") as member:
                block = b"0" * (1024 * 1024)
                remaining = payload_size
                while remaining:
                    chunk = block[:min(len(block), remaining)]
                    member.write(chunk)
                    remaining -= len(chunk)

    empty_path = path.with_name(path.stem + "-empty.zip")
    write_zip(empty_path, 0)
    overhead = empty_path.stat().st_size
    empty_path.unlink()
    if size <= overhead:
        raise ValueError("ZIP fixture size is too small")
    write_zip(path, size - overhead)
    if path.stat().st_size != size:
        raise RuntimeError(f"Could not build an exact {size}-byte ZIP fixture")


def prepare_fixture_configs(directory):
    internal = (ROOT / "scripts/vps-test/nginx.conf").read_text(encoding="utf-8")
    if internal.count("listen 80;") != 1:
        raise RuntimeError("Expected one internal nginx listen 80 directive")
    internal = internal.replace("listen 80;", "listen 8080;", 1)

    public = (ROOT / "scripts/vps-test/https-public.conf").read_text(encoding="utf-8")
    substitutions = {
        "/etc/letsencrypt/live/humorpedia-vps-ip/fullchain.pem": "/fixtures/tls.crt",
        "/etc/letsencrypt/live/humorpedia-vps-ip/privkey.pem": "/fixtures/tls.key",
    }
    for source, replacement in substitutions.items():
        if public.count(source) != 1:
            raise RuntimeError(f"Expected one fixture certificate path: {source}")
        public = public.replace(source, replacement, 1)

    (directory / "00-internal.conf").write_text(internal, encoding="utf-8", newline="\n")
    (directory / "10-public.conf").write_text(public, encoding="utf-8", newline="\n")
    snippets = directory / "snippets"
    snippets.mkdir()
    (snippets / "humorpedia-proxy.conf").write_text(
        (ROOT / "scripts/vps-test/https-proxy.conf").read_text(encoding="utf-8"),
        encoding="utf-8",
        newline="\n",
    )


def mount_arg(source, target, *, readonly=False):
    option = f"type=bind,source={Path(source).resolve()},target={target}"
    if readonly:
        option += ",readonly"
    return option


def read_status(sock, *, skip_informational=False):
    stream = sock.makefile("rb")
    while True:
        line = stream.readline(65537)
        if not line or len(line) > 65536:
            stream.close()
            raise RuntimeError("nginx closed the connection before returning HTTP status")
        try:
            _version, status_text, _reason = line.decode("iso-8859-1").rstrip("\r\n").split(" ", 2)
            status = int(status_text)
        except (ValueError, TypeError) as error:
            stream.close()
            raise RuntimeError(f"Invalid HTTP status line: {line!r}") from error
        while True:
            header = stream.readline(65537)
            if not header or len(header) > 65536:
                stream.close()
                raise RuntimeError("Malformed HTTP response headers")
            if header in (b"\r\n", b"\n"):
                break
        if not (skip_informational and 100 <= status < 200 and status != 101):
            stream.close()
            return status


def open_connection(host, port, *, tls):
    connection = http.client.HTTPSConnection(
        host, port, timeout=120, context=ssl._create_unverified_context()
    ) if tls else http.client.HTTPConnection(host, port, timeout=120)
    connection.connect()
    return connection


def request_multipart(host, port, path, zip_path, *, tls=True):
    boundary = "----humorpedia-fixture-" + secrets.token_hex(12)
    prefix = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="fixture.zip"\r\n'
        "Content-Type: application/zip\r\n\r\n"
    ).encode("ascii")
    suffix = f"\r\n--{boundary}--\r\n".encode("ascii")
    content_length = len(prefix) + zip_path.stat().st_size + len(suffix)
    connection = open_connection(host, port, tls=tls)
    try:
        connection.putrequest("POST", path, skip_host=True, skip_accept_encoding=True)
        connection.putheader("Host", "127.0.0.1")
        connection.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")
        connection.putheader("Content-Length", str(content_length))
        connection.putheader("Expect", "100-continue")
        connection.putheader("Connection", "close")
        connection.endheaders()
        status = read_status(connection.sock)
        if status != 100:
            return status

        try:
            connection.send(prefix)
            with zip_path.open("rb") as payload:
                while chunk := payload.read(1024 * 1024):
                    connection.send(chunk)
            connection.send(suffix)
        except OSError:
            # An over-limit response may close while a body is being sent.
            return read_status(connection.sock, skip_informational=True)
        return read_status(connection.sock, skip_informational=True)
    finally:
        connection.close()


def request_health(host, port, *, tls):
    connection = open_connection(host, port, tls=tls)
    try:
        connection.request("GET", "/api/health", headers={"Host": "127.0.0.1", "Connection": "close"})
        response = connection.getresponse()
        response.read()
        return response.status
    finally:
        connection.close()


def wait_for_health(host, port, *, tls, timeout=45):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            if request_health(host, port, tls=tls) == 200:
                return
        except (OSError, http.client.HTTPException) as error:
            last_error = error
        time.sleep(0.25)
    raise RuntimeError(f"Fixture HTTP upstream did not become ready: {last_error}")


def wait_for_backend_container(name, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = docker([
            "exec", name, "python", "-c",
            "import socket; s=socket.create_connection(('127.0.0.1',8001),timeout=1); s.close()",
        ], check=False)
        if result.returncode == 0:
            return
        time.sleep(0.25)
    raise RuntimeError(f"Fixture backend did not listen on port 8001: {result.stderr.strip()}")


def expect_status(label, actual, expected):
    if actual != expected:
        raise AssertionError(f"{label}: expected HTTP {expected}, got {actual}")
    print(f"PASS {label}: HTTP {actual}")


def run_checks(backend_image):
    token = secrets.token_hex(6)
    network = f"proxy-limit-test-{token}"
    backend_name = f"proxy-limit-backend-{token}"
    nginx_name = f"proxy-limit-nginx-{token}"
    with tempfile.TemporaryDirectory(prefix="humorpedia-proxy-limits-") as temp_name:
        temp = Path(temp_name)
        config_dir = temp / "conf.d"
        config_dir.mkdir()
        prepare_fixture_configs(config_dir)
        (temp / "server.py").write_text(SERVER_SOURCE, encoding="utf-8", newline="\n")

        network_created = False
        try:
            docker(["image", "inspect", backend_image])
            docker(["image", "inspect", NGINX_IMAGE])
            network_created = True
            docker(["network", "create", network])

            docker([
                "run", "--pull=never", "--rm", "--network", "none", "--entrypoint", "openssl",
                "--mount", mount_arg(temp, "/fixtures"), backend_image,
                "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                "-keyout", "/fixtures/tls.key", "-out", "/fixtures/tls.crt",
                "-subj", "/CN=127.0.0.1",
            ])

            docker([
                "run", "--pull=never", "--detach", "--name", backend_name, "--network", network,
                "--network-alias", "backend", "--log-driver", "none", "--entrypoint", "python",
                backend_image, "-u", "-c", SERVER_SOURCE,
            ])
            wait_for_backend_container(backend_name)

            common_mounts = [
                "--mount", mount_arg(config_dir, "/etc/nginx/conf.d", readonly=True),
                "--mount", mount_arg(config_dir / "snippets", "/etc/nginx/snippets", readonly=True),
                "--mount", mount_arg(temp, "/fixtures", readonly=True),
            ]
            docker([
                "run", "--pull=never", "--rm", "--network", network,
                *common_mounts, "--entrypoint", "nginx", NGINX_IMAGE, "-t",
            ])

            docker([
                "run", "--pull=never", "--detach", "--name", nginx_name, "--network", network,
                "--publish", "127.0.0.1::443", "--publish", "127.0.0.1::8080",
                *common_mounts, "--entrypoint", "nginx", NGINX_IMAGE, "-g", "daemon off;",
            ])

            public_port = int(re.search(r"127\.0\.0\.1:(\d+)", docker(["port", nginx_name, "443/tcp"]).stdout).group(1))
            internal_port = int(re.search(r"127\.0\.0\.1:(\d+)", docker(["port", nginx_name, "8080/tcp"]).stdout).group(1))
            docker(["exec", nginx_name, "nginx", "-t"])
            wait_for_health("127.0.0.1", internal_port, tls=False)
            wait_for_health("127.0.0.1", public_port, tls=True)

            zip_50 = temp / "fixture-50m.zip"
            zip_52_plus = temp / "fixture-52m-plus.zip"
            zip_20_plus = temp / "fixture-20m-plus.zip"
            write_zip_of_exact_size(zip_50, 50 * 1024 * 1024)
            write_zip_of_exact_size(zip_52_plus, 52 * 1024 * 1024 + 1)
            write_zip_of_exact_size(zip_20_plus, 20 * 1024 * 1024 + 1)

            expect_status("50 MiB ZIP through public HTTPS + internal nginx", request_multipart("127.0.0.1", public_port, PREVIEW_PATH, zip_50), 200)
            expect_status("50 MiB ZIP through internal nginx", request_multipart("127.0.0.1", internal_port, PREVIEW_PATH, zip_50, tls=False), 200)
            expect_status("52 MiB + 1 ZIP preview through public HTTPS", request_multipart("127.0.0.1", public_port, PREVIEW_PATH, zip_52_plus), 413)
            expect_status("52 MiB + 1 ZIP preview through internal nginx", request_multipart("127.0.0.1", internal_port, PREVIEW_PATH, zip_52_plus, tls=False), 413)
            expect_status("over-20 MiB ZIP on other API through public HTTPS", request_multipart("127.0.0.1", public_port, OTHER_API_PATH, zip_20_plus), 413)
            expect_status("over-20 MiB ZIP on other API through internal nginx", request_multipart("127.0.0.1", internal_port, OTHER_API_PATH, zip_20_plus, tls=False), 413)
        finally:
            cleanup_errors = []
            for name in (nginx_name, backend_name):
                result = docker(["rm", "--force", name], check=False)
                if result.returncode and "no such container" not in result.stderr.lower():
                    cleanup_errors.append(("container", name, result.stderr.strip()))
            if network_created:
                result = docker(["network", "rm", network], check=False)
                error = result.stderr.lower()
                if result.returncode and "no such network" not in error and "not found" not in error:
                    cleanup_errors.append(("network", network, result.stderr.strip()))
            if cleanup_errors:
                message = "; ".join(f"{kind} {name}: {error}" for kind, name, error in cleanup_errors)
                if sys.exc_info()[0] is None:
                    raise RuntimeError(f"Fixture cleanup failed: {message}")
                print(f"WARNING: fixture cleanup failed: {message}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend-image",
        required=True,
        help="Already-local backend image containing python and openssl (no image pull is attempted)",
    )
    args = parser.parse_args()
    run_checks(args.backend_image)


if __name__ == "__main__":
    main()
