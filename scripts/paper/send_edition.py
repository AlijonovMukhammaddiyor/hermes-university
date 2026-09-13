#!/usr/bin/env python3
"""Put the printed edition in the reader's Telegram.

The agent has no file-sending tool, so the skill could not "attach the PDF" however
it was asked to — the paper was being printed into a directory nobody opens. This
posts it with the Bot API directly.

Credentials come from config.env, which already holds them. The document goes to
TELEGRAM_HOME_CHANNEL when set (the group the digests go to), else the first id in
TELEGRAM_ALLOWED_USERS.

Standard library only; the multipart body is assembled by hand rather than pulling
in requests for one upload.

Usage:
    send_edition.py <pdf> [--caption TEXT] [--env PATH] [--chat ID]
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import urllib.error
import urllib.request
import uuid
from pathlib import Path

API = "https://api.telegram.org"
TIMEOUT = 120
# Telegram refuses a document over 50 MB from a bot.
MAX_BYTES = 50 * 1024 * 1024


def read_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise SystemExit(f"no config at {path}")
    out = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def multipart(fields: dict[str, str], file_field: str, path: Path) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    sep = f"--{boundary}".encode()
    body = bytearray()
    for key, value in fields.items():
        body += sep + b"\r\n"
        body += f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
        body += str(value).encode() + b"\r\n"
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    body += sep + b"\r\n"
    body += (f'Content-Disposition: form-data; name="{file_field}"; '
             f'filename="{path.name}"\r\n').encode()
    body += f"Content-Type: {mime}\r\n\r\n".encode()
    body += path.read_bytes() + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def send(pdf: Path, token: str, chat: str, caption: str) -> dict:
    size = pdf.stat().st_size
    if size > MAX_BYTES:
        raise SystemExit(f"{pdf.name} is {size // 1024 // 1024} MB; Telegram's bot limit is 50 MB")

    body, content_type = multipart(
        # Plain text: the caption carries figures and dashes that HTML parsing trips on.
        {"chat_id": chat, "caption": caption[:1024], "disable_notification": "false"},
        "document", pdf,
    )
    request = urllib.request.Request(f"{API}/bot{token}/sendDocument", data=body,
                                     headers={"Content-Type": content_type})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        raise SystemExit(f"Telegram refused the upload ({exc.code}): {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(f"Telegram unreachable: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--caption", default=None)
    parser.add_argument("--env", type=Path, default=Path("/root/hermes-university/config.env"))
    parser.add_argument("--chat", default=None)
    args = parser.parse_args(argv)

    pdf = args.pdf.expanduser()
    if not pdf.is_file():
        raise SystemExit(f"no edition at {pdf}")

    env = read_env(args.env.expanduser())
    token = env.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set")
    chat = (args.chat or env.get("TELEGRAM_HOME_CHANNEL")
            or (env.get("TELEGRAM_ALLOWED_USERS") or "").split(",")[0].strip())
    if not chat:
        raise SystemExit("no chat id: set TELEGRAM_HOME_CHANNEL or TELEGRAM_ALLOWED_USERS")

    caption = args.caption or f"The Builder's Daily — {pdf.stem}"
    result = send(pdf, token, chat, caption)
    if not result.get("ok"):
        raise SystemExit(f"Telegram returned: {json.dumps(result)[:300]}")
    print(f"sent {pdf.name} ({pdf.stat().st_size // 1024} KB) to {chat}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
