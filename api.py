from typing import Dict, List, Optional
from urllib.parse import quote_plus
import requests

from constants import BASE_URL


def fetch_image_infos(
    results: Dict[str, str],
    query: str,
    rating: Optional[str] = None,
    min_score: Optional[int] = None,
    max_pages: int = 10,
    per_page: int = 100,
) -> None:
    rating_filter = f"+rating:{rating}" if rating else ""

    page = 1
    while page <= max_pages:
        url = (
            f"{BASE_URL}?limit={per_page}&page={page}"
            f"&tags={quote_plus(query)}{rating_filter}"
        )
        if min_score:
            url += f"+score:>={min_score}"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                break
            posts = resp.json()
            if not posts:
                break
            for post in posts:
                img_url = post.get("file_url")
                img_hash = post.get("md5")
                if not img_url or not img_hash or img_hash in results:
                    continue
                results[img_hash] = img_url
            page += 1
        except Exception:
            break


def fetch_and_cache_all_image_infos(
    queries: List[str],
    ratings: List[str],
    min_score: Optional[int] = None,
    max_pages: int = 10,
    per_page: int = 100,
) -> Dict[str, str]:
    results: Dict[str, str] = {}
    ratings_set = set(ratings)

    for rating in ratings_set:
        for query in queries:
            fetch_image_infos(results, query, rating, min_score, max_pages, per_page)

    return results
