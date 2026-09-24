#!/usr/bin/env python3
"""
Script to download StatsBomb open data from GitHub repository.
Downloads competitions, matches, and creates a local structure for data processing.
"""

import os
import json
import requests
from pathlib import Path
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Base URL for StatsBomb open data
BASE_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"

# Target competitions (English names)
TARGET_COMPETITIONS = {
    "Premier League": 2,
    "La Liga": 4,
    "Champions League": 16,
}

class StatsBombDownloader:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def _download_json(self, url: str, retries: int = 3) -> Optional[Dict]:
        """Download JSON from URL with retry logic."""
        for attempt in range(retries):
            try:
                logger.info(f"Downloading: {url} (attempt {attempt + 1}/{retries})")
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt == retries - 1:
                    logger.error(f"Failed to download {url} after {retries} attempts")
                    return None
        return None

    def download_competitions(self) -> Optional[List[Dict]]:
        """Download competitions list."""
        url = f"{BASE_URL}/competitions.json"
        logger.info("Downloading competitions list...")
        data = self._download_json(url)

        if data:
            # Save to file
            output_file = self.output_dir / "competitions.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved competitions to {output_file}")
            logger.info(f"Found {len(data)} competitions")

            # Log available competitions
            for comp in data:
                logger.debug(f"  - {comp.get('competition_name', 'Unknown')} (ID: {comp.get('competition_id')})")

            return data
        return None

    def download_matches(self, competitions_data: List[Dict]) -> Dict[str, List[Dict]]:
        """Download matches for target competitions."""
        all_matches = {}

        for comp in competitions_data:
            comp_name = comp.get('competition_name', 'Unknown')
            comp_id = comp.get('competition_id')
            season_id = comp.get('season_id')

            # Only download target competitions
            if comp_name not in TARGET_COMPETITIONS or comp_id != TARGET_COMPETITIONS[comp_name]:
                continue

            logger.info(f"Downloading matches for {comp_name} (Season {comp.get('season_name')})...")

            url = f"{BASE_URL}/matches/{comp_id}/{season_id}.json"
            matches = self._download_json(url)

            if matches:
                key = f"{comp_name}_{season_id}"
                all_matches[key] = matches

                # Save to file
                output_file = self.output_dir / f"matches_{comp_name.replace(' ', '_')}_{season_id}.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(matches, f, indent=2)
                logger.info(f"Saved {len(matches)} matches to {output_file}")
            else:
                logger.warning(f"Failed to download matches for {comp_name}")

        return all_matches

    def download_events(self, matches_data: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
        """Download events for all matches."""
        all_events = {}
        total_events = 0

        for competition_key, matches in matches_data.items():
            logger.info(f"Downloading events for {competition_key} ({len(matches)} matches)...")

            competition_events = []
            match_dir = self.output_dir / competition_key
            match_dir.mkdir(exist_ok=True)

            for idx, match in enumerate(matches, 1):
                match_id = match.get('match_id')
                match_name = f"{match.get('home_team', {}).get('home_team_name', 'Unknown')} vs {match.get('away_team', {}).get('away_team_name', 'Unknown')}"

                url = f"{BASE_URL}/events/{match_id}.json"
                events = self._download_json(url)

                if events:
                    competition_events.extend(events)
                    total_events += len(events)

                    # Save individual match events
                    match_file = match_dir / f"match_{match_id}.json"
                    with open(match_file, 'w', encoding='utf-8') as f:
                        json.dump(events, f, indent=2)

                    logger.debug(f"  [{idx}/{len(matches)}] Match {match_id} ({match_name}): {len(events)} events")
                else:
                    logger.warning(f"  [{idx}/{len(matches)}] Failed to download events for match {match_id}")

            all_events[competition_key] = competition_events

            # Save aggregated events
            agg_file = self.output_dir / f"events_{competition_key}.json"
            with open(agg_file, 'w', encoding='utf-8') as f:
                json.dump(competition_events, f, indent=2)
            logger.info(f"Saved {len(competition_events)} events to {agg_file}")

        logger.info(f"Downloaded total of {total_events} events")
        return all_events

    def download_all(self) -> bool:
        """Download all data."""
        try:
            # Step 1: Download competitions
            competitions = self.download_competitions()
            if not competitions:
                logger.error("Failed to download competitions")
                return False

            # Step 2: Download matches
            matches = self.download_matches(competitions)
            if not matches:
                logger.error("Failed to download matches")
                return False

            # Step 3: Download events
            events = self.download_events(matches)
            if not events:
                logger.error("Failed to download events")
                return False

            logger.info("Successfully downloaded all data")
            return True

        except Exception as e:
            logger.error(f"Error during download: {e}")
            return False


def main():
    """Main entry point."""
    output_dir = Path(__file__).parent.parent / "core" / "data" / "statsbomb_raw"

    logger.info(f"Starting StatsBomb data download to {output_dir}")

    downloader = StatsBombDownloader(str(output_dir))
    success = downloader.download_all()

    if success:
        logger.info("Download completed successfully")
        return 0
    else:
        logger.error("Download failed")
        return 1


if __name__ == "__main__":
    exit(main())
