import re
import streamlit as st

st.set_page_config(page_title="خوارزمية التحقيق الرقمي - MVP", layout="wide")

# ---------- Helpers ----------
AR_DIACRITICS = re.compile(r"[\u0617-\u061A\u064B-\u0652\u0670\u06D6-\u06ED]")

def normalize_ar(text: str) -> str:
    """Normalize Arabic: remove diacritics, unify alef/yaa/taa marbuta, remove punctuation, trim spaces."""
    if not text:
        return ""
    text = text.strip()
    text = AR_DIACRITICS.sub("", text)
    # unify letters
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ى", "ي").replace("ة", "ه")
    # remove punctuation
    text = re.sub(r"[^\w\s\u0600-\u06FF]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def tokenize_ar(text: str):
    text = normalize_ar(text)
    if not text:
        return []
    return text.split()

def similarity_by_reference_words(reference: str, candidate: str) -> float:
    """
    Similarity% = (shared words count ÷ total words in reference) × 100
    shared counted as unique word overlap (set-based) to keep it simple for MVP.
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

def parse_narrators(input_text: str):
    """
    Expect lines like:
    الراوي, 90
    or
    الراوي | 90
    or
    الراوي: 90
    """
    narrators = []
    for line in (input_text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        # split by common delimiters
        parts = re.split(r"[,\|\:؛\t]+", line)
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) < 2:
            continue
        name = parts[0]
        try:
            score = float(parts[1])
        except:
            continue
        score = max(0.0, min(100.0, score))
        narrators.append((name, score))
    return narrators

def path_grade_multiplicative(narrators):
    """
    Path Grade = Π(score/100) × 100
    """
    if not narrators:
        return 0.0
    product = 1.0
    for _, s in narrators:
        product *= (s / 100.0)
    return product * 100.0

# ---------- UI ----------
st.title("🧮 خوارزمية التحقيق الرقمي للإسناد والمتن — نموذج أولي (MVP)")

col1, col2 = st.columns(2)

with col1:
    st.subheader("1) حساب درجة السند (الضرب الاحتمالي)")
    st.caption("اكتب كل راوٍ في سطر: الاسم ثم الدرجة من 1 إلى 100. مثال: ابن جريج, 85")
    narrators_text = st.text_area(
        "قائمة الرواة + الدرجات",
        height=220,
        placeholder="الصحابي, 100\nراوي 2, 90\nراوي 3, 85\n..."
    )

    narrators = parse_narrators(narrators_text)

    if narrators:
        st.write("**الرواة المُدخلون:**")
        for n, s in narrators:
            st.write(f"- {n} — {s}")
        pg = path_grade_multiplicative(narrators)
        st.metric("Path Grade (درجة الطريق)", f"{pg:.2f} / 100")
    else:
        st.info("أدخل الرواة بالصيغة: الاسم, الدرجة")

with col2:
    st.subheader("2) نسبة التشابه اللفظي (بالكلمات المشتركة)")
    st.caption("Similarity% = (الكلمات المشتركة ÷ كلمات المتن المرجعي) × 100 — نسخة MVP مبسطة")
    ref_text = st.text_area("المتن المرجعي", height=120, placeholder="اكتب المتن المرجعي هنا...")
    cand_text = st.text_area("المتن المقارن", height=120, placeholder="اكتب المتن المقارن هنا...")

    if ref_text.strip():
        sim = similarity_by_reference_words(ref_text, cand_text)
        st.metric("Similarity % (نسبة التشابه)", f"{sim:.2f}%")
    else:
        st.info("أدخل المتن المرجعي لحساب التشابه.")

st.divider()

st.subheader("3) النتيجة النهائية (مقترحة)")
st.caption("Final Score = Path Grade × (Similarity%/100) — ويمكن لاحقًا تطويرها بإضافة كشف الإدراج/الزيادات.")

if narrators and ref_text.strip():
    pg = path_grade_multiplicative(narrators)
    sim = similarity_by_reference_words(ref_text, cand_text)
    final_score = pg * (sim / 100.0)
    c1, c2, c3 = st.columns(3)
    c1.metric("Path Grade", f"{pg:.2f}")
    c2.metric("Similarity %", f"{sim:.2f}%")
    c3.metric("Final Score", f"{final_score:.2f} / 100")
else:
    st.warning("لإظهار Final Score: أدخل الرواة والدرجات + المتن المرجعي والمتن المقارن.")
