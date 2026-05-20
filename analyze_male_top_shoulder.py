import re
from pathlib import Path
from typing import Dict, List
from statistics import median

import pandas as pd
import requests

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
REQUEST_TIMEOUT = 20
PRODUCTS_PER_GROUP = 10
REVIEWS_PER_ITEM = 500
REVIEW_PAGE_SIZE = 20

PLP_GOODS_API = "https://api.musinsa.com/api2/dp/v2/plp/goods"
REVIEW_API = "https://goods.musinsa.com/api2/review/v1/view/list"
ACTUAL_SIZE_API_TEMPLATE = "https://goods-detail.musinsa.com/api2/goods/{goods_no}/actual-size"

FITNESS_TOP_CATEGORY = "017042001"
OUTPUT_DIR = Path("review_new_excels")
OUTPUT_FILE = OUTPUT_DIR / "남성_상의_어깨분석.xlsx"
ALPHA = 0.5  # 절대수치 점수 가중치
BETA = 0.5   # 어깨키워드 언급 점수 가중치

SHOULDER_KEYWORDS = [
    "어깨",
    "어깨선",
    "어좁",
    "어깡",
    "숄더",
    "견갑",
]


def normalize_text(text: str) -> str:
    return " ".join((text or "").strip().split())


def fetch_male_top_products() -> List[Dict]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    products: List[Dict] = []
    page = 1
    while len(products) < PRODUCTS_PER_GROUP and page <= 20:
        params = {
            "gf": "M",
            "sortCode": "REVIEW",
            "separatorId": "2",
            "category": FITNESS_TOP_CATEGORY,
            "size": "60",
            "testGroup": "",
            "caller": "CATEGORY",
            "page": str(page),
            "seen": "0",
            "seenAds": "",
        }
        response = session.get(PLP_GOODS_API, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
        product_list = payload.get("data", {}).get("list", [])
        if not product_list:
            break

        for item in product_list:
            goods_no = str(item.get("goodsNo", "")).strip()
            if not goods_no:
                continue
            products.append(
                {
                    "goods_no": goods_no,
                    "goods_name": normalize_text(str(item.get("goodsName", ""))),
                    "review_count_ranked": int(item.get("reviewCount") or 0),
                }
            )
            if len(products) >= PRODUCTS_PER_GROUP:
                break
        page += 1

    deduped: List[Dict] = []
    seen = set()
    for product in products:
        if product["goods_no"] in seen:
            continue
        seen.add(product["goods_no"])
        deduped.append(product)
    return deduped[:PRODUCTS_PER_GROUP]


def fetch_latest_review_texts(goods_no: str, limit: int = REVIEWS_PER_ITEM) -> List[str]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    texts: List[str] = []
    page = 0
    while len(texts) < limit:
        params = {
            "goodsNo": goods_no,
            "page": page,
            "pageSize": REVIEW_PAGE_SIZE,
            "sort": "new_desc",
        }
        response = session.get(REVIEW_API, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
        review_list = payload.get("data", {}).get("list", [])
        if not review_list:
            break

        for review in review_list:
            content = normalize_text(str(review.get("content", "")))
            if content:
                texts.append(content)
            if len(texts) >= limit:
                break
        page += 1
    return texts[:limit]


def fetch_size_measurements(goods_no: str) -> Dict[str, Dict[str, float]]:
    url = ACTUAL_SIZE_API_TEMPLATE.format(goods_no=goods_no)
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    size_rows = payload.get("data", {}).get("sizes", [])

    result: Dict[str, Dict[str, float]] = {"어깨": {}, "가슴": {}, "총장": {}}
    for size_row in size_rows:
        size_name = normalize_text(str(size_row.get("name", "")))
        if not size_name:
            continue
        for item in size_row.get("items", []):
            measure_name = normalize_text(str(item.get("name", "")))
            value = item.get("value")
            if not isinstance(value, (int, float)):
                continue
            value = float(value)
            if "어깨" in measure_name:
                result["어깨"][size_name] = value
            elif "가슴" in measure_name:
                result["가슴"][size_name] = value
            elif "총장" in measure_name:
                result["총장"][size_name] = value
    return result


def get_median_from_map(size_map: Dict[str, float]) -> float | None:
    if not size_map:
        return None
    return float(median(size_map.values()))


def safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def count_shoulder_mentions(texts: List[str]) -> int:
    pattern = re.compile("|".join(re.escape(k) for k in SHOULDER_KEYWORDS))
    return sum(1 for text in texts if pattern.search(text))


def add_scoring_columns(df: pd.DataFrame) -> pd.DataFrame:
    # value / overall mean normalization
    df["정규화_어깨너비/가슴단면"] = (
        pd.to_numeric(df["어깨너비/가슴단면"], errors="coerce")
        / pd.to_numeric(df["어깨너비/가슴단면"], errors="coerce").mean()
    )
    df["정규화_어깨너비/총장"] = (
        pd.to_numeric(df["어깨너비/총장"], errors="coerce")
        / pd.to_numeric(df["어깨너비/총장"], errors="coerce").mean()
    )
    df["정규화_어깨키워드_언급비율"] = (
        pd.to_numeric(df["어깨키워드_언급비율(%)"], errors="coerce")
        / pd.to_numeric(df["어깨키워드_언급비율(%)"], errors="coerce").mean()
    )

    # Absolute-size score: two absolute ratios equally weighted.
    df["점수_절대수치"] = (
        df["정규화_어깨너비/가슴단면"] * 0.5
        + df["정규화_어깨너비/총장"] * 0.5
    )

    # Mention score from normalized shoulder mention ratio.
    df["점수_언급비율"] = df["정규화_어깨키워드_언급비율"]

    # Final score with adjustable alpha/beta.
    df["최종점수"] = df["점수_절대수치"] * ALPHA + df["점수_언급비율"] * BETA
    return df


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    products = fetch_male_top_products()
    print(f"[상품목록] 남성_상의 {len(products)}개")

    rows: List[Dict] = []
    for idx, product in enumerate(products, start=1):
        goods_no = product["goods_no"]
        product_name = product["goods_name"] or f"상품_{goods_no}"
        print(f"[분석 시작] 남성_상의{idx} goodsNo={goods_no}")

        try:
            measurement_map = fetch_size_measurements(goods_no)
        except Exception as exc:
            print(f"[경고] 어깨 실측 조회 실패 goodsNo={goods_no}: {exc}")
            measurement_map = {"어깨": {}, "가슴": {}, "총장": {}}

        shoulder_median = get_median_from_map(measurement_map["어깨"])
        chest_median = get_median_from_map(measurement_map["가슴"])
        length_median = get_median_from_map(measurement_map["총장"])
        shoulder_to_chest = safe_div(shoulder_median, chest_median)
        shoulder_to_length = safe_div(shoulder_median, length_median)

        review_texts = fetch_latest_review_texts(goods_no, REVIEWS_PER_ITEM)
        mention_count = count_shoulder_mentions(review_texts)
        review_count = len(review_texts)
        mention_ratio = (mention_count / review_count * 100.0) if review_count else 0.0

        rows.append(
            {
                "그룹": f"남성_상의{idx}",
                "상품번호": goods_no,
                "상품명": product_name,
                "랭킹기준_후기수": product["review_count_ranked"],
                "어깨단면_중앙값": shoulder_median,
                "가슴단면_중앙값": chest_median,
                "총장_중앙값": length_median,
                "어깨너비/가슴단면": shoulder_to_chest,
                "어깨너비/총장": shoulder_to_length,
                "최신리뷰_수집개수": review_count,
                "어깨키워드_언급리뷰수": mention_count,
                "어깨키워드_언급비율(%)": round(mention_ratio, 2),
            }
        )
        print(
            f"[완료] 남성_상의{idx} 리뷰 {review_count}개, "
            f"어깨 언급 {mention_count}개 ({mention_ratio:.2f}%)"
        )

    result_df = pd.DataFrame(
        rows,
        columns=[
            "그룹",
            "상품번호",
            "상품명",
            "랭킹기준_후기수",
            "어깨단면_중앙값",
            "가슴단면_중앙값",
            "총장_중앙값",
            "어깨너비/가슴단면",
            "어깨너비/총장",
            "최신리뷰_수집개수",
            "어깨키워드_언급리뷰수",
            "어깨키워드_언급비율(%)",
        ],
    )
    result_df = add_scoring_columns(result_df)
    result_df = result_df.sort_values("최종점수", ascending=False).reset_index(drop=True)
    result_df.to_excel(OUTPUT_FILE, index=False)
    print(f"[저장 완료] {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
