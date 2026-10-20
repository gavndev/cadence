from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

from mutagen import File as MutagenFile
from mutagen.flac import FLAC, Picture as FlacPicture
from mutagen.id3 import (
    APIC,
    COMM,
    ID3,
    ID3NoHeaderError,
    TALB,
    TCOM,
    TCON,
    TDRC,
    TIT2,
    TPE1,
    TPE2,
    TPOS,
    TRCK,
    USLT,
)
from mutagen.mp4 import MP4, MP4Cover
from mutagen.wave import WAVE

AUDIO_EXTENSIONS = {
    ".mp3",
    ".flac",
    ".wav",
    ".wave",
    ".m4a",
    ".mp4",
    ".aac",
    ".ogg",
    ".oga",
    ".opus",
    ".wma",
    ".aiff",
    ".aif",
    ".wv",
}

TEXT_FIELDS = (
    "title",
    "artist",
    "album",
    "albumartist",
    "date",
    "genre",
    "tracknumber",
    "discnumber",
    "comment",
    "composer",
    "lyrics",
)

MP4_KEYS = {
    "title": "\xa9nam",
    "artist": "\xa9ART",
    "album": "\xa9alb",
    "albumartist": "aART",
    "date": "\xa9day",
    "genre": "\xa9gen",
    "tracknumber": "trkn",
    "discnumber": "disk",
    "comment": "\xa9cmt",
    "composer": "\xa9wrt",
    "lyrics": "\xa9lyr",
}

ID3_KEYS = {
    "title": "TIT2",
    "artist": "TPE1",
    "album": "TALB",
    "albumartist": "TPE2",
    "date": "TDRC",
    "genre": "TCON",
    "tracknumber": "TRCK",
    "discnumber": "TPOS",
    "composer": "TCOM",
    "comment": "COMM",
    "lyrics": "USLT",
}

VORBIS_KEYS = {
    "title": "TITLE",
    "artist": "ARTIST",
    "album": "ALBUM",
    "albumartist": "ALBUMARTIST",
    "date": "DATE",
    "genre": "GENRE",
    "tracknumber": "TRACKNUMBER",
    "discnumber": "DISCNUMBER",
    "composer": "COMPOSER",
    "comment": "COMMENT",
    "lyrics": "LYRICS",
}

APE_KEYS = {
    "title": "Title",
    "artist": "Artist",
    "album": "Album",
    "albumartist": "Album Artist",
    "date": "Year",
    "genre": "Genre",
    "tracknumber": "Track",
    "discnumber": "Disc",
    "composer": "Composer",
    "comment": "Comment",
    "lyrics": "Lyrics",
}

WMA_KEYS = {
    "title": "Title",
    "artist": "Author",
    "album": "WM/AlbumTitle",
    "albumartist": "WM/AlbumArtist",
    "date": "WM/Year",
    "genre": "WM/Genre",
    "tracknumber": "WM/TrackNumber",
    "discnumber": "WM/PartOfSet",
    "composer": "WM/Composer",
    "comment": "Description",
    "lyrics": "WM/Lyrics",
}


def tag_keys_for(path: Path) -> dict[str, str]:
    suffix = path.suffix.lower()
    if suffix in {".m4a", ".mp4", ".aac"}:
        return dict(MP4_KEYS)
    if suffix in {".flac", ".ogg", ".oga", ".opus"}:
        return dict(VORBIS_KEYS)
    if suffix == ".wv":
        return dict(APE_KEYS)
    if suffix == ".wma":
        return dict(WMA_KEYS)
    return dict(ID3_KEYS)


def library_root() -> Path:
    from backend.library_config import resolved_library

    path = resolved_library()
    path.mkdir(parents=True, exist_ok=True)
    return path


def encode_file_id(relative_path: str) -> str:
    return base64.urlsafe_b64encode(relative_path.encode("utf-8")).decode("ascii")


def decode_file_id(file_id: str) -> str:
    padded = file_id + "=" * (-len(file_id) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")


def resolve_audio_path(file_id: str) -> Path:
    relative = Path(decode_file_id(file_id))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Invalid file id")
    full = (library_root() / relative).resolve()
    if not str(full).startswith(str(library_root())):
        raise ValueError("Path escapes library")
    if not full.is_file():
        raise FileNotFoundError(relative.as_posix())
    return full


def list_audio_files() -> list[dict[str, Any]]:
    root = library_root()
    results: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        relative = path.relative_to(root).as_posix()
        results.append(
            {
                "id": encode_file_id(relative),
                "name": path.name,
                "relative_path": relative,
                "folder": Path(relative).parent.as_posix() if Path(relative).parent.as_posix() != "." else "",
                "extension": path.suffix.lower().lstrip("."),
                "size": path.stat().st_size,
            }
        )
    return results


def _first_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return _first_text(value[0] if value else "")
    return str(value).strip()


def _easy_get(audio: Any, keys: list[str]) -> str:
    for key in keys:
        if key in audio:
            return _first_text(audio[key])
    return ""


def _mp4_text(audio: MP4, field: str) -> str:
    key = MP4_KEYS[field]
    value = audio.tags.get(key) if audio.tags else None
    if not value:
        return ""
    if field in {"tracknumber", "discnumber"} and isinstance(value[0], tuple):
        current, total = value[0]
        if total:
            return f"{current}/{total}"
        return str(current)
    return _first_text(value)


def _duration(audio: Any) -> float | None:
    info = getattr(audio, "info", None)
    if info is None:
        return None
    length = getattr(info, "length", None)
    return float(length) if length is not None else None


def _bitrate(audio: Any) -> int | None:
    info = getattr(audio, "info", None)
    if info is None:
        return None
    bitrate = getattr(info, "bitrate", None)
    return int(bitrate) if bitrate else None


def _sample_rate(audio: Any) -> int | None:
    info = getattr(audio, "info", None)
    if info is None:
        return None
    rate = getattr(info, "sample_rate", None)
    return int(rate) if rate else None


def _channels(audio: Any) -> int | None:
    info = getattr(audio, "info", None)
    if info is None:
        return None
    channels = getattr(info, "channels", None)
    return int(channels) if channels else None


ID3_FRAMES = {
    "title": TIT2,
    "artist": TPE1,
    "album": TALB,
    "albumartist": TPE2,
    "date": TDRC,
    "genre": TCON,
    "tracknumber": TRCK,
    "discnumber": TPOS,
    "composer": TCOM,
}


def _id3_text(tags: ID3, frame_id: str) -> str:
    frames = tags.getall(frame_id)
    if not frames:
        return ""
    frame = frames[0]
    text = getattr(frame, "text", None)
    if text:
        return _first_text(text)
    return _first_text(getattr(frame, "text", "") or str(frame))


def _read_id3_tags(id3: ID3 | None) -> dict[str, str]:
    if id3 is None:
        return {field: "" for field in TEXT_FIELDS}
    comments = id3.getall("COMM")
    comment = ""
    if comments:
        comment = _first_text(getattr(comments[0], "text", comments[0]))
    lyrics_frames = id3.getall("USLT")
    lyrics = ""
    if lyrics_frames:
        lyrics = str(lyrics_frames[0].text or "")
    return {
        "title": _id3_text(id3, "TIT2"),
        "artist": _id3_text(id3, "TPE1"),
        "album": _id3_text(id3, "TALB"),
        "albumartist": _id3_text(id3, "TPE2"),
        "date": _id3_text(id3, "TDRC") or _id3_text(id3, "TYER"),
        "genre": _id3_text(id3, "TCON"),
        "tracknumber": _id3_text(id3, "TRCK"),
        "discnumber": _id3_text(id3, "TPOS"),
        "comment": comment,
        "composer": _id3_text(id3, "TCOM"),
        "lyrics": lyrics,
    }


def _write_id3_tags(id3: ID3, tags: dict[str, str]) -> None:
    for field, frame_cls in ID3_FRAMES.items():
        id3.delall(frame_cls.__name__)
        value = tags.get(field, "")
        if value:
            id3.add(frame_cls(encoding=3, text=value))

    id3.delall("COMM")
    if tags.get("comment"):
        id3.add(COMM(encoding=3, lang="eng", desc="", text=tags["comment"]))

    id3.delall("USLT")
    if tags.get("lyrics"):
        id3.add(USLT(encoding=3, lang="eng", desc="", text=tags["lyrics"]))


def _read_generic(path: Path) -> dict[str, Any]:
    audio = MutagenFile(path.as_posix(), easy=True)
    if audio is None:
        raise ValueError(f"Unsupported audio file: {path.name}")

    tags = {
        "title": _easy_get(audio, ["title"]),
        "artist": _easy_get(audio, ["artist"]),
        "album": _easy_get(audio, ["album"]),
        "albumartist": _easy_get(audio, ["albumartist"]),
        "date": _easy_get(audio, ["date", "year"]),
        "genre": _easy_get(audio, ["genre"]),
        "tracknumber": _easy_get(audio, ["tracknumber", "track"]),
        "discnumber": _easy_get(audio, ["discnumber", "disc"]),
        "comment": _easy_get(audio, ["comment", "description"]),
        "composer": _easy_get(audio, ["composer"]),
        "lyrics": _easy_get(audio, ["lyrics"]),
    }
    return {
        "tags": tags,
        "duration": _duration(audio),
        "bitrate": _bitrate(audio),
        "sample_rate": _sample_rate(audio),
        "channels": _channels(audio),
        "has_artwork": _has_artwork(path),
    }


def _has_artwork(path: Path) -> bool:
    try:
        data, _mime = extract_artwork(path)
        return bool(data)
    except Exception:
        return False


def read_metadata(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix in {".m4a", ".mp4", ".aac"}:
        audio = MP4(path.as_posix())
        tags = {field: _mp4_text(audio, field) for field in TEXT_FIELDS}
        return {
            "tags": tags,
            "duration": _duration(audio),
            "bitrate": _bitrate(audio),
            "sample_rate": _sample_rate(audio),
            "channels": _channels(audio),
            "has_artwork": bool(audio.tags and audio.tags.get("covr")),
        }
    if suffix in {".wav", ".wave"}:
        audio = WAVE(path.as_posix())
        return {
            "tags": _read_id3_tags(audio.tags),
            "duration": _duration(audio),
            "bitrate": _bitrate(audio),
            "sample_rate": _sample_rate(audio),
            "channels": _channels(audio),
            "has_artwork": _has_artwork(path),
        }
    return _read_generic(path)


def _set_easy(audio: Any, field: str, value: str) -> None:
    aliases = {
        "title": ["title"],
        "artist": ["artist"],
        "album": ["album"],
        "albumartist": ["albumartist"],
        "date": ["date"],
        "genre": ["genre"],
        "tracknumber": ["tracknumber"],
        "discnumber": ["discnumber"],
        "comment": ["comment"],
        "composer": ["composer"],
        "lyrics": ["lyrics"],
    }
    keys = aliases.get(field, [field])
    if not value:
        for key in keys:
            if key in audio:
                del audio[key]
        return
    audio[keys[0]] = value


def _parse_pair(value: str) -> tuple[int, int]:
    if "/" in value:
        left, right = value.split("/", 1)
        return int(left or 0), int(right or 0)
    return int(value or 0), 0


def write_metadata(path: Path, tags: dict[str, str]) -> dict[str, Any]:
    suffix = path.suffix.lower()
    cleaned = {key: (tags.get(key) or "").strip() for key in TEXT_FIELDS}

    if suffix in {".m4a", ".mp4", ".aac"}:
        audio = MP4(path.as_posix())
        if audio.tags is None:
            audio.add_tags()
        for field, value in cleaned.items():
            key = MP4_KEYS[field]
            if not value:
                if key in audio.tags:
                    del audio.tags[key]
                continue
            if field in {"tracknumber", "discnumber"}:
                current, total = _parse_pair(value)
                audio.tags[key] = [(current, total)]
            else:
                audio.tags[key] = [value]
        audio.save()
        return read_metadata(path)

    if suffix in {".wav", ".wave"}:
        audio = WAVE(path.as_posix())
        if audio.tags is None:
            audio.add_tags()
        _write_id3_tags(audio.tags, cleaned)
        audio.save()
        return read_metadata(path)

    audio = MutagenFile(path.as_posix(), easy=True)
    if audio is None:
        raise ValueError(f"Unsupported audio file: {path.name}")
    if audio.tags is None:
        audio.add_tags()
    for field, value in cleaned.items():
        try:
            _set_easy(audio, field, value)
        except Exception:
            continue
    audio.save()
    return read_metadata(path)


def extract_artwork(path: Path) -> tuple[bytes | None, str | None]:
    suffix = path.suffix.lower()

    if suffix in {".m4a", ".mp4", ".aac"}:
        audio = MP4(path.as_posix())
        covers = audio.tags.get("covr") if audio.tags else None
        if covers:
            cover = covers[0]
            mime = "image/png" if getattr(cover, "imageformat", None) == MP4Cover.FORMAT_PNG else "image/jpeg"
            return bytes(cover), mime
        return None, None

    if suffix == ".flac":
        audio = FLAC(path.as_posix())
        if audio.pictures:
            picture = audio.pictures[0]
            return bytes(picture.data), picture.mime or "image/jpeg"
        return None, None

    try:
        id3 = ID3(path.as_posix())
    except ID3NoHeaderError:
        id3 = None
    except Exception:
        id3 = None

    if id3 is not None:
        for frame in id3.getall("APIC"):
            return bytes(frame.data), frame.mime or "image/jpeg"

    audio = MutagenFile(path.as_posix())
    pictures = getattr(audio, "pictures", None)
    if pictures:
        picture = pictures[0]
        return bytes(picture.data), getattr(picture, "mime", None) or "image/jpeg"

    if isinstance(audio, WAVE) and audio.tags:
        for frame in audio.tags.getall("APIC"):
            return bytes(frame.data), frame.mime or "image/jpeg"

    return None, None


def write_artwork(path: Path, data: bytes, mime: str) -> None:
    suffix = path.suffix.lower()
    mime = mime or "image/jpeg"

    if suffix in {".m4a", ".mp4", ".aac"}:
        audio = MP4(path.as_posix())
        if audio.tags is None:
            audio.add_tags()
        fmt = MP4Cover.FORMAT_PNG if "png" in mime else MP4Cover.FORMAT_JPEG
        audio.tags["covr"] = [MP4Cover(data, imageformat=fmt)]
        audio.save()
        return

    if suffix == ".flac":
        audio = FLAC(path.as_posix())
        picture = FlacPicture()
        picture.type = 3
        picture.mime = mime
        picture.desc = "Cover"
        picture.data = data
        audio.clear_pictures()
        audio.add_picture(picture)
        audio.save()
        return

    if suffix in {".wav", ".wave"}:
        audio = WAVE(path.as_posix())
        if audio.tags is None:
            audio.add_tags()
        audio.tags.delall("APIC")
        audio.tags.add(
            APIC(
                encoding=3,
                mime=mime,
                type=3,
                desc="Cover",
                data=data,
            )
        )
        audio.save()
        return

    try:
        id3 = ID3(path.as_posix())
    except ID3NoHeaderError:
        id3 = ID3()
    id3.delall("APIC")
    id3.add(
        APIC(
            encoding=3,
            mime=mime,
            type=3,
            desc="Cover",
            data=data,
        )
    )
    id3.save(path.as_posix())
