import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="Address Risk Scanner", layout="wide")

st.title("📦 Address Risk Scanner Dashboard")

# =========================
# FILE UPLOAD
# =========================
uploaded_file = st.file_uploader("Upload Orders CSV", type=["csv"])

if uploaded_file:

    df = pd.read_csv(uploaded_file)
    df.fillna("", inplace=True)

    # =========================
    # SAME LOGIC (UNCHANGED)
    # =========================
    df["full_address"] = (
        df["Shipping Address Line 1"].astype(str) + " " +
        df["Shipping Address Line 2"].astype(str) + " " +
        df["City, State"].astype(str)
    )

    df["word_count"] = df["Shipping Address Line 1"].apply(
        lambda x: len(str(x).split())
    )

    median_word_count = df["word_count"].median()

    def has_fake_words(text):
        return bool(re.search(r"\b(test|asdf|xxxx|na|none)\b", text.lower()))

    def has_repeated_chars(text):
        return bool(re.search(r"(.)\1{4,}", text))

    def has_number(text):
        return any(char.isdigit() for char in text)

    def is_suspicious_phone(phone):
        phone = str(phone)
        if not phone.isdigit() or len(phone) != 10:
            return True
        if len(set(phone)) == 1:
            return True
        if phone in ["1234567890", "0987654321"]:
            return True
        return False

    def is_valid_pincode(pin):
        pin = str(pin)
        if not pin.isdigit() or len(pin) != 6:
            return False
        if len(set(pin)) == 1:
            return False
        return True

    def landmark_score(text):
        keywords = ["near", "behind", "opposite", "beside", "landmark"]
        return sum(1 for k in keywords if k in text.lower())

    def is_suspicious_name(name):
        name = str(name).lower()
        if len(name) < 3:
            return True
        if name in ["test", "abc", "xyz"]:
            return True
        return False

    df["phone_count"] = df["Customer Mobile"].map(df["Customer Mobile"].value_counts())

    def risk_logic(row):

        address = row["full_address"]
        wc = row["word_count"]
        payment = str(row["Pymt"]).upper()

        if wc < 5:
            return "JUNK", 10, "Very low word count (<5)"

        score = 0
        reasons = []

        if payment == "PREPAID":
            if wc <= 4:
                score += 2
                reasons.append("Low word count (PREPAID)")
        else:
            if wc < median_word_count:
                score += 2
                reasons.append("Below median word count (COD)")

        if has_fake_words(address):
            score += 3
            reasons.append("Fake words")

        if has_repeated_chars(address):
            score += 2
            reasons.append("Repeated characters")

        if not has_number(address):
            score += 2
            reasons.append("No numeric detail")

        if is_suspicious_phone(row["Customer Mobile"]):
            score += 3
            reasons.append("Suspicious phone")

        if not is_valid_pincode(row["Pincode"]):
            score += 3
            reasons.append("Invalid pincode")

        if landmark_score(address) >= 2:
            score += 2
            reasons.append("Too many landmarks")

        if is_suspicious_name(row["Customer Name"]):
            score += 2
            reasons.append("Suspicious name")

        if row["phone_count"] > 3:
            score += 2
            reasons.append("Repeated phone number")

        if payment == "COD":
            score += 1

        if score >= 5:
            return "JUNK", score, ", ".join(reasons)
        elif score >= 3:
            return "SUSPICIOUS", score, ", ".join(reasons)
        else:
            return "OK", score, ", ".join(reasons)

    df[["risk_flag", "risk_score", "reasons"]] = df.apply(
        lambda row: pd.Series(risk_logic(row)), axis=1
    )

    # =========================
    # ✅ DEBUG (VERY IMPORTANT)
    # =========================
    st.write("### 📊 Risk Distribution")
    st.write(df["risk_flag"].value_counts())

    # =========================
    # ✅ MATCH YOUR SCRIPT OUTPUT
    # =========================
    risky_df = df[df["risk_flag"].isin(["JUNK", "SUSPICIOUS"])]

    risky_df = risky_df[[
        "Display Order #",
        "Products",
        "Customer Name",
        "Customer Mobile",
        "Shipping Address Line 1",
        "Shipping Address Line 2",
        "City, State",
        "Pincode",
        "Pymt",
        "word_count",
        "risk_score",
        "risk_flag",
        "reasons"
        # "full_address"
    ]]

    # SORT LIKE YOUR SCRIPT
    risky_df = risky_df.sort_values(by="risk_score", ascending=False)

    # =========================
    # FILTERS
    # =========================
    st.sidebar.header("Filters")

    risk_filter = st.sidebar.multiselect(
        "Risk Type",
        ["JUNK", "SUSPICIOUS"],
        default=["JUNK", "SUSPICIOUS"]
    )

    payment_filter = st.sidebar.multiselect(
        "Payment Type",
        options=risky_df["Pymt"].unique(),
        default=risky_df["Pymt"].unique()
    )

    filtered_df = risky_df[
        (risky_df["risk_flag"].isin(risk_filter)) &
        (risky_df["Pymt"].isin(payment_filter))
    ]

    # =========================
    # METRICS
    # =========================
    col1, col2, col3 = st.columns(3)

    col1.metric("Total Orders", len(df))
    col2.metric("Risky Orders", len(risky_df))
    col3.metric("High Risk (JUNK)", len(risky_df[risky_df["risk_flag"] == "JUNK"]))

    # =========================
    # TABLE
    # =========================
    st.subheader(f"📋 Orders to Review ({len(filtered_df)})")

    st.dataframe(filtered_df, use_container_width=True)

    # =========================
    # DOWNLOAD
    # =========================
    csv = filtered_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "⬇ Download Filtered Data",
        csv,
        "filtered_risky_orders.csv",
        "text/csv"
    )

else:
    st.info("Please upload a CSV file to proceed.")
