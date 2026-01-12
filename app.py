import re
import pandas as pd
import streamlit as st

# ================== CONFIG ==================
st.set_page_config(page_title="منصة أطلس السنة – MVP", layout="wide")
st.write("VERSION: ATLAS-CORE v0.6")

# ================== Session State ==================
if "query_text" not in st.session_state:
    st.session_state.query_text = ""

# ================== Arabic helpers ==================
AR_DIACRITICS = re.compile(r"[\u0617-\u061A\u064B-\u0652\u0670\u06D6-\u06ED]")

def normalize_ar(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    text = AR_DIACRITICS.sub("", text)
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ى", "ي").replace("ة", "ه")
    text = re.sub(r"[^\w\s\u0600-\u06FF]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def tokenize_ar(text: str):
    return normalize_ar(text).split() if text else []

def similarity_by_reference_words(reference: str, candidate: str) -> float:
    ref_tokens = tokenize_ar(reference)
    cand_tokens = tokenize_ar(candidate)
    if not ref_tokens:
        return 0.0
    shared = len(set(ref_tokens) & set(cand_tokens))
    return (shared / len(ref_tokens)) * 100.0

def contains_most_words(reference: str, candidate: str, threshold: float = 0.8) -> bool:
    ref_tokens = tokenize_ar(reference)
    cand_tokens = tokenize_ar(candidate)
    if not ref_tokens:
        return False
    shared = sum(1 for tok in ref_tokens if tok in cand_tokens)
    return (shared / len(ref_tokens)) >= threshold

# ================== Data loading ==================
@st.cache_data
def load_hadith_data():
    df = pd.read_csv("hadith_data.csv")
    needed = {"hadith_key", "source", "ref", "isnad", "matn"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    return df

df_hadith = load_hadith_data()

# ================== UI ==================
st.title("📚 منصة أطلس السنة – البحث الأطلسي")

tab1, tab2 = st.tabs(["🔎 البحث وبناء وحدة الحديث", "ℹ️ ملاحظات منهجية"])

# ================== TAB 1 ==================
with tab1:
    st.subheader("🔎 البحث الأطلسي عن الحديث")

    query = st.text_area(
        "نص البحث (يمكن إدخال أكثر من حديث – كل حديث في سطر مستقل)",
        height=120,
        key="query_text",
        placeholder="مثال:\nالدين النصيحة\nإنما الأعمال بالنيات"
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        min_sim = st.slider("٪ الحد الأدنى للتشابه (للبحث غير الصارم)", 10, 100, 50, 5)
    with col2:
        top_k = st.slider("عدد النتائج (في الوضع غير الأطلسي)", 5, 200, 30, 5)
    with col3:
        atlas_mode = st.checkbox("🧭 وضع الأطلس (عرض كل الطرق)", value=True)

    strict_core = st.checkbox(
        "🔒 بحث أطلسي (يشترط نواة الحديث ≥ 80٪)",
        value=True
    )

    if st.button("🧹 مسح نص البحث"):
        st.session_state.query_text = ""

    if st.button("ابحث", type="primary"):
        if not query.strip():
            st.warning("اكتب نصًا للبحث أولًا.")
        else:
            queries = [q.strip() for q in query.split("\n") if q.strip()]
            df = df_hadith.copy()

            all_results = []

            for q in queries:
                q_norm = normalize_ar(q)
                temp = df.copy()

                temp["core_match"] = temp["matn"].astype(str).apply(
                    lambda x: contains_most_words(q_norm, x, threshold=0.8)
                )

                temp["similarity"] = temp["matn"].astype(str).apply(
                    lambda x: similarity_by_reference_words(q_norm, x)
                )

                if strict_core:
                    temp = temp[temp["core_match"]]
                else:
                    temp = temp[temp["similarity"] >= float(min_sim)]

                all_results.append(temp)

            results = pd.concat(all_results).drop_duplicates()

            if not atlas_mode:
                results = results.sort_values(
                    ["similarity"],
                    ascending=False
                ).head(int(top_k))
            else:
                results = results.sort_values(["hadith_key", "ref"])

            if results.empty:
                st.error("لا توجد نتائج مطابقة.")
            else:
                st.success(
                    f"تم العثور على {len(results)} رواية ضمن "
                    f"{results['hadith_key'].nunique()} وحدة حديثية أطلسية."
                )

                for hadith_key, grp in results.groupby("hadith_key"):
                    with st.expander(
                        f"🧭 وحدة حديث أطلسية: {hadith_key} | عدد الطرق: {len(grp)}",
                        expanded=True
                    ):
                        st.markdown("### 📌 المتن المرجعي (Raw)")
                        st.write(grp.iloc[0]["matn"])

                        st.markdown("### 🧾 الطرق والروايات")
                        for _, r in grp.iterrows():
                            st.markdown(
                                f"- **المصدر:** {r['source']} | **المرجع:** {r['ref']}\n"
                                f"  - **السند (Raw):** {r['isnad']}\n"
                                f"  - **المتن (Raw):** {r['matn']}"
                            )

# ================== TAB 2 ==================
with tab2:
    st.info(
        "هذه المنصة أداة تحضير أطلسية:\n"
        "- لا تُصدر أحكامًا حديثية\n"
        "- لا تفصل السند والمتن آليًا\n"
        "- تُستخدم لبناء بطاقة الحديث الأطلسية\n\n"
        "النص يبقى محفوظًا عند تغيير الإعدادات."
    )
