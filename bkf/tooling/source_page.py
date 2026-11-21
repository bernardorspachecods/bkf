"""Fetch public web pages and extract source metadata and readable text."""

from __future__ import annotations

import codecs
import ipaddress
import json
import re
import socket
import ssl
import time
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import Future, wait
from contextlib import closing, suppress
from dataclasses import dataclass
from datetime import date
from email.message import Message
from html.parser import HTMLParser
from http.client import HTTPConnection, IncompleteRead
from threading import Thread
from typing import TypeVar
from urllib.error import HTTPError
from urllib.parse import parse_qsl, quote, unquote, urlencode, urljoin, urlsplit, urlunsplit


UNKNOWN = "unknown"
FETCH_TIMEOUT = 20
SOCKET_TIMEOUT = 15
MAX_BODY = 5_000_000
MAX_HTTP_REDIRECTS = 5
HTTP_REDIRECTS = {301, 302, 303, 307, 308}
_T = TypeVar("_T")
KINDS = ("docs", "article", "talk", "package", "standard", "repo", "paper", "thread")
TRACKING_KEYS = {"fbclid", "gclid"}
# Common country-code namespaces and hosted sites where tenants own their URLs.
COUNTRY_NAMESPACES = {"ac", "co", "com", "edu", "gov", "net", "org"}
HOSTED_SUFFIXES = {"appspot.com", "blogspot.com", "github.io", "gitlab.io", "pages.dev",
                   "readthedocs.io", "vercel.app", "wordpress.com"}
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
BYLINE_MARKER = re.compile(r"(?:^|[-_\s])(?:byline|(?:article|entry|post)[-_]+meta)(?:$|[-_\s])")
BLOCKS = {"address", "article", "blockquote", "br", "dd", "div", "dl", "dt", "figcaption",
          "figure", "hr", "li", "main", "ol", "p", "pre", "section", "td", "th", "tr", "ul"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param",
        "source", "track", "wbr"}
HIDDEN = {"nav", "noscript", "script", "style", "svg", "template"}
SCRIPT_TYPES = {"", "module", "application/ecmascript", "application/javascript", "text/ecmascript",
                "text/javascript"}
REFRESH = re.compile(r"\s*\d+(?:\.\d+)?\s*;\s*url\s*=", re.IGNORECASE)
SCRIPT_URL = r"""(?P<url>'[^'\\\r\n]*'|"[^"\\\r\n]*")"""
SCRIPT_REDIRECTS = (
    re.compile(rf"\s*(?:window\s*\.\s*)?location\s*\.\s*replace\s*\(\s*{SCRIPT_URL}\s*\)\s*(?:;\s*)?"),
    re.compile(rf"\s*(?:(?:window\s*\.\s*)?location\s*\.\s*href|window\s*\.\s*location)"
               rf"\s*=\s*{SCRIPT_URL}\s*(?:;\s*)?"),
)
ARTICLE_TYPES = {"article", "blogposting", "newsarticle", "report", "scholarlyarticle",
                 "techarticle", "apireference", "discussionforumposting", "softwareapplication",
                 "softwaresourcecode", "videoobject", "presentationdigitaldocument", "legislation"}
KIND_BY_TYPE = {
    "apireference": "docs", "techarticle": "docs", "discussionforumposting": "thread",
    "scholarlyarticle": "paper", "softwaresourcecode": "repo", "softwareapplication": "package",
    "videoobject": "talk", "presentationdigitaldocument": "talk", "legislation": "standard",
}


ZERO_WIDTH = str.maketrans("", "", "\u200b\u200c\u200d\u2060\ufeff")
INVALID_URL_CHARS = r'\s\x00-\x20\x7f-\x9f<>"{}|\\^`'
SNAPSHOT_HEADER = "<!-- BKF:SNAPSHOT:1 -->"
SNAPSHOT_HEADING = "## "
HTML_WHITESPACE = "\t\n\f\r "
HTML_SPACE_RUN = re.compile(rf"[{HTML_WHITESPACE}]+")
# WHATWG labels grouped by the Python codec used to decode them.
# https://encoding.spec.whatwg.org/encodings.json
HTML_ENCODINGS = {
    label: codec
    for codec, labels in {
        "utf-8": "unicode-1-1-utf-8 unicode11utf8 unicode20utf8 utf-8 utf8 x-unicode20utf8",
        "cp866": "866 cp866 csibm866 ibm866",
        "iso-8859-2": "csisolatin2 iso-8859-2 iso-ir-101 iso8859-2 iso88592 iso_8859-2 iso_8859-2:1987 l2 "
                      "latin2",
        "iso-8859-3": "csisolatin3 iso-8859-3 iso-ir-109 iso8859-3 iso88593 iso_8859-3 iso_8859-3:1988 l3 "
                      "latin3",
        "iso-8859-4": "csisolatin4 iso-8859-4 iso-ir-110 iso8859-4 iso88594 iso_8859-4 iso_8859-4:1988 l4 "
                      "latin4",
        "iso-8859-5": "csisolatincyrillic cyrillic iso-8859-5 iso-ir-144 iso8859-5 iso88595 iso_8859-5 "
                      "iso_8859-5:1988",
        "iso-8859-6": "arabic asmo-708 csiso88596e csiso88596i csisolatinarabic ecma-114 iso-8859-6 "
                      "iso-8859-6-e iso-8859-6-i iso-ir-127 iso8859-6 iso88596 iso_8859-6 iso_8859-6:1987",
        "iso-8859-7": "csisolatingreek ecma-118 elot_928 greek greek8 iso-8859-7 iso-ir-126 iso8859-7 iso88597 "
                      "iso_8859-7 iso_8859-7:1987 sun_eu_greek",
        "iso-8859-8": "csiso88598e csisolatinhebrew hebrew iso-8859-8 iso-8859-8-e iso-ir-138 iso8859-8 "
                      "iso88598 iso_8859-8 iso_8859-8:1988 visual csiso88598i iso-8859-8-i logical",
        "iso-8859-10": "csisolatin6 iso-8859-10 iso-ir-157 iso8859-10 iso885910 l6 latin6",
        "iso-8859-13": "iso-8859-13 iso8859-13 iso885913",
        "iso-8859-14": "iso-8859-14 iso8859-14 iso885914",
        "iso-8859-15": "csisolatin9 iso-8859-15 iso8859-15 iso885915 iso_8859-15 l9",
        "iso-8859-16": "iso-8859-16",
        "koi8-r": "cskoi8r koi koi8 koi8-r koi8_r",
        "koi8-u": "koi8-ru koi8-u",
        "mac_roman": "csmacintosh mac macintosh x-mac-roman",
        "cp874": "dos-874 iso-8859-11 iso8859-11 iso885911 tis-620 windows-874",
        "windows-1250": "cp1250 windows-1250 x-cp1250",
        "windows-1251": "cp1251 windows-1251 x-cp1251",
        "windows-1252": "ansi_x3.4-1968 ascii cp1252 cp819 csisolatin1 ibm819 iso-8859-1 iso-ir-100 iso8859-1 "
                        "iso88591 iso_8859-1 iso_8859-1:1987 l1 latin1 us-ascii windows-1252 x-cp1252",
        "windows-1253": "cp1253 windows-1253 x-cp1253",
        "windows-1254": "cp1254 csisolatin5 iso-8859-9 iso-ir-148 iso8859-9 iso88599 iso_8859-9 "
                        "iso_8859-9:1989 l5 latin5 windows-1254 x-cp1254",
        "windows-1255": "cp1255 windows-1255 x-cp1255",
        "windows-1256": "cp1256 windows-1256 x-cp1256",
        "windows-1257": "cp1257 windows-1257 x-cp1257",
        "windows-1258": "cp1258 windows-1258 x-cp1258",
        "mac_cyrillic": "x-mac-cyrillic x-mac-ukrainian",
        "gb18030": "chinese csgb2312 csiso58gb231280 gb2312 gb_2312 gb_2312-80 gbk iso-ir-58 x-gbk gb18030",
        "big5hkscs": "big5 big5-hkscs cn-big5 csbig5 x-x-big5",
        "euc-jp": "cseucpkdfmtjapanese euc-jp x-euc-jp",
        "iso-2022-jp": "csiso2022jp iso-2022-jp",
        "cp932": "csshiftjis ms932 ms_kanji shift-jis shift_jis sjis windows-31j x-sjis",
        "cp949": "cseuckr csksc56011987 euc-kr iso-ir-149 korean ks_c_5601-1987 ks_c_5601-1989 ksc5601 "
                 "ksc_5601 windows-949",
        "replacement": "csiso2022kr hz-gb-2312 iso-2022-cn iso-2022-cn-ext iso-2022-kr replacement",
        "utf-16be": "unicodefffe utf-16be",
        "utf-16le": "csunicode iso-10646-ucs-2 ucs-2 unicode unicodefeff utf-16 utf-16le",
        "x-user-defined": "x-user-defined",
    }.items()
    for label in labels.split()
}
USER_DEFINED_CHARACTERS = "".join(map(chr, (*range(0x80), *range(0xF780, 0xF800))))


def clean(value: object) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""


def clean_heading(value: str) -> str:
    return clean(value.translate(ZERO_WIDTH))


def encode_snapshot(lines: Iterable[tuple[str, bool]], *, marked: bool = False) -> str:
    """Serialize lines with a flag for each extracted heading, always marked when `marked`."""
    encoded = []
    escaped = marked
    for line, heading in lines:
        if heading:
            line = SNAPSHOT_HEADING + line
        elif line.startswith((SNAPSHOT_HEADING, "\\")) or (
            not encoded and line.rstrip("\r\n") == SNAPSHOT_HEADER
        ):
            line = "\\" + line
            escaped = True
        encoded.append(line)
    return (SNAPSHOT_HEADER + "\n" if escaped else "") + "".join(encoded)


URL_ESCAPES = {ord(char): f"%{ord(char):02X}" for char in ' "<>`{}|^'}


def encode_url(url: str) -> str:
    """Strip a URL and percent-encode the characters a browser encodes after its authority."""
    url = url.strip()
    match = re.match(r"[A-Za-z][A-Za-z0-9+.-]*://[^/?#]*", url)
    if match is None:
        return url
    return match.group() + url[match.end():].translate(URL_ESCAPES)


def normalize_url(url: str) -> str:
    """Return the store's identity key for an HTTP(S) URL."""
    if re.search(rf"[{INVALID_URL_CHARS}]", url):
        raise ValueError("URL contains a character that must be percent-encoded")
    parts = urlsplit(url)
    host = parts.hostname
    if parts.scheme not in {"http", "https"} or not host or parts.username is not None:
        raise ValueError("expected an HTTP(S) URL without credentials")
    if "%" in host:
        raise ValueError("invalid hostname")
    if parts.netloc.startswith("[") and not re.fullmatch(r"\[[^\]]+\](?::[0-9]*)?", parts.netloc):
        raise ValueError("invalid bracketed hostname")
    host = host.rstrip(".").removeprefix("www.")
    if not host:
        raise ValueError("expected a hostname")
    host = f"[{host}]" if ":" in host else host
    port = parts.port
    if port is not None and (parts.scheme, port) not in {("http", 80), ("https", 443)}:
        host = f"{host}:{port}"
    query = sorted(
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_KEYS and not key.lower().startswith(("utm_", "mc_"))
    )
    fragment = parts.fragment if parts.fragment.startswith(("/", "!/")) else ""
    return urlunsplit(("https", host, parts.path.rstrip("/") or "/", urlencode(query), fragment))


def site_domain(url: str) -> str:
    host = urlsplit(url).hostname or ""
    host = host.rstrip(".")
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        pass
    labels = host.split(".")
    suffix = ".".join(labels[-2:])
    has_two_label_suffix = suffix in HOSTED_SUFFIXES or (
        len(labels) >= 2 and len(labels[-1]) == 2 and labels[-2] in COUNTRY_NAMESPACES
    )
    return ".".join(labels[-(3 if has_two_label_suffix else 2):])


def site_name(url: str) -> str:
    domain = site_domain(url)
    try:
        ipaddress.ip_address(domain)
    except ValueError:
        return domain.partition(".")[0]
    return domain


def repository_owner(url: str) -> str:
    parts = urlsplit(url)
    host = (parts.hostname or "").rstrip(".").removeprefix("www.")
    segments = parts.path.strip("/").split("/")
    if host not in {"github.com", "gitlab.com"} or len(segments) < 2 or not all(segments[:2]):
        return ""
    owner = unquote(segments[0])
    if owner.casefold() in {"-", "explore", "groups", "orgs", "search", "topics", "users"}:
        return ""
    return owner


def iso_date(value: object) -> str:
    text = clean(value)
    match = re.match(r"^(\d{4})([-/])(\d{1,2})\2(\d{1,2})(?:$|[Tt ])", text)
    if match:
        try:
            return date(int(match[1]), int(match[3]), int(match[4])).isoformat()
        except ValueError:
            pass
    return ""


@dataclass(frozen=True)
class FetchedPage:
    url: str
    html: str | None
    lossy: bool = False


class FetchError(OSError):
    """The raw page could not be fetched within the network boundary or limits."""


class FetchBudget:
    def __init__(self) -> None:
        self.deadline = time.monotonic() + FETCH_TIMEOUT
        self.http_redirects = 0
        self.socket: socket.socket | None = None

    def remaining(self) -> float:
        seconds = self.deadline - time.monotonic()
        if seconds <= 0:
            raise FetchError("fetch deadline exceeded")
        return seconds

    def track_socket(self, connection: socket.socket) -> None:
        self.socket = connection
        connection.settimeout(min(SOCKET_TIMEOUT, self.remaining()))

    def run(self, work: Callable[[], _T]) -> _T:
        # DNS and buffered HTTP reads can block beyond a socket inactivity
        # timeout. Return on the absolute deadline and interrupt the active I/O.
        result: Future[_T] = Future()

        def execute() -> None:
            try:
                result.set_result(work())
            except Exception as exc:
                result.set_exception(exc)

        Thread(target=execute, daemon=True).start()
        done, _ = wait([result], timeout=max(0, self.deadline - time.monotonic()))
        if done and time.monotonic() < self.deadline:
            return result.result()
        if (connection := self.socket) is not None:
            with suppress(OSError):
                connection.shutdown(socket.SHUT_RDWR)
            with suppress(OSError):
                connection.close()
        raise FetchError("fetch deadline exceeded")


def _public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        elif ip.is_site_local or ip.sixtofour is not None:
            return False
    return ip.is_global and not (
        ip.is_loopback or ip.is_private or ip.is_link_local
        or ip.is_multicast or ip.is_reserved or ip.is_unspecified
    )


def _connect(host: str, port: int, budget: FetchBudget) -> socket.socket:
    budget.remaining()
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
    budget.remaining()
    if not addresses:
        raise FetchError(f"no addresses found for {host}")
    for family, _, _, _, endpoint in addresses:
        if family not in {socket.AF_INET, socket.AF_INET6} or not _public_address(endpoint[0]):
            raise FetchError(f"refused non-public address {endpoint[0]} for {host}")
    last_error = None
    for family, socktype, protocol, _, endpoint in addresses:
        budget.remaining()
        connection = socket.socket(family, socktype, protocol)
        try:
            budget.track_socket(connection)
            # Use the checked numeric endpoint. The HTTP Host header and TLS
            # certificate still use the original hostname.
            connection.connect(endpoint)
        except OSError as exc:
            connection.close()
            last_error = exc
        else:
            return connection
    raise FetchError(f"connection to {host} failed: {last_error}")


def _html_encoding(label: str | None) -> str | None:
    if label and label.isascii():
        return HTML_ENCODINGS.get(label.strip(HTML_WHITESPACE).lower())
    return None


class _CharsetParser(HTMLParser):
    encoding: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta" or self.encoding:
            return
        attributes = dict(attrs)
        encoding = _html_encoding(attributes.get("charset"))
        if encoding is None and (attributes.get("http-equiv") or "").strip().lower() == "content-type":
            header = Message()
            header["Content-Type"] = attributes.get("content") or ""
            encoding = _html_encoding(header.get_content_charset())
        if encoding in {"utf-16le", "utf-16be"}:
            encoding = "utf-8"
        elif encoding == "x-user-defined":
            encoding = "windows-1252"
        self.encoding = encoding


def _encoding(data: bytearray, http_charset: str | None) -> str:
    for markers, encoding in (
        ((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE), "utf-32"),
        ((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE), "utf-16"),
        ((codecs.BOM_UTF8,), "utf-8-sig"),
    ):
        if data.startswith(markers):
            return encoding
    if encoding := _html_encoding(http_charset):
        return encoding
    parser = _CharsetParser()
    parser.feed(data.decode("latin-1"))
    return parser.encoding or "utf-8"


def _decode(data: bytearray, http_charset: str | None) -> tuple[str, bool]:
    encoding = _encoding(data, http_charset)
    if encoding == "replacement":
        return ("\ufffd", True) if data else ("", False)
    if encoding == "x-user-defined":
        return codecs.charmap_decode(data, "strict", USER_DEFINED_CHARACTERS)[0], False
    try:
        return data.decode(encoding), False
    except UnicodeError:
        return data.decode(encoding, errors="replace"), True


def _fetch_http(url: str, budget: FetchBudget) -> FetchedPage:
    while True:
        budget.remaining()
        normalize_url(url)
        parts = urlsplit(url)
        host = parts.hostname.encode("idna").decode("ascii")
        secure = parts.scheme == "https"
        port = parts.port if parts.port is not None else (443 if secure else 80)
        target = quote(urlunsplit(("", "", parts.path or "/", parts.query, "")), safe="/%?&=:+;,@!$'()*[]")
        with closing(HTTPConnection(host, port)) as connection:
            connection.sock = _connect(host, port, budget)
            if secure:
                context = ssl.create_default_context()
                context.set_alpn_protocols(["http/1.1"])
                connection.sock = context.wrap_socket(
                    connection.sock, server_hostname=host, do_handshake_on_connect=False,
                )
                budget.track_socket(connection.sock)
                connection.sock.do_handshake()
            budget.track_socket(connection.sock)
            # The socket must always be the one installed above.
            connection.auto_open = False
            authority = f"[{host}]" if ":" in host else host
            if port != (443 if secure else 80):
                authority = f"{authority}:{port}"
            connection.request("GET", target, headers={
                "Host": authority, "User-Agent": "BKF Sources", "Connection": "close",
            })
            with connection.getresponse() as response:
                if response.status in HTTP_REDIRECTS and (location := response.getheader("Location")):
                    if budget.http_redirects >= MAX_HTTP_REDIRECTS:
                        raise FetchError(f"exceeded {MAX_HTTP_REDIRECTS} HTTP redirects")
                    budget.http_redirects += 1
                    url = urljoin(url, location)
                    continue
                if not 200 <= response.status < 300:
                    raise HTTPError(url, response.status, response.reason, response.headers, None)
                if response.headers.get_content_type() not in {"text/html", "application/xhtml+xml"}:
                    return FetchedPage(url, None)
                if response.length is not None and response.length > MAX_BODY:
                    raise FetchError("response body exceeds 5 MB")
                data = bytearray()
                while chunk := response.read(min(65_536, MAX_BODY + 1 - len(data))):
                    if len(data) + len(chunk) > MAX_BODY:
                        raise FetchError("response body exceeds 5 MB")
                    data.extend(chunk)
                    budget.remaining()
                if response.length:
                    raise IncompleteRead(data, response.length)
                html, lossy = _decode(data, response.headers.get_content_charset())
                return FetchedPage(url, html, lossy)


def fetch_page(url: str, *, budget: FetchBudget | None = None) -> FetchedPage:
    if budget is not None:
        return _fetch_http(url, budget)
    budget = FetchBudget()
    return budget.run(lambda: _fetch_http(url, budget))


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, list[str]] = {}
        self.canonicals: list[str] = []
        self.redirects: list[str] = []
        self.title: list[str] = []
        self.json_ld: list[str] = []
        self.lines: list[tuple[str, bool]] = []
        self.published_time = ""
        self.byline_time = ""
        self._elements: list[tuple[str, bool]] = []
        self._line: list[str] = []
        self._hidden: list[str] = []
        self._script: list[str] | None = None
        self._script_type = ""
        self._heading = ""
        self._in_head = False
        self._in_title = False

    def _flush(self) -> None:
        text = "".join(self._line)
        line = clean_heading(text) if self._heading else clean(text)
        if line:
            self.lines.append((line + "\n", bool(self._heading)))
        self._line.clear()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._hidden:
            if tag not in VOID:
                self._hidden.append(tag)
            return
        attributes = dict(attrs)
        if tag in HIDDEN or attributes.get("role") == "navigation" or "hidden" in attributes:
            if tag not in VOID:
                self._hidden.append(tag)
            media_type = (attributes.get("type") or "").partition(";")[0].strip().lower()
            if tag == "script" and (media_type == "application/ld+json"
                                    or (media_type in SCRIPT_TYPES and "src" not in attributes)):
                self._script = []
                self._script_type = media_type
        elif tag == "head":
            self._in_head = True
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            if (attributes.get("http-equiv") or "").strip().lower() == "refresh":
                content = attributes.get("content") or ""
                if match := REFRESH.match(content):
                    target = content[match.end():].strip()
                    if "\n" not in target:
                        if len(target) >= 2 and target[0] in "\"'" and target[-1] == target[0]:
                            target = target[1:-1].strip()
                        self.redirects.append(target)
            name = (attributes.get("property") or attributes.get("name") or "").strip().lower()
            content = clean(attributes.get("content"))
            if name and content:
                self.meta.setdefault(name, []).append(content)
        elif tag == "link":
            if "canonical" in (attributes.get("rel") or "").lower().split():
                href = (attributes.get("href") or "").strip()
                if href:
                    self.canonicals.append(href)
        elif not self._in_head:
            in_byline = bool(self._elements and self._elements[-1][1])
            marker = f"{attributes.get('class') or ''} {attributes.get('id') or ''}".lower()
            if tag == "time" and (day := iso_date(attributes.get("datetime"))):
                classes = (attributes.get("class") or "").lower()
                itemprop = (attributes.get("itemprop") or "").lower()
                properties = HTML_SPACE_RUN.split(itemprop)
                if "published" in HTML_SPACE_RUN.split(classes) or "datepublished" in properties:
                    self.published_time = self.published_time or day
                elif (in_byline and not {"datemodified", "startdate", "enddate"}.intersection(properties)
                      and "published" not in itemprop
                      and not any(marker in classes for marker in ("updated", "modified", "published"))):
                    self.byline_time = self.byline_time or day
            if tag not in VOID:
                self._elements.append((tag, in_byline or bool(BYLINE_MARKER.search(marker))))
            if tag in HEADINGS:
                self._flush()
                self._heading = tag
            elif tag in BLOCKS:
                if self._heading:
                    self._line.append(" ")
                else:
                    self._flush()

    def handle_endtag(self, tag: str) -> None:
        if self._hidden:
            if tag == "script" and self._script is not None:
                script = "".join(self._script)
                self._script = None
                if self._script_type == "application/ld+json":
                    self.json_ld.append(script)
                else:
                    # Recognize a standalone literal redirect without interpreting JavaScript.
                    for pattern in SCRIPT_REDIRECTS:
                        if match := pattern.fullmatch(script):
                            self.redirects.append(match["url"][1:-1])
                            break
            if tag in self._hidden:
                while self._hidden.pop() != tag:
                    pass
        elif tag == "head":
            self._in_head = False
        elif tag == "title":
            self._in_title = False
        elif not self._in_head:
            for index in range(len(self._elements) - 1, -1, -1):
                if self._elements[index][0] == tag:
                    del self._elements[index:]
                    break
            if tag == self._heading or tag in BLOCKS and not self._heading:
                self._flush()
                self._heading = ""

    def handle_data(self, data: str) -> None:
        if self._script is not None:
            self._script.append(data)
        elif self._hidden:
            return
        elif self._in_title:
            self.title.append(data)
        elif not self._in_head:
            self._line.append(data)

    def close(self) -> None:
        super().close()
        self._flush()


def _nodes(value: object):
    if isinstance(value, list):
        for item in value:
            yield from _nodes(item)
    elif isinstance(value, dict):
        yield value
        yield from _nodes(value.get("@graph"))


def _types(node: dict) -> list[str]:
    values = node.get("@type", [])
    if not isinstance(values, list):
        values = [values]
    return [value.rstrip("/").rsplit("/", 1)[-1].lower() for value in values if isinstance(value, str)]


def _names(value: object, by_id: dict[str, dict]):
    values = value if isinstance(value, list) else [value]
    for item in values:
        if isinstance(item, dict):
            ref = item.get("@id")
            if not clean(item.get("name")) and isinstance(ref, str):
                item = by_id.get(ref, item)
            name = clean(item.get("name"))
            types = _types(item)
            person = "person" in types if types else None
        else:
            name, person = clean(item), None
        if name and name.casefold() != UNKNOWN:
            yield name, person


def _page_nodes(parser: PageParser) -> tuple[list[dict], list[dict]]:
    nodes = []
    for raw in parser.json_ld:
        try:
            nodes.extend(_nodes(json.loads(raw)))
        except (ValueError, RecursionError):
            continue
    # Site, breadcrumb and author nodes often precede the main article in an @graph.
    context_types = {"breadcrumblist", "organization", "person", "website", "imageobject",
                     "corporation", "publisher"}
    content = [node for node in nodes if set(_types(node)).isdisjoint(context_types)]
    content.sort(key=lambda node: (
        not bool(ARTICLE_TYPES.intersection(_types(node))),
        not bool({"headline", "datePublished", "dateModified", "author"}.intersection(node)),
    ))
    return content, nodes


@dataclass(frozen=True)
class PageDetails:
    url: str
    title: str
    author: str
    person: bool | None
    published: str
    updated: str
    json_types: tuple[str, ...]
    snapshot: str
    site: str = ""
    client_redirect: str | None = None
    published_from: str | None = None
    first_author: str | None = None


def _web_links(url: str, links: list[str]) -> Iterator[str]:
    for link in links:
        if not link:
            continue
        try:
            candidate = urljoin(url, link)
            normalize_url(candidate)
        except ValueError:
            continue
        yield candidate


def extract_page(page: FetchedPage) -> PageDetails:
    parser = PageParser()
    parser.feed(page.html or "")
    parser.close()
    content, nodes = _page_nodes(parser)
    by_id = {node["@id"]: node for node in nodes
             if isinstance(node.get("@id"), str) and clean(node.get("name"))}

    def meta(*keys: str):
        for key in keys:
            yield from parser.meta.get(key, [])

    url = next((candidate for candidate in _web_links(page.url, parser.canonicals)
                if site_domain(candidate) == site_domain(page.url)), page.url)

    title = next(
        (text for node in content for key in ("headline", "name") if (text := clean(node.get(key)))),
        "",
    ) or next(meta("og:title", "citation_title"), "") or clean("".join(parser.title))
    names = next((names for node in content if (names := list(_names(node.get("author"), by_id)))), [])
    site = next((name for name in meta("og:site_name") if name.casefold() != UNKNOWN), "")
    publisher = next(
        (name for node in nodes for name, _ in _names(node.get("publisher"), by_id)), "",
    ) or next((name for name in meta("publisher", "citation_publisher")
               if name.casefold() != UNKNOWN), "") or site or next(
        (name for node in nodes if {"website", "organization", "corporation"}.intersection(_types(node))
         and (name := clean(node.get("name"))) and name.casefold() != UNKNOWN),
        "",
    )
    if not names:
        names = next((names for key in ("author", "citation_author")
                      if (names := [(name, None) for name in meta(key) if name.casefold() != UNKNOWN])), [])
    first, person = names[0] if names else ("", None)
    author = ", ".join(name for name, _ in names)
    domain_label = site_name(url)
    owner = repository_owner(url)
    if owner and person is not True and author.casefold() in {"", domain_label}:
        author, person = owner, False
    elif not author:
        author = publisher or domain_label
        person = False
    elif person is None and first.casefold() == publisher.casefold():
        person = False

    def extract_date(key: str, *meta_keys: str) -> str:
        values = [node.get(key) for node in content]
        values.extend(meta(*meta_keys))
        return next((parsed for value in values if (parsed := iso_date(value))), "")

    published = extract_date("datePublished", "article:published_time", "citation_publication_date",
                             "citation_date", "citation_online_date")
    published = published or parser.published_time or parser.byline_time
    published_from = None
    if not published:
        path_dates = re.findall(r"/([0-9]{4}/[0-9]{2}/[0-9]{2})(?=/)", urlsplit(url).path)
        published = next((parsed for value in path_dates if (parsed := iso_date(value))), "")
        if published:
            published_from = "url"

    return PageDetails(
        url, title or UNKNOWN, author or UNKNOWN, person, published or UNKNOWN,
        extract_date("dateModified", "article:modified_time", "citation_modified_date",
                     "citation_last_modified_date", "citation_update_date") or UNKNOWN,
        tuple(value for node in content for value in _types(node)),
        encode_snapshot(parser.lines),
        site or publisher,
        next(_web_links(page.url, parser.redirects), None),
        published_from=published_from,
        first_author=first if len(names) > 1 else None,
    )


def infer_kind(url: str, json_types: tuple[str, ...]) -> str:
    parts = urlsplit(url)
    host = (parts.hostname or "").removeprefix("www.")
    domain = site_domain(url)
    if domain in {"github.com", "gitlab.com", "bitbucket.org", "codeberg.org"}:
        return "repo"
    if domain in {"npmjs.com", "pypi.org", "crates.io", "rubygems.org", "packagist.org"}:
        return "package"
    if host.startswith("docs.") or "docs" in parts.path.lower().split("/"):
        return "docs"
    return next((KIND_BY_TYPE[value] for value in json_types if value in KIND_BY_TYPE), "article")
