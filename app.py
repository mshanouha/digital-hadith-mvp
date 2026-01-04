import re
import pandas as pd
import streamlit as st
st.write("VERSION: TAB-SEARCH v0.2")
st.set_page_config(page_title="منصة التحقيق الرقمي - MVP", layout="wide")

# ----------------- Arabic helpers -----------------
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
    """
    Similarity% = (الكلمات المشتركة ÷ كلمات المتن المرجعي) × 100
    MVP: تقاطع مجموعات كلمات (unique overlap)
    """
    ref_tokens = tokenize_ar(reference)
    cand_tokens = tokenize_ar(candidate)
    if not ref_tokens:
        return 0.0
    ref_set = set(ref_tokens)
    cand_set = set(cand_tokens)
    shared = len(ref_set.intersection(cand_set))
    total = len(ref_set)
    return (shared / total) * 100.0

# ----------------- Data loading -----------------
@st.cache_data
def load_hadith_data():
    """
    Loads hadith data from hadith_data.csv if exists.
    If not exists, uses a tiny built-in sample so the app works immediately.
    """
    try:
        df = pd.read_csv("hadith_data.csv")
        # expected columns
        needed = {"hadith_key", "source", "ref", "isnad", "matn"}
        missing = needed - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns in hadith_data.csv: {missing}")
        return df
    except Exception:
        # fallback tiny sample
        sample = [
            {
                "hadith_key": "H001",
                "source": "عينة",
                "ref": "1",
                "isnad": "فلان عن فلان عن عرفجه",
                "matn": "اصيب انفه فاتخذ انفا من ورق فانتن عليه فامره النبي ان يتخذ انفا من ذهب"
            },
            {
                "hadith_key": "H001",
                "source": "عينة",
                "ref": "2",
                "isnad": "فلان عن فلان عن عرفجه (طريق آخر)",
                "matn": "اصيب انفه فاتخذ انفا من ورق فانتن عليه فامر النبي ان يتخذ انفا من ذهب"
            },
            {
                "hadith_key": "H002",
                "source": "عينة",
                "ref": "3",
                "isnad": "فلان عن فلان",
                "matn": "انما الاعمال بالنيات وانما لكل امرئ ما نوى"
            },
        ]
        return pd.DataFrame(sample)

df_hadith = load_hadith_data()

# ----------------- UI -----------------
st.title("📚 منصة التحقيق الرقمي للإسناد والمتن — MVP")

tab1, tab2, tab3 = st.tabs(["🔎 البحث عن الحديث", "🧾 تقييم الرواة (قيد التطوير)", "📦 الكتب الحديثية (قيد التطوير)"])

# ============ TAB 1: SEARCH ============
with tab1:
    st.subheader("🔎 البحث عن الحديث بكل طرقه")
    st.caption("اكتب المتن (أو جزءًا منه). سيعرض النظام النتائج الأقرب، ويجمع الطرق المتعددة تحت نفس الحديث.")

    query = st.text_area("نص البحث (المتن)", height=120, placeholder="مثال: أصيب أنفه فاتخذ أنفًا من ورق...")

    colA, colB, colC = st.columns(3)
    with colA:
        min_sim = st.slider("الحد الأدنى للتشابه %", 10, 100, 50, 5)
    with colB:
        top_k = st.slider("عدد النتائج (الطرق) المعروضة", 5, 200, 30, 5)
    with colC:
        group_view = st.checkbox("تجميع النتائج حسب الحديث (عرض كل الطرق)", value=True)

    if st.button("ابحث", type="primary"):
        q = query.strip()
        if not q:
            st.warning("اكتب نصًا للبحث أولًا.")
        else:
            # compute similarity against each matn row
            sims = []
            q_norm = normalize_ar(q)
            for idx, row in df_hadith.iterrows():
                matn = str(row["matn"])
                sim = similarity_by_reference_words(q_norm, matn)
                sims.append(sim)

            results = df_hadith.copy()
            results["similarity"] = sims
            results = results.sort_values("similarity", ascending=False)

            # filter and limit
            results = results[results["similarity"] >= float(min_sim)].head(int(top_k))

            if results.empty:
                st.error("لا توجد نتائج ضمن حد التشابه المحدد. جرّب تخفيض الحد الأدنى.")
            else:
                st.success(f"تم العثور على {len(results)} طريق/رواية ضمن التشابه ≥ {min_sim}%")

                if group_view:
                    # group by hadith_key to show all paths
                    for hadith_key, grp in results.groupby("hadith_key"):
                        best = grp.iloc[0]
                        header = f"حديث: {hadith_key} — أفضل تشابه: {best['similarity']:.2f}%"
                        with st.expander(header, expanded=True):
                            st.write(f"**المتن (أقرب نتيجة):** {best['matn']}")
                            st.write(f"**عدد الطرق المعروضة لهذا الحديث:** {len(grp)}")
                            st.divider()
                            for _, r in grp.iterrows():
                                st.markdown(
                                    f"- **المصدر:** {r['source']} | **المرجع:** {r['ref']} | **التشابه:** {r['similarity']:.2f}%\n"
                                    f"  - **السند:** {r['isnad']}\n"
                                    f"  - **المتن:** {r['matn']}"
                                )
                else:
                    # flat view
                    for _, r in results.iterrows():
                        st.markdown(
                            f"**{r['source']} — {r['ref']}** | التشابه: **{r['similarity']:.2f}%**\n\n"
                            f"- السند: {r['isnad']}\n"
                            f"- المتن: {r['matn']}\n"
                            "---"
                        )

    st.divider()
    st.info(
        "📌 لإضافة بياناتك الحقيقية: ضع ملف باسم **hadith_data.csv** داخل المستودع بنفس الأعمدة:\n"
        "`hadith_key, source, ref, isnad, matn`\n"
        "وسيعتمد عليه التطبيق تلقائيًا."
    )

# ============ TAB 2 Placeholder ============
with tab2:
    st.subheader("🧾 تقييم الرواة (قيد التطوير)")
    st.write("سنضيف هنا لاحقًا: تقييم الرواة لكل طريق + النتيجة المركبة + مقارنة الطرق.")

# ============ TAB 3 Placeholder ============
with tab3:
    st.subheader("📦 الكتب الحديثية (قيد التطوير)")
    st.write("سنضيف هنا لاحقًا: بطاقة الكتاب الحديثية والإحصاءات (عدد الأحاديث/الأسانيد/المتون/المكرر...).")

