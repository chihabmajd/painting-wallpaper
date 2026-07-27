"""Keep the pool of ready-to-show paintings topped up.

Runs in the background after login and once a day on a timer — never on the
login path itself. Each pooled entry is fully downloaded and composed to screen
size ahead of time, so showing it later costs nothing. If the network is down,
whatever is already pooled keeps the next few logins working.
"""
import os
import random
import sys
import time
from pathlib import Path

import requests

import compose_wallpaper
import store

RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 5

MET_SEARCH = "https://collectionapi.metmuseum.org/public/collection/v1/search"
MET_OBJECT = "https://collectionapi.metmuseum.org/public/collection/v1/objects/{}"
WIKIDATA_ENTITY = "https://www.wikidata.org/wiki/Special:EntityData/{}.json"
WIKI_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"

HEADERS = {"User-Agent": "painting-wallpaper/1.0 (personal desktop script)"}

JPEG_MAGIC = b"\xff\xd8\xff"


def write_image_atomically(path: Path, data: bytes) -> None:
    """Write an image so that it is either complete on disk or not there at all.

    Nothing downstream re-validates a pooled image beyond a cheap header check,
    and a half-written file is indistinguishable from a good one in pool.json,
    so a torn write poisons the pool until someone deletes the file by hand.
    Writing to a sidecar and renaming means a crash mid-download leaves a
    stray .part, never a truncated .jpg; the fsync is what makes that hold
    across an unclean shutdown rather than just across a process crash.
    """
    if not data.startswith(JPEG_MAGIC):
        raise RuntimeError(f"downloaded data is not a JPEG ({len(data)} bytes)")

    tmp = path.with_name(path.name + ".part")
    with tmp.open("wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    tmp.replace(path)


def fetch_highlight_ids() -> list[int]:
    resp = requests.get(
        MET_SEARCH,
        params={"q": "painting", "isHighlight": "true", "hasImages": "true"},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("objectIDs") or []


def fetch_object(object_id: int) -> dict:
    resp = requests.get(MET_OBJECT.format(object_id), headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_wikipedia_info(wikidata_url: str) -> tuple[str, str] | None:
    """Returns (extract, article_url) for the object's Wikipedia article, if any."""
    if not wikidata_url:
        return None
    qid = wikidata_url.rstrip("/").rsplit("/", 1)[-1]
    try:
        resp = requests.get(WIKIDATA_ENTITY.format(qid), headers=HEADERS, timeout=10)
        resp.raise_for_status()
        entity = resp.json()["entities"][qid]
        title = entity.get("sitelinks", {}).get("enwiki", {}).get("title")
        if not title:
            return None
        resp = requests.get(
            WIKI_SUMMARY.format(title.replace(" ", "_")), headers=HEADERS, timeout=10
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        extract = data.get("extract")
        article_url = data.get("content_urls", {}).get("desktop", {}).get("page")
        if not extract or not article_url:
            return None
        return extract, article_url
    except (requests.RequestException, KeyError, ValueError):
        return None


def compose_fallback_description(obj: dict) -> str:
    parts = [obj.get(k) for k in ("medium", "culture", "creditLine")]
    parts = [p for p in parts if p]
    return ". ".join(parts) if parts else "No further description available."


def pick_painting(max_attempts: int = 20) -> dict:
    ids = fetch_highlight_ids()
    if not ids:
        raise RuntimeError("Met API returned no highlight paintings")

    seen = store.load_seen()
    candidates = [i for i in ids if i not in seen] or ids
    random.shuffle(candidates)

    for object_id in candidates[:max_attempts]:
        obj = fetch_object(object_id)
        seen.add(object_id)
        store.save_seen(seen)

        # "isHighlight=true&q=painting" is a free-text search, not a strict
        # category filter — it also returns furniture, sculpture, etc. that
        # merely mention "painting" somewhere in their record. objectName is
        # the reliable field for "this is actually a painting".
        if obj.get("objectName") != "Painting":
            continue

        image_url = obj.get("primaryImage")
        if not image_url or not obj.get("isPublicDomain"):
            continue

        wiki_info = fetch_wikipedia_info(obj.get("objectWikidata_URL", ""))
        if wiki_info:
            description, wikipedia_url = wiki_info
            source = "wikipedia"
        else:
            description, wikipedia_url, source = compose_fallback_description(obj), "", "met"

        return {
            "objectID": object_id,
            "title": obj.get("title") or "Untitled",
            "artist": obj.get("artistDisplayName") or "Unknown artist",
            "artistBio": obj.get("artistDisplayBio") or "",
            "date": obj.get("objectDate") or "",
            "medium": obj.get("medium") or "",
            "department": obj.get("department") or "",
            "creditLine": obj.get("creditLine") or "",
            "objectURL": obj.get("objectURL") or "",
            "wikipediaURL": wikipedia_url,
            "imageURL": image_url,
            "description": description.strip(),
            "descriptionSource": source,
        }

    raise RuntimeError("Could not find a usable highlight painting after several attempts")


def fetch_one() -> dict | None:
    """Pick, download and compose one painting, retrying through network errors."""
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            info = pick_painting()

            image_resp = requests.get(info["imageURL"], headers=HEADERS, timeout=30)
            image_resp.raise_for_status()
            ext = Path(info["imageURL"]).suffix or ".jpg"
            image_path = store.MEDIA_DIR / f"{info['objectID']}{ext}"
            write_image_atomically(image_path, image_resp.content)
            info["imagePath"] = str(image_path)

            try:
                info["wallpaperPath"] = str(
                    compose_wallpaper.compose(image_path, info["objectID"])
                )
            except Exception as exc:  # noqa: BLE001
                print(f"warning: compositing failed, using raw image: {exc}", file=sys.stderr)
                info["wallpaperPath"] = str(image_path)

            return info
        except (requests.RequestException, RuntimeError, OSError) as exc:
            print(f"attempt {attempt}/{RETRY_ATTEMPTS} failed: {exc}", file=sys.stderr)
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    return None


def main() -> None:
    store.MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    pool = store.load_pool()
    added = 0
    while len(pool) < store.POOL_SIZE:
        info = fetch_one()
        if info is None:
            print("giving up for now, keeping what's already pooled", file=sys.stderr)
            break
        pool.append(info)
        store.save_pool(pool)  # save as we go so partial progress survives
        added += 1
        print(f"pooled: {info['title']} — {info['artist']}")

    print(f"pool ready: {len(pool)}/{store.POOL_SIZE} (+{added} this run)")


if __name__ == "__main__":
    main()
