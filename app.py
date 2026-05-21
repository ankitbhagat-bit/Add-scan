import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="Address Risk Scanner", layout="wide")

st.title("Address Risk Scanner")

# =====================================================
# HELPERS
# =====================================================

def clean_text(value):
    if pd.isna(value):
        return ""
    value = str(value)
    value = value.replace("`", "").replace("'", "").strip()
    return value


def clean_phone(value):
    value = clean_text(value)
    value = re.sub(r"\D", "", value)

    # If phone got exported as 919876543210, keep last 10 digits
    if len(value) > 10:
        value = value[-10:]

    return value


def clean_pincode(value):
    value = clean_text(value)
    value = re.sub(r"\D", "", value)

    # Keep first 6 digits only
    if len(value) > 6:
        value = value[:6]

    return value


def normalize_payment(value):
    value = clean_text(value).upper()

    if "COD" in value or "CASH ON DELIVERY" in value:
        return "COD"

    if "PREPAID" in value or "PREPAID" in value.replace(" ", ""):
        return "PREPAID"

    if "PAID" in value and "PENDING" not in value:
        return "PREPAID"

    if "PENDING" in value:
        return "COD"

    return value if value else "UNKNOWN"


def safe_col(df, col_name, default=""):
    if col_name in df.columns:
        return df[col_name].apply(clean_text)
    return pd.Series([default] * len(df))


def combine_cols(df, cols):
    available_cols = [col for col in cols if col in df.columns]

    if not available_cols:
        return pd.Series([""] * len(df))

    combined = df[available_cols].fillna("").astype(str).agg(" ".join, axis=1)
    return combined.apply(clean_text)


# =====================================================
# FORMAT MAPPERS
# =====================================================

def map_unicommerce(df):
    """
    Your current Unicommerce structure.
    """

    mapped = pd.DataFrame()

    mapped["order_id"] = safe_col(df, "Display Order #")
    mapped["cx_name"] = safe_col(df, "Customer Name")
    mapped["cx_mobile"] = safe_col(df, "Customer Mobile").apply(clean_phone)
    mapped["cx_email"] = safe_col(df, "Customer Email") if "Customer Email" in df.columns else ""
    mapped["shopify_tags"] = safe_col(df, "ShopifyTags")
    mapped["product_sku"] = safe_col(df, "SKU") if "SKU" in df.columns else safe_col(df, "Products")
    mapped["product_name"] = safe_col(df, "Products")
    mapped["address_line_1"] = safe_col(df, "Shipping Address Line 1")
    mapped["address_line_2"] = safe_col(df, "Shipping Address Line 2")
    mapped["city_state"] = safe_col(df, "City, State")
    mapped["address"] = combine_cols(
        df,
        [
            "Shipping Address Line 1",
            "Shipping Address Line 2",
            "City, State"
        ]
    )
    mapped["pincode"] = safe_col(df, "Pincode").apply(clean_pincode)
    mapped["payment_method"] = safe_col(df, "Pymt").apply(normalize_payment)
    mapped["quantity"] = pd.to_numeric(safe_col(df, "Quantity", 1), errors="coerce").fillna(1).astype(int)
    mapped["order_price"] = pd.to_numeric(safe_col(df, "Order Price", 0), errors="coerce").fillna(0)

    return mapped


def map_easyecom(df):
    """
    EasyEcom structure shared by you.
    """

    mapped = pd.DataFrame()

    mapped["order_id"] = safe_col(df, "Order Number")
    mapped["cx_name"] = ""
    mapped["cx_mobile"] = ""
    mapped["cx_email"] = ""
    mapped["shopify_tags"] = ""
    mapped["product_sku"] = safe_col(df, "SKU")
    mapped["product_name"] = safe_col(df, "Product Name")
    mapped["address_line_1"] = ""
    mapped["address_line_2"] = ""
    mapped["city_state"] = combine_cols(df, ["Shipping City", "Shipping State"])
    mapped["address"] = combine_cols(df, ["Shipping City", "Shipping State", "Shipping Postal code"])
    mapped["pincode"] = safe_col(df, "Shipping Postal code").apply(clean_pincode)
    mapped["payment_method"] = safe_col(df, "Payment Status").apply(normalize_payment)
    mapped["quantity"] = pd.to_numeric(safe_col(df, "Quantity", 1), errors="coerce").fillna(1).astype(int)
    mapped["order_price"] = pd.to_numeric(safe_col(df, "Payment Amount", 0), errors="coerce").fillna(0)

    return mapped


def map_shopify(df):
    """
    Shopify export structure shared by you.
    """

    mapped = pd.DataFrame()

    mapped["order_id"] = safe_col(df, "Name")
    mapped["cx_name"] = safe_col(df, "Shipping Name")
    mapped["cx_mobile"] = safe_col(df, "Shipping Phone").apply(clean_phone)

    # fallback if Shipping Phone is empty
    billing_phone = safe_col(df, "Billing Phone").apply(clean_phone)
    phone = safe_col(df, "Phone").apply(clean_phone)

    mapped["cx_mobile"] = mapped["cx_mobile"].where(mapped["cx_mobile"] != "", billing_phone)
    mapped["cx_mobile"] = mapped["cx_mobile"].where(mapped["cx_mobile"] != "", phone)

    mapped["cx_email"] = safe_col(df, "Email")
    mapped["shopify_tags"] = safe_col(df, "Tags")
    mapped["product_sku"] = safe_col(df, "Lineitem sku")
    mapped["product_name"] = safe_col(df, "Lineitem name")

    mapped["address_line_1"] = safe_col(df, "Shipping Address1")
    mapped["address_line_2"] = safe_col(df, "Shipping Address2")
    mapped["city_state"] = combine_cols(df, ["Shipping City", "Shipping Province"])

    mapped["address"] = combine_cols(
        df,
        [
            "Shipping Address1",
            "Shipping Address2",
            "Shipping City",
            "Shipping Province",
            "Shipping Country"
        ]
    )

    mapped["pincode"] = safe_col(df, "Shipping Zip").apply(clean_pincode)
    mapped["payment_method"] = safe_col(df, "Payment Method").apply(normalize_payment)

    # fallback from shipping method if payment method is empty
    shipping_method_payment = safe_col(df, "Shipping Method").apply(normalize_payment)
    mapped["payment_method"] = mapped["payment_method"].where(
        mapped["payment_method"] != "UNKNOWN",
        shipping_method_payment
    )

    mapped["quantity"] = pd.to_numeric(safe_col(df, "Lineitem quantity", 1), errors="coerce").fillna(1).astype(int)
    mapped["order_price"] = pd.to_numeric(safe_col(df, "Total", 0), errors="coerce").fillna(0)

    return mapped


def standardize_file(df, file_type):
    if file_type == "Unicommerce":
        return map_unicommerce(df)

    if file_type == "EasyEcom":
        return map_easyecom(df)

    if file_type == "Shopify":
        return map_shopify(df)

    return df


# =====================================================
# RISK LOGIC
# =====================================================

def has_fake_words(text):
    return bool(re.search(r"\b(test|asdf|xxxx|na|none|null|dummy|sample)\b", str(text).lower()))


def has_repeated_chars(text):
    return bool(re.search(r"(.)\1{4,}", str(text)))


def has_number(text):
    return any(char.isdigit() for char in str(text))


def is_suspicious_phone(phone):
    phone = clean_phone(phone)

    if not phone.isdigit() or len(phone) != 10:
        return True

    if len(set(phone)) == 1:
        return True

    if phone in ["1234567890", "0987654321", "9876543210"]:
        return True

    return False


def is_valid_pincode(pin):
    pin = clean_pincode(pin)

    if not pin.isdigit() or len(pin) != 6:
        return False

    if len(set(pin)) == 1:
        return False

    return True


def landmark_score(text):
    keywords = [
        "near",
        "behind",
        "opposite",
        "beside",
        "landmark",
        "in front",
        "front of",
        "next to",
        "besides",
        "samne",
        "pass",
        "paas",
        "ke paas"
    ]

    text = str(text).lower()
    return sum(1 for keyword in keywords if keyword in text)


def is_suspicious_name(name):
    name = str(name).lower().strip()

    if name == "":
        return False

    if len(name) < 3:
        return True

    if name in ["test", "abc", "xyz", "dummy", "sample"]:
        return True

    if has_repeated_chars(name):
        return True

    return False


def risk_logic(row, median_word_count):
    address = str(row["address"])
    wc = row["word_count"]
    payment = str(row["payment_method"]).upper()

    if wc < 3:
        return "JUNK", 10, "Very low address word count (<3)"

    score = 0
    reasons = []

    if payment == "PREPAID":
        if wc <= 4:
            score += 2
            reasons.append("Low word count for prepaid order")
    else:
        if wc < median_word_count:
            score += 2
            reasons.append("Below median address word count for COD order")

    if has_fake_words(address):
        score += 3
        reasons.append("Fake words in address")

    if has_repeated_chars(address):
        score += 2
        reasons.append("Repeated characters in address")

    if not has_number(address):
        score += 2
        reasons.append("No numeric detail in address")

    if is_suspicious_phone(row["cx_mobile"]):
        score += 3
        reasons.append("Suspicious or missing phone number")

    if not is_valid_pincode(row["pincode"]):
        score += 3
        reasons.append("Invalid pincode")

    if landmark_score(address) >= 2:
        score += 2
        reasons.append("Too many landmark-style words")

    if is_suspicious_name(row["cx_name"]):
        score += 2
        reasons.append("Suspicious customer name")

    if row["phone_count"] > 3:
        score += 2
        reasons.append("Repeated phone number across multiple orders")

    if payment == "COD":
        score += 1
        reasons.append("COD order")

    if score >= 5:
        return "JUNK", score, ", ".join(reasons)

    elif score >= 3:
        return "SUSPICIOUS", score, ", ".join(reasons)

    else:
        return "OK", score, ", ".join(reasons)


# =====================================================
# TOP SELECTOR
# =====================================================

file_type = st.radio(
    "Select CSV Format",
    ["Unicommerce", "EasyEcom", "Shopify"],
    horizontal=True
)

uploaded_file = st.file_uploader(
    f"Upload {file_type} Orders CSV",
    type=["csv"]
)

if uploaded_file:

    try:
        raw_df = pd.read_csv(uploaded_file, dtype=str)
    except UnicodeDecodeError:
        raw_df = pd.read_csv(uploaded_file, dtype=str, encoding="latin1")

    raw_df.fillna("", inplace=True)

    st.write("Uploaded file preview")
    st.dataframe(raw_df.head(5), use_container_width=True)

    df = standardize_file(raw_df, file_type)
    df.fillna("", inplace=True)

    # =====================================================
    # REQUIRED STANDARD COLUMNS
    # =====================================================

    df["address"] = df["address"].apply(clean_text)
    df["cx_mobile"] = df["cx_mobile"].apply(clean_phone)
    df["pincode"] = df["pincode"].apply(clean_pincode)
    df["payment_method"] = df["payment_method"].apply(normalize_payment)

    df["word_count"] = df["address"].apply(lambda x: len(str(x).split()))
    median_word_count = df["word_count"].median()

    if pd.isna(median_word_count):
        median_word_count = 0

    if "cx_mobile" in df.columns:
        df["phone_count"] = df["cx_mobile"].map(df["cx_mobile"].value_counts())
    else:
        df["phone_count"] = 0

    df[["risk_flag", "risk_score", "reasons"]] = df.apply(
        lambda row: pd.Series(risk_logic(row, median_word_count)),
        axis=1
    )

    # =====================================================
    # MAIN VISIBLE SCANNER COLUMNS
    # =====================================================

    visible_cols = [
        "order_id",
        "cx_name",
        "cx_mobile",
        "cx_email",
        "shopify_tags",
        "product_sku",
        "product_name",
        "address",
        "pincode",
        "payment_method",
        "quantity",
        "order_price",
        "word_count",
        "risk_score",
        "risk_flag",
        "reasons"
    ]

    scanner_df = df[visible_cols].copy()

    risky_df = scanner_df[scanner_df["risk_flag"].isin(["JUNK", "SUSPICIOUS"])].copy()
    risky_df = risky_df.sort_values(by="risk_score", ascending=False)

    # =====================================================
    # SIDEBAR FILTERS
    # =====================================================

    st.sidebar.header("Filters")

    risk_filter = st.sidebar.multiselect(
        "Risk Type",
        ["JUNK", "SUSPICIOUS"],
        default=["JUNK", "SUSPICIOUS"]
    )

    payment_options = sorted(risky_df["payment_method"].dropna().unique().tolist())

    payment_filter = st.sidebar.multiselect(
        "Payment Method",
        options=payment_options,
        default=payment_options
    )

    product_options = sorted(risky_df["product_name"].dropna().unique().tolist())

    product_filter = st.sidebar.multiselect(
        "Product Name",
        options=product_options,
        default=product_options
    )

    filtered_df = risky_df[
        (risky_df["risk_flag"].isin(risk_filter)) &
        (risky_df["payment_method"].isin(payment_filter)) &
        (risky_df["product_name"].isin(product_filter))
    ]

    # =====================================================
    # METRICS
    # =====================================================

    st.subheader("Risk Summary")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Orders", len(df))
    col2.metric("Risky Orders", len(risky_df))
    col3.metric("High Risk JUNK", len(risky_df[risky_df["risk_flag"] == "JUNK"]))
    col4.metric("Suspicious", len(risky_df[risky_df["risk_flag"] == "SUSPICIOUS"]))

    st.write("Risk Distribution")
    risk_distribution = df["risk_flag"].value_counts().reset_index()
    risk_distribution.columns = ["Risk Type", "Order Count"]
    st.dataframe(risk_distribution, use_container_width=True)

    # =====================================================
    # CUSTOMER SEGREGATION
    # =====================================================

    st.subheader("Customer Segregation")

    col1, col2 = st.columns(2)

    with col1:
        st.write("Quantity More Than 1")
        quantity_df = scanner_df[scanner_df["quantity"] > 1].copy()
        st.dataframe(quantity_df, use_container_width=True)

        csv_quantity = quantity_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download Quantity More Than 1 Orders",
            csv_quantity,
            "quantity_more_than_1_orders.csv",
            "text/csv"
        )

    with col2:
        st.write("Payment Method Summary")
        payment_summary = scanner_df.groupby("payment_method").agg(
            order_count=("order_id", "count"),
            total_amount=("order_price", "sum")
        ).reset_index()

        st.dataframe(payment_summary, use_container_width=True)

        csv_payment = payment_summary.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download Payment Method Summary",
            csv_payment,
            "payment_method_summary.csv",
            "text/csv"
        )

    st.write("Product Name Summary")
    product_summary = scanner_df.groupby("product_name").agg(
        order_count=("order_id", "count"),
        total_quantity=("quantity", "sum"),
        total_amount=("order_price", "sum")
    ).reset_index().sort_values(by="order_count", ascending=False)

    st.dataframe(product_summary, use_container_width=True)

    csv_product = product_summary.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download Product Summary",
        csv_product,
        "product_summary.csv",
        "text/csv"
    )

    # =====================================================
    # DUPLICATE ORDER CHECK
    # =====================================================

    st.subheader("Duplicate Orders")

    duplicate_df = scanner_df[
        scanner_df["cx_mobile"].notna() &
        (scanner_df["cx_mobile"] != "") &
        scanner_df["cx_mobile"].duplicated(keep=False)
    ].copy()

    duplicate_df = duplicate_df.sort_values(by=["cx_mobile", "order_id"], ascending=True)

    if len(duplicate_df) == 0:
        st.success("No duplicate orders found")
    else:
        st.error(f"Found {len(duplicate_df)} orders with duplicate phone numbers")

        st.write("Duplicate Phone Summary")
        duplicate_summary = duplicate_df["cx_mobile"].value_counts().reset_index()
        duplicate_summary.columns = ["Phone Number", "Order Count"]
        st.dataframe(duplicate_summary, use_container_width=True)

        st.write("Duplicate Order Details")
        st.dataframe(duplicate_df, use_container_width=True)

        csv_dup = duplicate_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            "Download Duplicate Orders",
            csv_dup,
            "duplicate_orders.csv",
            "text/csv"
        )

    # =====================================================
    # RISK TABLE
    # =====================================================

    st.subheader(f"Orders to Review ({len(filtered_df)})")
    st.dataframe(filtered_df, use_container_width=True)

    csv_risky = filtered_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download Filtered Risky Orders",
        csv_risky,
        "filtered_risky_orders.csv",
        "text/csv"
    )

    # =====================================================
    # FULL CLEANED OUTPUT
    # =====================================================

    st.subheader("Full Standardized Data")
    st.dataframe(scanner_df, use_container_width=True)

    csv_full = scanner_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download Full Standardized Data",
        csv_full,
        "full_standardized_orders.csv",
        "text/csv"
    )

else:
    st.info("Please select CSV format and upload a file to proceed.")
