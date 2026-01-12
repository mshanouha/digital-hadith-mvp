import re
import pandas as pd
import streamlit as st

# ================== CONFIG ==================
st.set_page_config(page_title="منصة أطلس السنة – MVP", layout="wide")
st.write("VERSION: ATLAS-STRICT v0.4")

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
    ref_set = set(ref_tokens)
    cand_set = set(cand_tokens)
    shared = len(ref_set.intersection(cand_set))
    return (shared / len(ref_set)) * 100.0

def contains_all_words(reference: str, candidate: str) -> bool:
    """
    بحث أطلسي صارم:
    True إذا كان المتن يحتوي على جميع كلمات المتن المرجعي
    """
    ref_tokens = tokenize_ar(reference)
    cand_tokens = tokenize_ar(candidate)
    if not ref_tokens:
        return False
    return all(tok in cand_tokens for tok in ref_tokens)

# ================== Data loading ==================
@st.cache_data
def load_hadith_data():
    try:
        df = pd.read_csv("hadith_data.csv")
        needed = {"hadith_key", "source", "ref", "isnad", "matn"}
        missing = needed - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns: {missing}")
        return df
    except Exception:
        # fallback sample
        sample = [
            {
                "hadith_key": "B00001",
                "source": "عينة",
                "ref": "1",
                "isnad": "فلان عن فلان",
                "matn": "انما الاعمال بالنيات وانما لكل امرئ ما نوى"
            },
            {
                "hadith_key": "B00002",
                "source": "عينة",
                "ref": "2",
                "isnad": "فلان عن فلان",
                "matn": "الدين النصيحه قلنا لمن قال لله ولكتابه"
            },
        ]
        return pd.DataFrame(sample)

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
        placeholder="مثال:\nالدين النصيحة\nإنما الأعمال بالنيات"
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        min_sim = st.slider("٪ الحد الأدنى للتشابه (للبحث غير الصارم)", 10, 100, 50, 5)
    with col2:
        top_k = st.slider("عدد النتائج (في الوضع غير الأطلسي)", 5, 200, 30, 5)
    with col3:
        atlas_mode = st.checkbox("🧭 وضع الأطلس (عرض كل الطرق)", value=True)

    strict_all_words = st.checkbox(
        "🔒 بحث أطلسي صارم (يشترط وجود جميع كلمات الحديث)",
        value=True
    )

    search_mode = st.selectbox(
        "طريقة البحث (عند تعطيل الصرامة)",
        ["الاثنين معًا (أفضل)", "احتواء النص", "تشابه بالكلمات"],
        index=0
    )

    if st.button("ابحث", type="primary"):
        if not query.strip():
            st.warning("اكتب نصًا للبحث أولًا.")
        else:
            from rapidfuzz import fuzz

            queries = [q.strip() for q in query.split("\n") if q.strip()]
            df = df_hadith.copy()
            df["matn_norm"] = df["matn"].astype(str).apply(normalize_ar)

            all_results = []

            for q in queries:
                q_norm = normalize_ar(q)
                temp = df.copy()

                temp["contains_all"] = temp["matn"].astype(str).apply(
                    lambda x: contains_all_words(q_norm, x)
                )

                temp["contains"] = temp["matn_norm"].apply(
                    lambda x: q_norm in x
                )

                temp["similarity"] = temp["matn"].astype(str).apply(
                    lambda x: similarity_by_reference_words(q_norm, x)
                )

                if strict_all_words:
                    temp = temp[temp["contains_all"]]
                else:
                    if search_mode == "احتواء النص":
                        temp = temp[temp["contains"]]
                    elif search_mode == "تشابه بالكلمات":
                        temp = temp[temp["similarity"] >= float(min_sim)]
                    else:
                        temp = temp[
                            (temp["contains"]) |
                            (temp["similarity"] >= float(min_sim))
                        ]

                all_results.append(temp)

            results = pd.concat(all_results).drop_duplicates()

            if not atlas_mode:
                results = results.sort_values(
                    ["similarity"],
                    ascending=[False]
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
        "🔹 هذه المنصة أداة تحضير أطلسية:\n"
        "- لا تُصدر أحكام صحة أو ضعف\n"
        "- لا تفصل السند والمتن آليًا\n"
        "- تُستخدم لبناء بطاقة الحديث الأطلسية\n\n"
        "🔹 البحث الصارم هو الوضع الافتراضي لبناء وحدة الحديث.\n"
        "🔹 يمكن تعطيله للبحث الاستكشافي فقط."
    )
