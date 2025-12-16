"""
Verify and geocode FamousPerson.birth_location values using the OpenCage API.

Usage (from project root):
    # Ensure dependencies are installed:
    #   pip install requests
    #
    # Set your OpenCage API key in the environment before running:
    #   PowerShell (current session):
    #       $env:OPENCAGE_API_KEY = 'YOUR_KEY_HERE'
    #
    # Then run:
    #   python scripts/maintenance/verify_famous_locations_opencage.py --batch-size 2000
    #
    # The script will:
    #   - Process up to N records per run (default 2000) to stay under free-tier limits
    #   - Respect the 1 request/second rate limit
    #   - Persist progress in JSON so you can resume on later days
"""

import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional, List

import requests

from database import SessionLocal, FamousPerson


OPENCAGE_API_URL = "https://api.opencagedata.com/geocode/v1/json"
PROGRESS_FILE = Path(
    "scripts/maintenance/famous_location_verification_progress.json"
)


@dataclass
class LocationCheckResult:
    id: int
    name: str
    original_location: str
    formatted: Optional[str]
    country: Optional[str]
    lat: Optional[float]
    lng: Optional[float]
    confidence: Optional[int]
    status: str  # "ok", "no_results", "error"
    error: Optional[str] = None


def load_progress() -> Dict[str, Any]:
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_progress(progress: Dict[str, Any]) -> None:
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2), encoding="utf-8")


def get_next_batch_ids(limit: int) -> List[int]:
    """Return up to `limit` FamousPerson IDs that have not yet been verified."""
    progress = load_progress()
    processed_ids = set(progress.get("processed_ids", []))

    session = SessionLocal()
    try:
        query = (
            session.query(FamousPerson.id)
            .order_by(FamousPerson.id)
        )
        ids: List[int] = []
        for fp_id, in query:
            if fp_id not in processed_ids:
                ids.append(fp_id)
            if len(ids) >= limit:
                break
    finally:
        session.close()

    return ids


def geocode_location(
    api_key: str,
    location: str,
) -> LocationCheckResult:
    params = {
        "key": api_key,
        "q": location,
        "limit": 1,
        "no_annotations": 1,
    }

    try:
        resp = requests.get(OPENCAGE_API_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return LocationCheckResult(
            id=-1,
            name="",
            original_location=location,
            formatted=None,
            country=None,
            lat=None,
            lng=None,
            confidence=None,
            status="error",
            error=str(e),
        )

    results = data.get("results") or []
    if not results:
        return LocationCheckResult(
            id=-1,
            name="",
            original_location=location,
            formatted=None,
            country=None,
            lat=None,
            lng=None,
            confidence=None,
            status="no_results",
        )

    best = results[0]
    geometry = best.get("geometry") or {}
    components = best.get("components") or {}

    return LocationCheckResult(
        id=-1,
        name="",
        original_location=location,
        formatted=best.get("formatted"),
        country=components.get("country"),
        lat=geometry.get("lat"),
        lng=geometry.get("lng"),
        confidence=best.get("confidence"),
        status="ok",
    )


def verify_batch(batch_size: int = 2000) -> None:
    api_key = os.getenv("OPENCAGE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENCAGE_API_KEY is not set. Please set it in your environment before running this script."
        )

    progress = load_progress()
    processed_ids: List[int] = progress.get("processed_ids", [])
    results: Dict[str, Any] = progress.get("results", {})

    batch_ids = get_next_batch_ids(batch_size)
    if not batch_ids:
        print("No more famous people to verify. All done.")
        return

    print(f"Verifying {len(batch_ids)} famous people locations with OpenCage...")

    session = SessionLocal()
    try:
        for idx, fp_id in enumerate(batch_ids, start=1):
            fp: FamousPerson = session.query(FamousPerson).get(fp_id)  # type: ignore
            if not fp:
                continue

            location_str = fp.birth_location
            print(f"[{idx}/{len(batch_ids)}] #{fp.id} {fp.name} – '{location_str}'")

            # Call OpenCage and respect 1 req/sec rate limit
            res = geocode_location(api_key, location_str)
            # Attach id/name for easier tracking
            res.id = fp.id
            res.name = fp.name

            # Store result keyed by ID as string
            results[str(fp.id)] = asdict(res)
            processed_ids.append(fp.id)

            # Persist progress every 25 records to be safe
            if idx % 25 == 0:
                save_progress(
                    {
                        "processed_ids": processed_ids,
                        "results": results,
                    }
                )

            # 1 request per second to stay within free-tier rate limits
            time.sleep(1.05)
    finally:
        session.close()

    # Final save
    save_progress(
        {
            "processed_ids": processed_ids,
            "results": results,
        }
    )

    print(f"Done. Progress saved to {PROGRESS_FILE}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Verify famous_people.birth_location using OpenCage."
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=2000,
        help="Number of records to verify in this run (default: 2000).",
    )
    args = parser.parse_args()

    verify_batch(batch_size=args.batch_size)


