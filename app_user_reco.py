from pathlib import Path
import html as html_lib

import pandas as pd
import requests
import streamlit as st

DATA_PATH = Path("review_new_excels/남성_상의_어깨분석.xlsx")
GOODS_INFO_API = "https://api.musinsa.com/api2/dp/v1/goods"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        return pd.DataFrame()
    df = pd.read_excel(DATA_PATH)
    if "최종점수" in df.columns:
        return df.sort_values("최종점수", ascending=False).reset_index(drop=True)
    return df


def recompute_scores(df: pd.DataFrame, alpha: float, beta: float) -> pd.DataFrame:
    result = df.copy()
    result["정규화_어깨너비/가슴단면"] = (
        pd.to_numeric(result["어깨너비/가슴단면"], errors="coerce")
        / pd.to_numeric(result["어깨너비/가슴단면"], errors="coerce").mean()
    )
    result["정규화_어깨너비/총장"] = (
        pd.to_numeric(result["어깨너비/총장"], errors="coerce")
        / pd.to_numeric(result["어깨너비/총장"], errors="coerce").mean()
    )
    result["정규화_어깨키워드_언급비율"] = (
        pd.to_numeric(result["어깨키워드_언급비율(%)"], errors="coerce")
        / pd.to_numeric(result["어깨키워드_언급비율(%)"], errors="coerce").mean()
    )
    result["점수_절대수치"] = (
        result["정규화_어깨너비/가슴단면"] * 0.5 + result["정규화_어깨너비/총장"] * 0.5
    )
    result["점수_언급비율"] = result["정규화_어깨키워드_언급비율"]
    result["최종점수"] = result["점수_절대수치"] * alpha + result["점수_언급비율"] * beta
    return result


@st.cache_data(show_spinner=False)
def load_goods_info(goods_nos: list[str]) -> dict[str, dict]:
    if not goods_nos:
        return {}
    try:
        response = requests.get(
            GOODS_INFO_API,
            params={"goodsNoList": ",".join(goods_nos), "saleStateList": "SALE,SOLD_OUT"},
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("data", {}).get("list", [])
        return {str(item.get("goodsNo")): item for item in items}
    except Exception:
        return {}


def inject_style() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: #f5f6f8;
            color: #111;
        }
        .block-container {
            padding-top: 2.3rem !important;
            padding-bottom: 2rem !important;
            max-width: 1280px;
        }
        .topbar {
            background: linear-gradient(135deg, #0f0f10 0%, #1b1c1f 100%);
            color: #fff;
            padding: 16px 22px;
            border-radius: 12px;
            margin-bottom: 12px;
            font-weight: 700;
            letter-spacing: .6px;
            box-shadow: 0 6px 20px rgba(0,0,0,0.18);
        }
        .topbar-sub {
            color: #b8bcc5;
            font-size: 12px;
            margin-top: 4px;
            font-weight: 500;
        }
        .subnav {
            display:flex;
            gap: 18px;
            padding: 12px 8px 14px 8px;
            border-bottom: 1px solid #e5e7eb;
            margin-bottom: 20px;
            color: #4a4e57;
            font-size: 14px;
            background: #fff;
            border-radius: 10px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }
        .subnav .active {
            color: #111;
            font-weight: 700;
            border-bottom: 2px solid #111;
            padding-bottom: 2px;
        }
        .badge {
            display:inline-block;
            background:#f3f4f6;
            border:1px solid #e5e7eb;
            border-radius:999px;
            padding: 4px 10px;
            font-size:12px;
            margin-right: 6px;
            margin-top: 6px;
        }
        .score-chip {
            display:inline-block;
            background:#111827;
            color:#fff;
            border-radius:6px;
            padding:3px 9px;
            font-size:12px;
            margin-left:6px;
            margin-top: 6px;
        }
        .product-title {
            font-size: 14px;
            line-height: 1.35;
            min-height: 40px;
            margin: 8px 0 4px 0;
            font-weight: 600;
        }
        .muted { color:#6b7280; font-size:12px; }
        .product-card {
            border: 1px solid #eceff3;
            border-radius: 14px;
            padding: 12px;
            height: 448px;
            display: flex;
            flex-direction: column;
            background: #ffffff;
            box-shadow: 0 2px 10px rgba(16,24,40,0.06);
            transition: transform 0.18s ease, box-shadow 0.18s ease;
        }
        .product-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 22px rgba(16,24,40,0.13);
        }
        .product-thumb {
            width: 100%;
            height: 220px;
            object-fit: contain;
            border-radius: 10px;
            background: #f5f5f5;
            margin-bottom: 10px;
            border: 1px solid #f0f2f4;
        }
        .price {
            margin-top: auto;
            font-weight: 700;
            font-size: 17px;
            letter-spacing: .1px;
        }
        .card-caption {
            color:#6b7280;
            font-size:12px;
            line-height:1.35;
            margin-top: 7px;
        }
        .filter-title {
            font-size: 18px;
            font-weight: 700;
            margin-bottom: 2px;
        }
        .filter-sub {
            color:#6b7280;
            font-size:12px;
            margin-bottom: 10px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_product_card(row: pd.Series, rank: int, goods_map: dict[str, dict]) -> None:
    goods_no = str(int(row["상품번호"]))
    info = goods_map.get(goods_no, {})
    image_url = str(info.get("imageUrl", ""))
    brand_name = str(info.get("brandName", "브랜드"))
    final_price = info.get("finalPrice", 0)
    review_count = info.get("reviewCount", 0)
    product_url = str(info.get("linkUrl", f"https://www.musinsa.com/products/{goods_no}"))

    safe_title = html_lib.escape(str(row["상품명"]))
    safe_brand = html_lib.escape(brand_name)
    safe_product_url = html_lib.escape(product_url, quote=True)
    thumb = image_url or "https://via.placeholder.com/400x400?text=NO+IMAGE"
    card_html = (
        "<div class='product-card'>"
        f"<a href='{safe_product_url}' target='_blank'>"
        f"<img class='product-thumb' src='{thumb}' />"
        "</a>"
        f"<div class='muted'>#{rank} · {safe_brand}</div>"
        f"<a href='{safe_product_url}' target='_blank' style='text-decoration:none;color:inherit;'>"
        f"<div class='product-title'>{safe_title}</div>"
        "</a>"
        f"<div><span class='badge'>어깨 추천</span>"
        f"<span class='badge'>리뷰 {int(review_count):,}</span>"
        f"<span class='score-chip'>점수 {row.get('최종점수', 0):.3f}</span></div>"
        f"<div class='price'>{int(final_price):,}원</div>"
        f"<div class='card-caption'>어깨 언급률 {row.get('어깨키워드_언급비율(%)', 0):.2f}% · "
        f"어깨중앙 {row.get('어깨단면_중앙값', 0):.1f}</div>"
        "</div>"
    )
    st.markdown(card_html, unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title="핏 기반 추천 데모", layout="wide")
    inject_style()

    st.markdown(
        "<div class='topbar'>"
        "MUSINSA STYLE · FIT RECOMMENDER DEMO"
        "<div class='topbar-sub'>신체 부위 기반 개인화 추천 · 사용자 데모 화면</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='subnav'>"
        "<span class='active'>피트니스</span><span>남성</span><span>상의</span>"
        "<span>브랜드</span><span>신상품</span><span>랭킹</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    df = load_data()
    if df.empty:
        st.error("추천 데이터가 없습니다. `남성_상의_어깨분석.xlsx`를 먼저 생성하세요.")
        return

    left, right = st.columns([1.2, 3.8])
    with left:
        st.markdown("<div class='filter-title'>필터</div>", unsafe_allow_html=True)
        st.markdown("<div class='filter-sub'>내 취향에 맞게 추천 조건을 조정해보세요.</div>", unsafe_allow_html=True)
        selected_part = st.selectbox(
        "어떤 부위 핏을 중요하게 보시나요?",
        ["어깨", "가슴", "총장"],
        index=0,
        )
        sort_key = st.selectbox("정렬", ["추천순", "리뷰 언급순", "상품 수치 순"], index=0)
        top_n = st.slider("노출 상품 수", min_value=4, max_value=10, value=8, step=1)
        with st.expander("추가 설정"):
            st.caption("추천순 계산에만 적용됩니다.")
            with st.form("weight_form"):
                alpha_input = st.slider("상품 수치 가중치 α", 0.0, 1.0, 0.5, 0.05)
                beta_input = st.slider("리뷰 언급 가중치 β", 0.0, 1.0, 0.5, 0.05)
                apply_weights = st.form_submit_button("가중치 적용")
            if apply_weights:
                if alpha_input + beta_input == 0:
                    st.warning("α+β가 0이어서 기본값(0.5, 0.5) 사용")
                    st.session_state["alpha"] = 0.5
                    st.session_state["beta"] = 0.5
                else:
                    st.session_state["alpha"] = alpha_input
                    st.session_state["beta"] = beta_input
        alpha = st.session_state.get("alpha", 0.5)
        beta = st.session_state.get("beta", 0.5)
        st.caption(f"현재 가중치: α={alpha:.2f}, β={beta:.2f}")
        st.caption("현재 데이터셋: 남성 피트니스 상의 상위 10개")

    if selected_part != "어깨":
        st.info("현재 데모는 `어깨` 추천 모델이 적용되어 있습니다. (가슴/총장은 다음 버전)")
        return

    ranked_df = recompute_scores(df, alpha=alpha, beta=beta)
    if sort_key == "추천순":
        ranked_df = ranked_df.sort_values("최종점수", ascending=False).reset_index(drop=True)
    elif sort_key == "리뷰 언급순":
        ranked_df = ranked_df.sort_values("어깨키워드_언급비율(%)", ascending=False).reset_index(drop=True)
    else:
        ranked_df = ranked_df.sort_values("점수_절대수치", ascending=False).reset_index(drop=True)

    goods_nos = [str(int(v)) for v in ranked_df["상품번호"].tolist()]
    goods_map = load_goods_info(goods_nos)

    shown = ranked_df.head(top_n).reset_index(drop=True)
    with right:
        st.markdown("### 어깨 핏 추천 상품")
        grid_cols = st.columns(4)
        for i, row in shown.iterrows():
            with grid_cols[i % 4]:
                render_product_card(row, i + 1, goods_map)

        st.markdown("#### 추천 근거")
        st.write(
            "- 상품 수치: 어깨/가슴, 어깨/총장 비율 반영\n"
            "- 텍스트신호: 최신 리뷰 500개 내 어깨 키워드 언급률 반영\n"
            "- 두 점수를 합쳐 최종 추천순 산출"
        )


if __name__ == "__main__":
    main()
