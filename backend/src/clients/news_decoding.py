"""Decode source responses while bounding wire and expanded body sizes."""

import zlib

import httpx

from src.exceptions.news_sources import NewsSourceError

_CHUNK_BYTES = 16384
_MAX_GZIP_MEMBERS = 32


def _invalid_encoding() -> NewsSourceError:
    return NewsSourceError(
        "content_encoding", "Источник вернул неподдерживаемый или повреждённый сжатый документ.",
    )


def _too_large() -> NewsSourceError:
    return NewsSourceError("response_too_large", "Документ превышает допустимый размер.")


async def read_news_body(response: httpx.Response, max_bytes: int) -> bytes:
    """Read a complete identity, gzip or deflate body within both size limits.

    Compressed responses use raw iteration: HTTPX's automatic decoding does
    not bound allocations by the expanded size. Every zlib call instead has
    an output limit, including a single sentinel byte to detect overflow.
    """
    encoding = response.headers.get("content-encoding", "identity").strip().lower()
    if encoding not in {"identity", "gzip", "x-gzip", "deflate"}:
        raise _invalid_encoding()
    size_header = response.headers.get("content-length", "").strip().lstrip("0")
    limit = str(max_bytes)
    if size_header.isascii() and size_header.isdigit() and (
        len(size_header) > len(limit)
        or (len(size_header) == len(limit) and size_header > limit)
    ):
        raise _too_large()

    is_gzip = encoding in {"gzip", "x-gzip"}
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS) if is_gzip else None
    prefix = b""
    members = 1
    downloaded = expanded = 0
    parts: list[bytes] = []
    # Identity has no automatic decompression and also supports pre-read
    # responses supplied by in-memory transports.
    chunks = (
        response.aiter_bytes(chunk_size=_CHUNK_BYTES)
        if encoding == "identity" else response.aiter_raw(chunk_size=_CHUNK_BYTES)
    )
    async for data in chunks:
        downloaded += len(data)
        if downloaded > max_bytes:
            raise _too_large()
        if encoding == "identity":
            parts.append(data)
            continue
        if decoder is None:
            data = prefix + data
            if len(data) < 2:
                prefix = data
                continue
            # Some HTTP servers send raw DEFLATE instead of the zlib wrapper.
            # Select by its header; never retry corrupt wrapped data as raw.
            wrapped = (
                data[0] & 15 == 8 and data[0] >> 4 <= 7
                and int.from_bytes(data[:2], "big") % 31 == 0
            )
            decoder = zlib.decompressobj(zlib.MAX_WBITS if wrapped else -zlib.MAX_WBITS)
        while data:
            if decoder.eof:
                if not is_gzip or members >= _MAX_GZIP_MEMBERS:
                    raise _invalid_encoding()
                decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
                members += 1
            try:
                decoded = decoder.decompress(data, max_bytes - expanded + 1)
            except zlib.error:
                raise _invalid_encoding() from None
            expanded += len(decoded)
            if expanded > max_bytes:
                raise _too_large()
            if decoded:
                parts.append(decoded)
            data = decoder.unused_data if decoder.eof else decoder.unconsumed_tail
    # flush() only accepts an initial allocation size, not a hard output cap.
    # eof confirms both the end marker and checksum without an unbounded flush.
    if encoding != "identity" and (decoder is None or not decoder.eof):
        raise _invalid_encoding()
    return b"".join(parts)
