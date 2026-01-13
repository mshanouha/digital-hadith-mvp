import re
import pandas as pd
import streamlit as st

# ======================================================
# CONFIG
# ======================================================
st.set_page_config(page_title="أطلس السنة – التحقيق الحديثي", layout="wide")
st.write("VERSION: ATLAS-HADITH v1.1")

# ======================================================
# SESSION STATE
# ======================================================
if "page" not in st.session_state:
    st.session_state.page = "search"

if "active_hadith" not in st.session_state:
    st.session_state.active_hadith = None

if "query_text" not in st.session_state:
    st.session_state.query_text = ""

def go_to_analysis(hadith_key):
    st.session_state.active_hadith = hadith_key
    st.session_state.page = "analysis"

def go_to_search():
    st.session_state.page = "search"

# ======================================================
# ARABIC NORMALIZATION
# ======================================================
AR_DIACRITICS = re.compile(r"[\u0617-\u061A\u064B-\u0652\u0670\u06D6-\u06ED]")

def normalize_ar(text):
    if not text:
        return ""
    text = AR_DIACRITICS.sub("", str(text))
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ى", "ي").replace("ة", "ه")
    text = re.sub(r"[^\w\s\u0600-\u06FF]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def tokenize_ar(text):
    return normalize_ar(text).split()

def contains_core(reference, candidate):
    ref_tokens = tokenize_ar(reference)
    cand_tokens = tokenize_ar(candidate)

    if not ref_tokens:
        return False

    shared = sum(1 for tok in ref_tokens if tok in cand_tokens)

    if len(ref_tokens) <= 4:
        return shared == len(ref_tokens)

    return (shared / len(ref_tokens)) >= 0.8

# ======================================================
# DATA
# ======================================================
@st.cache_data
def load_data():
    df = pd.read_csv("hadith_data.csv")
    return df

df_hadith = load_data()

# ======================================================
# SCORING & VISUALS
# ======================================================
def score_label(score):
    if score >= 9:
        return "قوي جدًا"
    elif score >= 7:
        return "قوي"
    elif score >= 5:
        return "متوسط"
    elif score >= 3:
        return "ضعيف"
    else:
        return "ضعيف جدًا"

def hadith_global_score(scores):
    if not scores:
        return 0
    max_score = max(scores)
    avg_score = sum(scores) / len(scores)
    strong = len([s for s in scores if s >= 7])
    final = (0.5 * max_score) + (0.3 * avg_score) + (0.2 * strong)
    return round(min(final, 10), 1)

def hadith_description(score):
    if score >= 9:
        return "حديث ثابت قوي جدًا"
    elif score >= 7:
        return "حديث صحيح قوي"
    elif score >= 5:
        return "حديث حسن أو متوسط القوة"
    elif score >= 3:
        return "حديث ضعيف"
    else:
        return "حديث ضعيف جدًا"

def render_color_bar(score):
    colors = [
        "#d73027", "#f46d43", "#fdae61", "#fee08b",
        "#ffffbf", "#d9ef8b", "#a6d96a", "#66bd63",
        "#1a9850", "#006837"
    ]
    active = int(round(score)) - 1
    blocks = ""
    for i, c in enumerate(colors):
        opacity = "1" if i <= active else "0.25"
        blocks += f"""
        <div style="
            width:28px;
            height:16px;
            margin:2px;
            background:{c};
            opacity:{opacity};
            display:inline-block;
            border-radius:4px;">
        </div>
        """
    st.markdown(blocks, unsafe_allow_html=True)

# ======================================================
# PAGE: SEARCH
# ======================================================
if st.session_state.page == "search":

    st.title("🔎 البحث الأطلسي عن الحديث")

    query = st.text_area(
        "نص البحث (كل حديث في سطر مستقل)",
        height=120,
        key="query_text",
        placeholder="مثال:\nإنما الأعمال بالنيات\nمن كذب علي متعمدا"
    )

    strict_core = st.checkbox("🔒 بحث أطلسي صارم (نواة الحديث ≥ 80٪)", value=True)

    if st.button("ابحث", type="primary"):
        if not query.strip():
            st.warning("اكتب نص البحث أولًا")
        else:
            queries = [q.strip() for q in query.split("\n") if q.strip()]
            results = []

            for q in queries:
                temp = df_hadith.copy()
                temp["match"] = temp["matn"].apply(lambda x: contains_core(q, x))
                if strict_core:
                    temp = temp[temp["match"]]
                results.append(temp)

            results = pd.concat(results).drop_duplicates()

            if results.empty:
                st.error("لا توجد نتائج")
            else:
                st.success(f"تم العثور على {results['hadith_key'].nunique()} وحدة حديثية")

                for hadith_key, grp in results.groupby("hadith_key"):
                    with st.expander(f"🧭 وحدة حديث: {hadith_key}", expanded=False):
                        st.write("📌 المتن المرجعي:")
                        st.write(grp.iloc[0]["matn"])
                        st.write(f"عدد الروايات: {len(grp)}")
                        st.button(
                            "🔎 الانتقال إلى التحقيق الحديثي",
                            key=f"analyze_{hadith_key}",
                            on_click=go_to_analysis,
                            args=(hadith_key,)
                        )

# ======================================================
# PAGE: ANALYSIS
# ======================================================
if st.session_state.page == "analysis":

    hadith_key = st.session_state.active_hadith
    st.title(f"🧭 التحقيق الحديثي – {hadith_key}")

    data = df_hadith[df_hadith["hadith_key"] == hadith_key]

    st.subheader("📌 النص النووي")
    st.write(data.iloc[0]["matn"])

    st.markdown("---")
    st.subheader("🧵 تقييم الطرق السندية (طرق حقيقية)")

    scores = []

    for isnad, group in data.groupby("isnad"):
        st.markdown(f"**السند:** {isnad}")
        st.write(f"عدد الروايات في هذا الطريق: {len(group)}")

        score = st.slider(
            "درجة الطريق (0–10)",
            0, 10, 7,
            key=f"score_{isnad}"
        )

        st.write(f"التوصيف: {score_label(score)}")
        scores.append(score)
        st.markdown("---")

    final_score = hadith_global_score(scores)

    st.subheader("📊 المؤشر النهائي للحديث")
    st.write(f"الدرجة: {final_score} / 10")
    render_color_bar(final_score)
    st.write(hadith_description(final_score))

    st.markdown("---")
    verdict = st.selectbox(
        "الحكم الحديثي النهائي",
        ["صحيح قطعي", "صحيح", "حسن", "مختلف فيه", "ضعيف"]
    )

    notes = st.text_area("📝 خلاصة التحقيق")

    if st.button("↩️ العودة إلى البحث"):
        go_to_search()
