import json
import time
from typing import Dict, List, Optional
from urllib.parse import quote_plus

import urllib3

from constants import BASE_URL
from logger import logger


def fetch_image_infos(
    http: urllib3.PoolManager,
    results: Dict[str, str],
    query: str,
    rating: Optional[str] = None,
    min_score: Optional[int] = None,
    max_pages: int = 10,
    per_page: int = 100,
    max_image_size: Optional[int] = None,
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
            response: urllib3.HTTPResponse = http.request("GET", url, timeout=30)

            if response.status != 200:
                break

            posts = json.loads(response.data.decode("utf-8"))
            response.release_conn()

            if not posts:
                break

            for post in posts:
                img_url = post.get("file_url")
                img_hash = post.get("md5")

                if not img_url or not img_hash or img_hash in results:
                    continue

                if max_image_size:
                    img_size = post.get("file_size")
                    if not img_size or img_size > max_image_size:
                        continue

                results[img_hash] = img_url

            page += 1

        except Exception as e:
            logger.error(e)
            time.sleep(1)
            break


def fetch_and_cache_all_image_infos(
    queries: List[str],
    ratings: List[str],
    min_score: Optional[int] = None,
    max_pages: int = 10,
    per_page: int = 100,
    max_image_size: Optional[int] = None,
) -> Dict[str, str]:
    http = urllib3.PoolManager()
    results: Dict[str, str] = {}
    ratings_set = set(ratings)

    for rating in ratings_set:
        for query in queries:
            fetch_image_infos(
                http,
                results,
                query,
                rating,
                min_score,
                max_pages,
                per_page,
                max_image_size,
            )

    return results
