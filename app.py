import re
import pandas as pd
import streamlit as st

# ======================================================
# CONFIG
# ======================================================
st.set_page_config(page_title="أطلس السنة – التحقيق الحديثي", layout="wide")
st.write("VERSION: ATLAS-HADITH v1.3")

# ======================================================
# SESSION STATE
# ======================================================
if "page" not in st.session_state:
    st.session_state.page = "search"

if "active_hadith" not in st.session_state:
    st.session_state.active_hadith = None

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

# ======================================================
# ISNAD NORMALIZATION
# ======================================================
def normalize_isnad(isnad):
    if not isnad or pd.isna(isnad):
        return None
    isnad = normalize_ar(isnad)
    for w in ["حدثنا", "اخبرنا", "قال", "سمعت", "عن"]:
        isnad = isnad.replace(w, "")
    isnad = re.sub(r"\s+", " ", isnad)
    return isnad.strip()

# ======================================================
# CORE MATCHING
# ======================================================
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
    df["isnad_norm"] = df["isnad"].apply(normalize_isnad)
    df = df[df["isnad_norm"].notna()]
    return df

df = load_data()

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
        return None
    max_score = max(scores)
    avg_score = sum(scores) / len(scores)
    n = len(scores)
    reference_bonus = 1 if (n == 1 and max_score >= 8) else 0
    final = (
        0.6 * max_score +
        0.3 * avg_score +
        0.1 * min(n, 5) +
        reference_bonus
    )
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
            width:26px;
            height:14px;
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
    query = st.text_area("نص البحث (كل حديث في سطر مستقل)", height=120)

    if st.button("ابحث", type="primary"):
        if not query.strip():
            st.warning("اكتب نص البحث أولًا")
        else:
            results = []
            for q in query.split("\n"):
                q = q.strip()
                if not q:
                    continue
                temp = df.copy()
                temp["match"] = temp["matn"].apply(lambda x: contains_core(q, x))
                temp = temp[temp["match"]]
                results.append(temp)

            results = pd.concat(results).drop_duplicates()
            if results.empty:
                st.error("لا توجد نتائج")
            else:
                for key, grp in results.groupby("hadith_key"):
                    with st.expander(f"🧭 وحدة حديث: {key}"):
                        st.write(grp.iloc[0]["matn"])
                        st.button(
                            "🔎 الانتقال إلى التحقيق",
                            key=f"an_{key}",
                            on_click=go_to_analysis,
                            args=(key,)
                        )

# ======================================================
# PAGE: ANALYSIS
# ======================================================
if st.session_state.page == "analysis":

    key = st.session_state.active_hadith
    data = df[df["hadith_key"] == key]

    st.title(f"🧭 التحقيق الحديثي – {key}")
    st.write(data.iloc[0]["matn"])

    st.markdown("---")
    st.subheader("🧵 تقييم الطرق السندية")

    scores = []

    for isnad, grp in data.groupby("isnad_norm"):
        st.markdown(f"**السند:** {isnad}")
        score = st.selectbox(
            "درجة الطريق",
            list(range(0, 11)),
            index=7,
            key=f"score_{isnad}"
        )
        render_color_bar(score)
        st.write(f"التوصيف: {score_label(score)}")
        scores.append(score)
        st.markdown("---")

    final = hadith_global_score(scores)

    if final is None:
        st.warning("لا يمكن حساب المؤشر النهائي")
    else:
        st.subheader("📊 المؤشر النهائي للحديث")
        st.write(f"الدرجة: {final} / 10")
        render_color_bar(final)
        st.write(hadith_description(final))

    st.markdown("---")
    st.selectbox("الحكم الحديثي النهائي", ["صحيح قطعي", "صحيح", "حسن", "مختلف فيه", "ضعيف"])
    st.text_area("خلاصة التحقيق")

    if st.button("↩️ العودة للبحث"):
        go_to_search()
