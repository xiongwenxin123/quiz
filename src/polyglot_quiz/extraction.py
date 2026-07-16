from __future__ import annotations

import ipaddress
import re
import socket
import time
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

from .models import ArticleDocument, ArticleParagraph, Sentence, TargetLanguage
from .observability import log_event


class ExtractionError(RuntimeError):
    pass


class UnsafeUrlError(ExtractionError):
    pass


_BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "br",
    "div",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "li",
    "main",
    "nav",
    "p",
    "section",
    "table",
    "tr",
}
_SKIP_TAGS = {"script", "style", "svg", "noscript", "nav", "footer", "form"}


class _ReadableTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if tag in _BLOCK_TAGS and self._skip_depth == 0:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if tag in _BLOCK_TAGS and self._skip_depth == 0:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth or not data.strip():
            return
        if self._in_title:
            self.title_parts.append(data.strip())
        else:
            self.parts.append(data)


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[\t \u00a0]+", " ", line).strip() for line in text.splitlines()]
    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines:
        if line:
            current.append(line)
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs)


def _paragraphs_from_trafilatura_xml(xml_text: str) -> tuple[str, str | None]:
    root = ET.fromstring(xml_text)
    main = root.find("main")
    if main is None:
        raise ValueError("Trafilatura XML has no main element")

    paragraphs = [
        re.sub(r"\s+", " ", "".join(element.itertext())).strip()
        for element in main.findall(".//p")
    ]
    paragraphs = [paragraph for paragraph in paragraphs if paragraph]
    if not paragraphs:
        raise ValueError("Trafilatura XML has no article paragraphs")

    heading = main.find("head")
    title = None
    if heading is not None:
        title = re.sub(r"\s+", " ", "".join(heading.itertext())).strip() or None
    return "\n\n".join(paragraphs), title


def split_sentences(text: str, language: TargetLanguage) -> list[Sentence]:
    if language == TargetLanguage.JAPANESE:
        chunks = re.split(r"(?<=[。！？])\s*|\n+", text)
    else:
        chunks = re.split(r"(?<=[.!?])\s+|\n+", text)
    cleaned = [chunk.strip() for chunk in chunks if chunk and chunk.strip()]
    return [Sentence(id=f"s{index}", text=value) for index, value in enumerate(cleaned, 1)]


def _token_count(text: str, language: TargetLanguage) -> int:
    if language == TargetLanguage.JAPANESE:
        return len(re.findall(r"[\u3040-\u30ff\u3400-\u9fff]+|[A-Za-z0-9]+", text))
    return len(re.findall(r"\b[\w'\u00c0-\u024f-]+\b", text, flags=re.UNICODE))


def document_from_text(
    text: str,
    language: TargetLanguage,
    *,
    title: str | None = None,
    source_url: str | None = None,
    extraction_method: str = "direct_text",
) -> ArticleDocument:
    normalized = normalize_text(text)
    if len(normalized) < 80:
        raise ExtractionError("The extracted article is too short (minimum 80 characters)")
    sentences: list[Sentence] = []
    paragraphs: list[ArticleParagraph] = []
    for paragraph_index, paragraph_text in enumerate(normalized.split("\n\n"), 1):
        local_sentences = split_sentences(paragraph_text, language)
        paragraph_sentence_ids: list[str] = []
        for local_sentence in local_sentences:
            sentence = Sentence(id=f"s{len(sentences) + 1}", text=local_sentence.text)
            sentences.append(sentence)
            paragraph_sentence_ids.append(sentence.id)
        if paragraph_sentence_ids:
            paragraphs.append(
                ArticleParagraph(
                    id=f"p{paragraph_index}",
                    text=paragraph_text,
                    sentence_ids=paragraph_sentence_ids,
                )
            )
    if not sentences:
        raise ExtractionError("No sentences could be extracted")
    return ArticleDocument(
        title=title,
        source_url=source_url,
        language=language,
        text=normalized,
        sentences=sentences,
        paragraphs=paragraphs,
        word_or_token_count=_token_count(normalized, language),
        extraction_method=extraction_method,
    )


def _validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeUrlError("Only public HTTP(S) URLs are supported")
    if parsed.username or parsed.password:
        raise UnsafeUrlError("URLs containing credentials are not allowed")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ExtractionError(f"Cannot resolve URL host: {parsed.hostname}") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise UnsafeUrlError(f"URL resolves to a non-public address: {ip}")


def _download_html(url: str, max_bytes: int, timeout_seconds: float) -> tuple[str, str]:
    current = url
    headers = {"User-Agent": "PolyglotQuiz/0.1 (+article extraction)"}
    with httpx.Client(timeout=timeout_seconds, headers=headers, follow_redirects=False) as client:
        for _ in range(6):
            _validate_public_url(current)
            with client.stream("GET", current) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise ExtractionError("Redirect response has no Location header")
                    current = urljoin(current, location)
                    continue
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if "html" not in content_type.lower():
                    raise ExtractionError(f"URL did not return HTML: {content_type or 'unknown'}")
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise ExtractionError(f"HTML exceeds the {max_bytes}-byte limit")
                    chunks.append(chunk)
                encoding = response.encoding or "utf-8"
                return b"".join(chunks).decode(encoding, errors="replace"), current
    raise ExtractionError("Too many redirects")


def extract_url(
    url: str,
    language: TargetLanguage,
    *,
    max_bytes: int = 3_000_000,
    timeout_seconds: float = 15,
) -> ArticleDocument:
    last_error: httpx.HTTPError | None = None
    for attempt in range(1, 4):
        try:
            html, final_url = _download_html(url, max_bytes, timeout_seconds)
            break
        except httpx.HTTPError as exc:
            last_error = exc
            log_event(
                "url_download_retry",
                log_level=30,
                attempt=attempt,
                max_attempts=3,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            if attempt < 3:
                time.sleep(0.4 * attempt)
    else:
        raise ExtractionError(f"URL download failed after 3 attempts: {last_error}") from last_error
    title: str | None = None
    method = "html_parser_fallback"
    text: str | None = None
    try:
        import trafilatura  # type: ignore[import-not-found]

        extracted_xml = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
            output_format="xml",
        )
        if extracted_xml:
            text, title = _paragraphs_from_trafilatura_xml(extracted_xml)
            method = "trafilatura_xml"
    except (ImportError, ET.ParseError, ValueError):
        pass
    if not text:
        parser = _ReadableTextParser()
        parser.feed(html)
        text = "".join(parser.parts)
        title = normalize_text(" ".join(parser.title_parts)) or None
    return document_from_text(
        text,
        language,
        title=title,
        source_url=final_url,
        extraction_method=method,
    )
