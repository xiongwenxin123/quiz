from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import re
import tarfile
import time
import urllib.request
from collections import defaultdict
from pathlib import Path


ENGLISH_REVISION = "d4e45b75b38f27b30dfc5c44d8c571aec7e7092f"
JAPANESE_REVISION = "04014e06019fc9d4af76e6dbb64ec709fe863c4d"
OPENSLR_SPANISH_URLS = (
    "https://openslr.elda.org/resources/21/es_wordlist.json.tgz",
    "https://openslr.trmal.net/resources/21/es_wordlist.json.tgz",
)
WORD_RE = re.compile(r"^[^\W\d_]+(?:[-'’][^\W\d_]+)*$", re.UNICODE)


def download(url: str) -> bytes:
    errors: list[str] = []
    for attempt in range(1, 4):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "polyglot-quiz-data/1.0"}
            )
            with urllib.request.urlopen(request, timeout=180) as response:
                return response.read()
        except Exception as exc:  # noqa: BLE001 - build script retries transports
            errors.append(f"attempt {attempt}: {exc}")
            if attempt < 3:
                time.sleep(attempt)
    raise RuntimeError(f"Download failed for {url}: {'; '.join(errors)}")


def download_first(urls: tuple[str, ...]) -> bytes:
    errors: list[str] = []
    for url in urls:
        try:
            return download(url)
        except Exception as exc:  # noqa: BLE001 - build script reports all mirrors
            errors.append(f"{url}: {exc}")
    raise RuntimeError("All download mirrors failed:\n" + "\n".join(errors))


def raw_github(repo: str, revision: str, path: str) -> bytes:
    return download(f"https://raw.githubusercontent.com/{repo}/{revision}/{path}")


def normalize_cefr(value: str) -> str | None:
    match = re.search(r"\b([ABC][12])\b", value.upper())
    return match.group(1) if match else None


def english_profile() -> dict[str, object]:
    repo = "openlanguageprofiles/olp-en-cefrj"
    vocab_files = (
        "cefrj-vocabulary-profile-1.5.csv",
        "octanove-vocabulary-profile-c1c2-1.0.csv",
    )
    vocabulary: dict[str, dict[str, str]] = {}
    for filename in vocab_files:
        text = raw_github(repo, ENGLISH_REVISION, filename).decode("utf-8-sig")
        for row in csv.DictReader(io.StringIO(text)):
            term = (row.get("headword") or row.get("Headword") or "").strip().casefold()
            level = normalize_cefr(row.get("CEFR") or row.get("Level") or "")
            if not term or not level or len(term) > 80:
                continue
            current = vocabulary.get(term)
            if current and current["level"] <= level:
                continue
            vocabulary[term] = {
                "level": level,
                "pos": (row.get("pos") or row.get("POS") or "").strip(),
            }

    grammar_text = raw_github(
        repo, ENGLISH_REVISION, "cefrj-grammar-profile-20180315.csv"
    ).decode("utf-8-sig")
    grammar: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in csv.DictReader(io.StringIO(grammar_text)):
        pattern = (row.get("Grammatical Item") or "").strip()
        level = normalize_cefr(
            row.get("CEFR-J Level") or row.get("FREQ*DISP") or row.get("Core Inventory") or ""
        )
        literal = pattern.replace("...", " ").replace("?", " ").strip()
        literal = re.sub(r"\s+", " ", literal)
        if not level or len(literal) < 3 or not re.search(r"[A-Za-z]", literal):
            continue
        key = (literal.casefold(), level)
        if key in seen:
            continue
        seen.add(key)
        grammar.append({"pattern": pattern, "match": literal, "level": level})

    return {
        "metadata": {
            "source": "CEFR-J Vocabulary and Grammar Profiles; Octanove C1/C2 Profile",
            "source_url": "https://github.com/openlanguageprofiles/olp-en-cefrj",
            "revision": ENGLISH_REVISION,
            "license": "CEFR-J citation-required terms; Octanove CC BY-SA 4.0",
            "level_status": "profile",
        },
        "vocabulary": vocabulary,
        "grammar": grammar,
    }


def japanese_profile() -> dict[str, object]:
    repo = "jkindrix/japanese-language-data"
    classifications = json.loads(
        raw_github(
            repo, JAPANESE_REVISION, "data/enrichment/jlpt-classifications.json"
        )
    )
    grammar_data = json.loads(
        raw_github(repo, JAPANESE_REVISION, "data/grammar/grammar.json")
    )
    vocabulary: dict[str, dict[str, str]] = {}
    for entry in classifications["classifications"]:
        if entry.get("kind") != "vocab":
            continue
        term = str(entry.get("text") or "").strip()
        level = str(entry.get("level") or "").upper()
        if not term or level not in {"N1", "N2", "N3", "N4", "N5"}:
            continue
        vocabulary[term] = {
            "level": level,
            "reading": str(entry.get("reading") or ""),
            "meaning_en": str(entry.get("meaning_en") or ""),
        }

    grammar: list[dict[str, str]] = []
    for entry in grammar_data["grammar_points"]:
        pattern = str(entry.get("pattern") or "").strip()
        level = str(entry.get("level") or "").upper()
        japanese_runs = re.findall(r"[ぁ-んァ-ヶ一-龯々〆ヵヶー]{3,}", pattern)
        match = max(
            enumerate(japanese_runs),
            key=lambda item: (len(item[1]), item[0]),
            default=(-1, ""),
        )[1]
        if not match or level not in {"N1", "N2", "N3", "N4", "N5"}:
            continue
        grammar.append(
            {
                "pattern": pattern,
                "match": match,
                "level": level,
                "meaning_en": str(entry.get("meaning_en") or ""),
                "review_status": str(entry.get("review_status") or "draft"),
            }
        )

    return {
        "metadata": {
            "source": "Japanese Language Data; Waller JLPT classifications",
            "source_url": "https://github.com/jkindrix/japanese-language-data",
            "revision": JAPANESE_REVISION,
            "license": "CC BY-SA 4.0",
            "level_status": "community_estimate_not_official",
        },
        "vocabulary": vocabulary,
        "grammar": grammar,
    }


def spanish_profile(archive: bytes) -> dict[str, object]:
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
        member = bundle.getmember("es_wordlist.json")
        extracted = bundle.extractfile(member)
        if extracted is None:
            raise RuntimeError("OpenSLR archive does not contain es_wordlist.json")
        raw_counts: dict[str, int] = json.load(extracted)

    counts: defaultdict[str, int] = defaultdict(int)
    for raw_term, count in raw_counts.items():
        term = raw_term.casefold().strip()
        if 2 <= len(term) <= 40 and WORD_RE.fullmatch(term):
            counts[term] += int(count)

    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:40_000]
    boundaries = ((1_000, "A1"), (2_500, "A2"), (5_000, "B1"), (10_000, "B2"), (20_000, "C1"), (40_000, "C2"))
    vocabulary: dict[str, dict[str, object]] = {}
    boundary_index = 0
    for rank, (term, count) in enumerate(ranked, start=1):
        while rank > boundaries[boundary_index][0]:
            boundary_index += 1
        vocabulary[term] = {
            "level": boundaries[boundary_index][1],
            "rank": rank,
            "count": count,
        }

    return {
        "metadata": {
            "source": "OpenSLR 21 Spanish Gigaword frequency list",
            "source_url": "https://www.openslr.org/21/",
            "license": "CC BY-SA 3.0 US",
            "level_status": "frequency_band_estimate_not_official_cefr",
            "rank_boundaries": {level: limit for limit, level in boundaries},
        },
        "vocabulary": vocabulary,
        "grammar": [],
    }


def write_profile(path: Path, profile: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(profile, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as output:
        output.write(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build bundled graded learning profiles")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("src/polyglot_quiz/data"),
    )
    parser.add_argument("--spanish-archive", type=Path)
    args = parser.parse_args()

    spanish_archive = (
        args.spanish_archive.read_bytes()
        if args.spanish_archive
        else download_first(OPENSLR_SPANISH_URLS)
    )
    profiles = {
        "en": english_profile(),
        "ja": japanese_profile(),
        "es": spanish_profile(spanish_archive),
    }
    for language, profile in profiles.items():
        destination = args.output_dir / f"learning-profile-{language}.json.gz"
        write_profile(destination, profile)
        print(
            f"{language}: {len(profile['vocabulary'])} vocabulary, "
            f"{len(profile['grammar'])} grammar -> {destination}"
        )


if __name__ == "__main__":
    main()
