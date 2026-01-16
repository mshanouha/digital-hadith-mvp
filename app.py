import re
import pandas as pd
import streamlit as st

# ======================================================
# CONFIG
# ======================================================
st.set_page_config(page_title="أطلس السنة", layout="wide")
st.write("VERSION: ATLAS-HADITH v1.5")

# ======================================================
# SESSION STATE
# ======================================================
if "page" not in st.session_state:
    st.session_state.page = "search"

if "active_hadith" not in st.session_state:
    st.session_state.active_hadith = None

if "similar_results" not in st.session_state:
    st.session_state.similar_results = None


def go(page):
    st.session_state.page = page
    st.rerun()

# ======================================================
# ROUTING (VERY IMPORTANT)
# ======================================================
def route():
    if st.session_state.page == "search":
        page_search()
        st.stop()
    elif st.session_state.page == "unit":
        page_unit()
        st.stop()
    elif st.session_state.page == "analysis":
        page_analysis()
        st.stop()

# ======================================================
# NORMALIZATION
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
# ISNAD
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
# STRICT CORE MATCH (ONLY FOR ANALYSIS)
# ======================================================
def contains_core(reference, candidate):
    ref_tokens = tokenize_ar(reference)
    cand_tokens = tokenize_ar(candidate)
    if not ref_tokens:
        return False
    shared = sum(1 for t in ref_tokens if t in cand_tokens)
    if len(ref_tokens) <= 4:
        return shared >= len(ref_tokens) - 1
    return (shared / len(ref_tokens)) >= 0.8

# ======================================================
# DATA
# ======================================================
@st.cache_data
def load_data():
    df = pd.read_csv("hadith_data.csv")
    df["matn_norm"] = df["matn"].apply(normalize_ar)
    df["isnad_norm"] = df["isnad"].apply(normalize_isnad)
    return df

df = load_data()

# ======================================================
# VISUAL BAR (NON INTERACTIVE)
# ======================================================
def render_bar(score):
    colors = [
        "#d73027", "#f46d43", "#fdae61", "#fee08b",
        "#ffffbf", "#d9ef8b", "#a6d96a", "#66bd63",
        "#1a9850", "#006837"
    ]
    active = int(round(score)) - 1
    html = ""
    for i, c in enumerate(colors):
        opacity = "1" if i <= active else "0.25"
        html += f"""
        <div style="
            width:24px;
            height:14px;
            background:{c};
            opacity:{opacity};
            display:inline-block;
            margin:2px;
            border-radius:4px;">
        </div>
        """
    st.markdown(html, unsafe_allow_html=True)

# ======================================================
# PAGE 1 — SEARCH
# ======================================================
def page_search():
    st.title("🔍 البحث عن الحديث")
    st.write("بحث لغوي عام: أدخل كلمة أو أكثر (يجب أن تجتمع الكلمات معًا).")

    query = st.text_input("نص البحث")

    if st.button("ابحث", type="primary"):
        query = query.strip()

        if not query:
            st.warning("أدخل كلمة واحدة على الأقل")
            return

        tokens = tokenize_ar(query)

        if not tokens:
            st.warning("النص غير صالح للبحث")
            return

        # =========================
        # AND SEARCH (all words)
        # =========================
        results = df.copy()
        for tok in tokens:
            results = results[
                results["matn_norm"].str.contains(tok, regex=False)
            ]

        if results.empty:
            st.info("🔍 لم توجد عبارة كاملة، تم البحث بالكلمات المفردة")

            # fallback OR search (اختياري)
            pattern = "|".join(tokens)
            results = df[df["matn_norm"].str.contains(pattern, regex=True)]

            if results.empty:
                st.error("لا توجد نتائج")
                return

        else:
            st.success("🔎 تم العثور على نتائج مطابقة للعبارة كاملة")

        # =========================
        # عرض النتائج
        # =========================
        for key, grp in results.groupby("hadith_key"):
            with st.expander(f"🧭 حديث: {key}"):
                st.write(grp.iloc[0]["matn"])

                if st.button("🧭 اختيار هذا الحديث", key=f"sel_{key}"):
                    st.session_state.active_hadith = key
                    st.session_state.page = "unit"
                    st.rerun()



# ======================================================
# PAGE 2 — HADITH UNIT
# ======================================================
def page_unit():
    key = st.session_state.active_hadith
    data = df[df["hadith_key"] == key]

    st.title(f"🧭 وحدة الحديث – {key}")
    st.markdown("### 📌 المتن المرجعي")
    st.write(data.iloc[0]["matn"])

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔎 البحث عن المتشابه"):
            ref = data.iloc[0]["matn"]
            sim = df[df["matn"].apply(lambda x: contains_core(ref, x))]
            st.session_state.similar_results = sim
            go("analysis")

    with col2:
        if st.button("📊 الانتقال إلى التحقيق"):
            st.session_state.similar_results = data
            go("analysis")

    st.markdown("---")
    if st.button("↩️ العودة للبحث"):
        go("search")

# ======================================================
# PAGE 3 — ANALYSIS
# ======================================================
def page_analysis():
    data = st.session_state.similar_results

    st.title("🔬 التحقيق الحديثي والمتشابه")

    scores = []

    for isnad, grp in data.groupby("isnad_norm"):
        st.markdown(f"**السند:** {isnad}")
        score = st.selectbox(
            "درجة الطريق (0–10)",
            list(range(11)),
            index=7,
            key=f"s_{isnad}"
        )
        render_bar(score)
        scores.append(score)
        st.markdown("---")

    if scores:
        final = round(sum(scores) / len(scores), 1)
        st.subheader("📊 المؤشر النهائي للحديث")
        st.write(f"الدرجة: {final} / 10")
        render_bar(final)

    if st.button("↩️ العودة لوحدة الحديث"):
        go("unit")

# ======================================================
# RUN APP
# ======================================================
route()
