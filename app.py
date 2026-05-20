from pathlib import Path

import pandas as pd
import requests
import streamlit as st

DATA_PATH = Path("review_new_excels/남성_상의_어깨분석.xlsx")
GOODS_INFO_API = "https://api.musinsa.com/api2/dp/v1/goods"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


@st.cache_data(show_spinner=False)
def load_analysis_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        return pd.DataFrame()
    return pd.read_excel(DATA_PATH)


@st.cache_data(show_spinner=False)
def load_goods_images(goods_nos: list[str]) -> dict[str, str]:
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
        return {str(item.get("goodsNo")): str(item.get("imageUrl", "")) for item in items}
    except Exception:
        return {}


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
    result = result.sort_values("최종점수", ascending=False).reset_index(drop=True)
    return result


def main() -> None:
    st.set_page_config(page_title="어깨 핏 분석 데모", layout="wide")
    st.title("남성 피트니스 상의 어깨 핏 분석 데모")
    st.caption("후기순 상위 10개 상품 기준 / 최신 500개 리뷰 / 어깨 실측 + 어깨 언급비율")

    df = load_analysis_data()
    if df.empty:
        st.error("분석 파일이 없습니다. `review_new_excels/남성_상의_어깨분석.xlsx`를 먼저 생성하세요.")
        return

    st.markdown("### 1) 분석 조건")
    c1, c2 = st.columns(2)
    with c1:
        alpha = st.slider("절대수치 가중치 α", min_value=0.0, max_value=1.0, value=0.5, step=0.05)
    with c2:
        beta = st.slider("언급비율 가중치 β", min_value=0.0, max_value=1.0, value=0.5, step=0.05)
    if alpha + beta == 0:
        st.warning("α + β가 0이면 점수 계산이 불가합니다. 기본값(0.5, 0.5) 사용.")
        alpha, beta = 0.5, 0.5

    result = recompute_scores(df, alpha=alpha, beta=beta)

    st.markdown("### 2) 점수 계산식")
    st.code(
        "점수_절대수치 = 0.5*(어깨너비/가슴단면 정규화) + 0.5*(어깨너비/총장 정규화)\n"
        "점수_언급비율 = 어깨키워드_언급비율 정규화\n"
        "최종점수 = α*점수_절대수치 + β*점수_언급비율",
        language="text",
    )

    st.markdown("### 3) 상품 랭킹")
    show_cols = [
        "그룹",
        "상품번호",
        "상품명",
        "어깨단면_중앙값",
        "어깨너비/가슴단면",
        "어깨너비/총장",
        "어깨키워드_언급비율(%)",
        "점수_절대수치",
        "점수_언급비율",
        "최종점수",
    ]
    st.dataframe(result[show_cols], use_container_width=True, hide_index=True)

    st.markdown("### 4) 상위 10개 카드")
    goods_nos = [str(v) for v in result["상품번호"].astype(str).tolist()]
    image_map = load_goods_images(goods_nos)

    for idx, row in result.iterrows():
        with st.container(border=True):
            c1, c2 = st.columns([1, 3])
            with c1:
                image_url = image_map.get(str(row["상품번호"]), "")
                if image_url:
                    st.image(image_url, use_container_width=True)
                else:
                    st.write("이미지 없음")
            with c2:
                st.markdown(f"**#{idx + 1} {row['상품명']}**")
                st.write(
                    f"- 상품번호: `{int(row['상품번호'])}`\n"
                    f"- 최종점수: `{row['최종점수']:.3f}`\n"
                    f"- 절대수치점수: `{row['점수_절대수치']:.3f}` / 언급점수: `{row['점수_언급비율']:.3f}`\n"
                    f"- 어깨언급비율: `{row['어깨키워드_언급비율(%)']:.2f}%`"
                )


if __name__ == "__main__":
    main()
