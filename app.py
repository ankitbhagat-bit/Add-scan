import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="Address Risk Scanner", layout="wide")

st.title("Address Risk Scanner")


# =====================================================
# HELPERS
# =====================================================

def clean_text(value):
    if value is None:
        return ""

    try:
        if value != value:
            return ""
    except Exception:
        pass

    value = str(value)

    if value == "<NA>":
        return ""

    value = value.replace("`", "").replace("'", "").strip()

    # Clean common Shopify encoding issue
    value = value.replace("â‚¹", "₹")

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

    if value == "":
        return "UNKNOWN"

    if "COD" in value or "CASH ON DELIVERY" in value:
        return "COD"

    if "PREPAID" in value or "PRE PAID" in value:
        return "PREPAID"

    if value in ["PAID", "AUTHORIZED", "PARTIALLY PAID"]:
        return "PREPAID"

    if value in ["PENDING", "UNPAID"]:
        return "COD"

    return value


def safe_col(df, col_name, default=""):
    df.columns = df.columns.str.strip()

    if col_name in df.columns:
        return df[col_name].apply(clean_text)

    return pd.Series([default] * len(df), index=df.index)


def first_non_empty(df, cols, default=""):
    df.columns = df.columns.str.strip()

    result = pd.Series([""] * len(df), index=df.index)

    for col in cols:
        if col in df.columns:
            current = df[col].apply(clean_text)
            result = result.where(result != "", current)

    return result.replace("", default)


def combine_cols(df, cols):
    df.columns = df.columns.str.strip()

    available_cols = [col for col in cols if col in df.columns]

    if not available_cols:
        return pd.Series([""] * len(df), index=df.index)

    combined = df[available_cols].fillna("").astype(str).agg(" ".join, axis=1)

    return combined.apply(clean_text)


def numeric_col(df, col_name, default=0):
    if col_name in df.columns:
        return pd.to_numeric(df[col_name], errors="coerce").fillna(default)

    return pd.Series([default] * len(df), index=df.index)


# =====================================================
# FORMAT MAPPERS
# =====================================================

def map_unicommerce(df):
    """
    Unicommerce structure.
    """

    df.columns = df.columns.str.strip()

    mapped = pd.DataFrame(index=df.index)

    mapped["order_id"] = safe_col(df, "Display Order #")

    mapped["cx_name"] = first_non_empty(
        df,
        [
            "Customer Name",
            "Customer",
            "Name"
        ]
    )

    mapped["cx_mobile"] = first_non_empty(
        df,
        [
            "Customer Mobile",
            "Mobile",
            "Phone",
            "Customer Phone"
        ]
    ).apply(clean_phone)

    mapped["cx_email"] = first_non_empty(
        df,
        [
            "Customer Email",
            "Email",
            "Customer Email ID"
        ]
    )

    mapped["shopify_tags"] = first_non_empty(
        df,
        [
            "ShopifyTags",
            "Shopify Tags",
            "Tags"
        ]
    )

    mapped["product_sku"] = first_non_empty(
        df,
        [
            "SKU",
            "Product SKU",
            "Item SKU",
            "Products"
        ]
    )

    mapped["product_name"] = first_non_empty(
        df,
        [
            "Products",
            "Product Name",
            "Item Name"
        ]
    )

    mapped["address_line_1"] = safe_col(df, "Shipping Address Line 1")
    mapped["address_line_2"] = safe_col(df, "Shipping Address Line 2")

    mapped["city_state"] = first_non_empty(
        df,
        [
            "City, State",
            "City State"
        ]
    )

    mapped["address"] = combine_cols(
        df,
        [
            "Shipping Address Line 1",
            "Shipping Address Line 2",
            "City, State",
            "City State"
        ]
    )

    mapped["pincode"] = first_non_empty(
        df,
        [
            "Pincode",
            "Pin Code",
            "Postal Code",
            "Zip"
        ]
    ).apply(clean_pincode)

    mapped["payment_method"] = first_non_empty(
        df,
        [
            "Pymt",
            "Payment Method",
            "Payment Mode",
            "Payment Type"
        ]
    ).apply(normalize_payment)

    mapped["quantity"] = pd.to_numeric(
        first_non_empty(
            df,
            [
                "Quantity",
                "Qty",
                "Item Quantity"
            ],
            default="1"
        ),
        errors="coerce"
    ).fillna(1).astype(int)

    mapped["order_price"] = pd.to_numeric(
        first_non_empty(
            df,
            [
                "Order Price",
                "Total",
                "Amount",
                "Order Amount"
            ],
            default="0"
        ),
        errors="coerce"
    ).fillna(0)

    return mapped


def map_easyecom(df):
    """
    EasyEcom structure.
    Supports the newer EasyEcom order export that includes columns like:
    Reference Code, Suborder No, Shipping Customer Name, Mobile No,
    Shipping Address Line 1/2, Shipping Zip Code, Payment Mode, etc.
    """

    df.columns = df.columns.str.strip()

    mapped = pd.DataFrame(index=df.index)

    mapped["order_id"] = first_non_empty(
        df,
        [
            "Reference Code",
            "Suborder No",
            "Suborder Number",
            "MP Ref No",
            "EE Invoice No",
            "Order Number",
            "Easy Id",
            "id"
        ]
    )

    mapped["cx_name"] = first_non_empty(
        df,
        [
            "Shipping Customer Name",
            "Billing Customer Name",
            "Customer Name",
            "Shipping Name",
            "Name"
        ]
    )

    mapped["cx_mobile"] = first_non_empty(
        df,
        [
            "Mobile No",
            "Customer Mobile",
            "Customer Phone",
            "Shipping Phone",
            "Phone",
            "Mobile"
        ]
    ).apply(clean_phone)

    mapped["cx_email"] = first_non_empty(
        df,
        [
            "Customer Email",
            "Email"
        ]
    )

    mapped["company_name"] = first_non_empty(
        df,
        [
            "Company Name",
            "Company",
            "Warehouse",
            "Facility"
        ]
    )

    mapped["shopify_tags"] = first_non_empty(
        df,
        [
            "Discount Codes",
            "MP Alias",
            "B2B Sales Channel",
            "Tags",
            "ShopifyTags",
            "Shopify Tags"
        ]
    )

    mapped["product_sku"] = first_non_empty(
        df,
        [
            "SKU",
            "Marketplace Sku",
            "Marketplace SKU",
            "Accounting Sku"
        ]
    )

    mapped["product_name"] = safe_col(df, "Product Name")

    mapped["address_line_1"] = first_non_empty(
        df,
        [
            "Shipping Address Line 1",
            "Shipping Address",
            "Address",
            "Address Line 1"
        ]
    )

    mapped["address_line_2"] = first_non_empty(
        df,
        [
            "Shipping Address Line 2",
            "Address Line 2",
            "Shipping Address 2"
        ]
    )

    mapped["city_state"] = combine_cols(
        df,
        [
            "Shipping City",
            "Shipping State",
            "Shipping Country"
        ]
    )

    mapped["shipping_city"] = safe_col(df, "Shipping City")
    mapped["shipping_state"] = safe_col(df, "Shipping State")
    mapped["shipping_country"] = safe_col(df, "Shipping Country")

    full_address = combine_cols(
        df,
        [
            "Shipping Address Line 1",
            "Shipping Address Line 2",
            "Shipping Address",
            "Address",
            "Address Line 1",
            "Address Line 2",
            "Shipping City",
            "Shipping State",
            "Shipping Country",
            "Shipping Zip Code",
            "Shipping Postal code"
        ]
    )

    fallback_city_pin = combine_cols(
        df,
        [
            "Shipping City",
            "Shipping State",
            "Shipping Country",
            "Shipping Zip Code",
            "Shipping Postal code"
        ]
    )

    mapped["address"] = full_address.where(full_address != "", fallback_city_pin)

    mapped["pincode"] = first_non_empty(
        df,
        [
            "Shipping Zip Code",
            "Shipping Postal code",
            "Pincode",
            "Pin Code",
            "Postal Code",
            "Zip",
            "Zip Code"
        ]
    ).apply(clean_pincode)

    mapped["payment_method"] = first_non_empty(
        df,
        [
            "Payment Mode",
            "Payment Status",
            "Payment Method",
            "Payment Gateway"
        ]
    ).apply(normalize_payment)

    mapped["quantity"] = pd.to_numeric(
        first_non_empty(
            df,
            [
                "Suborder Quantity",
                "Item Quantity",
                "Order Quantity",
                "Shipped Quantity",
                "Quantity",
                "Qty"
            ],
            default="1"
        ),
        errors="coerce"
    ).fillna(1).astype(int)

    mapped["order_price"] = pd.to_numeric(
        first_non_empty(
            df,
            [
                "Order Invoice Amount",
                "Collectible Amount",
                "Tax Item Price(Including Tax)",
                "COD(Including Tax)",
                "Item Price",
                "Payment Amount",
                "Selling Price",
                "MRP"
            ],
            default="0"
        ),
        errors="coerce"
    ).fillna(0)

    return mapped


def map_shopify(df):
    """
    Shopify export structure.
    Strong fallback added for address, pincode, phone and payment mode.
    """

    df.columns = df.columns.str.strip()

    mapped = pd.DataFrame(index=df.index)

    mapped["order_id"] = safe_col(df, "Name")

    mapped["cx_name"] = first_non_empty(
        df,
        [
            "Shipping Name",
            "Billing Name"
        ]
    )

    mapped["cx_mobile"] = first_non_empty(
        df,
        [
            "Shipping Phone",
            "Billing Phone",
            "Phone"
        ]
    ).apply(clean_phone)

    mapped["cx_email"] = safe_col(df, "Email")
    mapped["shopify_tags"] = safe_col(df, "Tags")

    mapped["product_sku"] = safe_col(df, "Lineitem sku")
    mapped["product_name"] = safe_col(df, "Lineitem name")

    mapped["address_line_1"] = first_non_empty(
        df,
        [
            "Shipping Address1",
            "Shipping Street",
            "Billing Address1",
            "Billing Street"
        ]
    )

    mapped["address_line_2"] = first_non_empty(
        df,
        [
            "Shipping Address2",
            "Billing Address2"
        ]
    )

    mapped["city_state"] = combine_cols(
        df,
        [
            "Shipping City",
            "Shipping Province",
            "Shipping Province Name",
            "Billing City",
            "Billing Province",
            "Billing Province Name"
        ]
    )

    shipping_address = combine_cols(
        df,
        [
            "Shipping Street",
            "Shipping Address1",
            "Shipping Address2",
            "Shipping City",
            "Shipping Province",
            "Shipping Province Name",
            "Shipping Country"
        ]
    )

    billing_address = combine_cols(
        df,
        [
            "Billing Street",
            "Billing Address1",
            "Billing Address2",
            "Billing City",
            "Billing Province",
            "Billing Province Name",
            "Billing Country"
        ]
    )

    mapped["address"] = shipping_address.where(shipping_address != "", billing_address)

    mapped["pincode"] = first_non_empty(
        df,
        [
            "Shipping Zip",
            "Billing Zip"
        ]
    ).apply(clean_pincode)

    payment_from_method = safe_col(df, "Payment Method").apply(normalize_payment)
    payment_from_shipping = safe_col(df, "Shipping Method").apply(normalize_payment)
    payment_from_financial = safe_col(df, "Financial Status").apply(normalize_payment)

    mapped["payment_method"] = payment_from_method

    mapped["payment_method"] = mapped["payment_method"].where(
        mapped["payment_method"] != "UNKNOWN",
        payment_from_shipping
    )

    mapped["payment_method"] = mapped["payment_method"].where(
        mapped["payment_method"] != "UNKNOWN",
        payment_from_financial
    )

    mapped["quantity"] = pd.to_numeric(
        safe_col(df, "Lineitem quantity", 1),
        errors="coerce"
    ).fillna(1).astype(int)

    mapped["order_price"] = pd.to_numeric(
        safe_col(df, "Total", 0),
        errors="coerce"
    ).fillna(0)

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
    return bool(
        re.search(
            r"\b(test|asdf|xxxx|na|none|null|dummy|sample|abc|xyz)\b",
            str(text).lower()
        )
    )


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
        "ke paas",
        "gali",
        "mandir",
        "school",
        "hospital",
        "chowk"
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


def short_address_risk_tag(row):
    if row["ship_address_line_1_word_count"] <= 3:
        return "High Risk"

    return "Low Risk"


def scanner_risk_tag(risk_flag):
    if risk_flag == "JUNK":
        return "High Risk"

    if risk_flag == "SUSPICIOUS":
        return "Medium Risk"

    return "Low Risk"


def risk_tag_style(value):
    value = str(value).lower()

    if "high" in value:
        return "background-color: #f8d7da; color: #842029; font-weight: 700;"

    if "medium" in value:
        return "background-color: #fff3cd; color: #664d03; font-weight: 700;"

    if "low" in value:
        return "background-color: #d1e7dd; color: #0f5132; font-weight: 700;"

    return ""


def style_risk_tags(df):
    risk_cols = [
        col for col in [
            "risk_tag",
            "short_address_risk",
            "Risk Tag",
            "Short Address Risk",
            "Risk Type"
        ]
        if col in df.columns
    ]

    if not risk_cols:
        return df

    return df.style.map(risk_tag_style, subset=risk_cols)


def display_table(df, max_rows=200, style=True):
    """
    Render a capped preview so large uploads do not crash Streamlit Cloud.
    Downloads still use the complete dataframe.
    """

    display_df = df.head(max_rows).copy()

    if len(df) > max_rows:
        st.caption(
            f"Showing first {max_rows:,} of {len(df):,} rows. "
            "Use the download button for the full data."
        )

    if style:
        st.dataframe(style_risk_tags(display_df), use_container_width=True)
    else:
        st.dataframe(display_df, use_container_width=True)


def scanner_display_df(df):
    return df.drop(columns=["risk_score", "risk_flag"], errors="ignore")


def append_reason(existing_reasons, new_reason):
    existing_reasons = clean_text(existing_reasons)

    if existing_reasons == "":
        return new_reason

    if new_reason in existing_reasons:
        return existing_reasons

    return f"{existing_reasons}, {new_reason}"


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


def manual_address_check(address, payment_method="COD", median_word_count=5):
    """
    Score a manually typed address using the same risk logic.
    Extract phone and pincode from pasted text when available.
    Neutral fallback fields keep the result focused on address quality.
    """

    clean_address = clean_text(address)
    phone_matches = re.findall(r"(?<!\d)(?:\+?91)?[6-9]\d{9}(?!\d)", clean_address)
    pincode_matches = re.findall(r"(?<!\d)\d{6}(?!\d)", clean_address)

    manual_phone = clean_phone(phone_matches[0]) if phone_matches else ""
    manual_pincode = clean_pincode(pincode_matches[-1]) if pincode_matches else ""

    row = {
        "address": clean_address,
        "word_count": len(clean_address.split()),
        "payment_method": normalize_payment(payment_method),
        "cx_mobile": manual_phone,
        "pincode": manual_pincode,
        "cx_name": "Manual Test",
        "phone_count": 1
    }

    return risk_logic(row, median_word_count)

def fill_missing_order_details(df):
    """
    Shopify sometimes gives multiple rows for one order.
    Some line-item rows have product details but blank address/payment/pincode.
    This fills missing fields using same order_id first, then same cx_mobile.
    """

    fill_cols = [
        "cx_name",
        "cx_email",
        "shopify_tags",
        "address",
        "pincode",
        "payment_method"
    ]

    for col in fill_cols:
        if col in df.columns:
            df[col] = df[col].replace("", pd.NA)

            # Fill using same order_id
            df[col] = df.groupby("order_id")[col].transform(
                lambda x: x.ffill().bfill()
            )

            # If still missing, fill using same mobile number
            df[col] = df.groupby("cx_mobile")[col].transform(
                lambda x: x.ffill().bfill()
            )

            df[col] = df[col].fillna("")

    return df
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

st.subheader("Manual Address Test")

manual_col1, manual_col2 = st.columns([4, 1])

with manual_col1:
    manual_address = st.text_input(
        "Enter address to test",
        placeholder="House no, street, area, city..."
    )

with manual_col2:
    manual_payment = st.selectbox(
        "Payment",
        ["COD", "PREPAID"],
        key="manual_payment"
    )

if st.button("Check Address"):
    if manual_address.strip() == "":
        st.warning("Please enter an address to test.")
    else:
        manual_flag, manual_score, manual_reasons = manual_address_check(
            manual_address,
            manual_payment
        )

        if manual_flag == "JUNK":
            st.error(f"Result: {manual_flag} | Score: {manual_score}")
        elif manual_flag == "SUSPICIOUS":
            st.warning(f"Result: {manual_flag} | Score: {manual_score}")
        else:
            st.success(f"Result: {manual_flag} | Score: {manual_score}")

        st.write(
            "Reasons:",
            manual_reasons if manual_reasons else "No risk reasons found"
        )

if uploaded_file:

    try:
        raw_df = pd.read_csv(uploaded_file, dtype=str)
    except UnicodeDecodeError:
        raw_df = pd.read_csv(uploaded_file, dtype=str, encoding="latin1")

    raw_df.columns = raw_df.columns.str.strip()
    raw_df.fillna("", inplace=True)

    st.write("Uploaded File Preview")
    display_table(raw_df.head(5), style=False)

    df = standardize_file(raw_df, file_type)
    df.fillna("", inplace=True)

    # =====================================================
    # REQUIRED STANDARD COLUMNS CLEANUP
    # =====================================================

    df["order_id"] = df["order_id"].apply(clean_text)
    df["cx_name"] = df["cx_name"].apply(clean_text)
    df["cx_mobile"] = df["cx_mobile"].apply(clean_phone)
    df["cx_email"] = df["cx_email"].apply(clean_text)
    if "company_name" not in df.columns:
        df["company_name"] = ""
    if "shipping_city" not in df.columns:
        df["shipping_city"] = ""
    if "shipping_state" not in df.columns:
        df["shipping_state"] = ""
    if "shipping_country" not in df.columns:
        df["shipping_country"] = ""

    df["company_name"] = df["company_name"].apply(clean_text)
    df["shipping_city"] = df["shipping_city"].apply(clean_text)
    df["shipping_state"] = df["shipping_state"].apply(clean_text)
    df["shipping_country"] = df["shipping_country"].apply(clean_text)
    df["shopify_tags"] = df["shopify_tags"].apply(clean_text)
    df["product_sku"] = df["product_sku"].apply(clean_text)
    df["product_name"] = df["product_name"].apply(clean_text)
    df["address_line_1"] = df["address_line_1"].apply(clean_text)
    df["address_line_2"] = df["address_line_2"].apply(clean_text)
    df["address"] = df["address"].apply(clean_text)
    df["pincode"] = df["pincode"].apply(clean_pincode)
    df["payment_method"] = df["payment_method"].apply(normalize_payment)
    # Fill blank Shopify line-item rows using same order/customer data
    df = fill_missing_order_details(df)
    
    # Clean again after filling
    df["address"] = df["address"].apply(clean_text)
    df["pincode"] = df["pincode"].apply(clean_pincode)
    df["payment_method"] = df["payment_method"].apply(normalize_payment)

    df["word_count"] = df["address"].apply(lambda x: len(str(x).split()))

    median_word_count = df["word_count"].median()

    if pd.isna(median_word_count):
        median_word_count = 0

    df["phone_count"] = df["cx_mobile"].map(df["cx_mobile"].value_counts())

    df[["risk_flag", "risk_score", "reasons"]] = df.apply(
        lambda row: pd.Series(risk_logic(row, median_word_count)),
        axis=1
    )

    df["risk_tag"] = df["risk_flag"].apply(scanner_risk_tag)

    if file_type == "EasyEcom":
        short_line_1_mask = df["address_line_1"].apply(
            lambda x: len(str(x).split())
        ) <= 3

        df.loc[short_line_1_mask, "risk_tag"] = "High Risk"
        df.loc[short_line_1_mask, "reasons"] = df.loc[
            short_line_1_mask,
            "reasons"
        ].apply(
            lambda reasons: append_reason(
                reasons,
                "Shipping Address Line 1 word count <= 3"
            )
        )

    # =====================================================
    # MAIN VISIBLE SCANNER COLUMNS
    # =====================================================

    visible_cols = [
        "order_id",
        "company_name",
        "cx_name",
        "cx_mobile",
        "cx_email",
        "shopify_tags",
        "product_sku",
        "product_name",
        "address_line_1",
        "address_line_2",
        "address",
        "pincode",
        "shipping_city",
        "shipping_state",
        "shipping_country",
        "payment_method",
        "quantity",
        "order_price",
        "word_count",
        "risk_tag",
        "risk_score",
        "risk_flag",
        "reasons"
    ]

    scanner_df = df[visible_cols].copy()

    risky_df = scanner_df[
        scanner_df["risk_tag"].isin(["High Risk", "Medium Risk"])
    ].copy()

    risky_df = risky_df.sort_values(by="risk_score", ascending=False)

    short_address_df = pd.DataFrame()

    if file_type == "EasyEcom":
        short_address_df = scanner_df.copy()
        short_address_df["ship_address_line_1_word_count"] = short_address_df[
            "address_line_1"
        ].apply(lambda x: len(str(x).split()))

        short_address_df = short_address_df[
            short_address_df["ship_address_line_1_word_count"] <= 3
        ].copy()

        short_address_df["short_address_risk"] = short_address_df.apply(
            short_address_risk_tag,
            axis=1
        )

    # =====================================================
    # SIDEBAR FILTERS
    # =====================================================

    st.sidebar.header("Filters")

    risk_filter = st.sidebar.multiselect(
        "Scanner Risk Tag",
        ["High Risk", "Medium Risk"],
        default=["High Risk", "Medium Risk"]
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

    short_address_risk_filter = []
    short_address_company_filter = []

    if file_type == "EasyEcom":
        st.sidebar.header("EasyEcom Short Address Filters")

        short_address_risk_options = [
            "Low Risk",
            "Medium Risk",
            "High Risk"
        ]

        short_address_risk_filter = st.sidebar.multiselect(
            "Short Address Risk",
            options=short_address_risk_options,
            default=short_address_risk_options
        )

        short_address_company_options = sorted(
            short_address_df["company_name"].dropna().unique().tolist()
        )

        short_address_company_filter = st.sidebar.multiselect(
            "Company Name",
            options=short_address_company_options,
            default=short_address_company_options
        )

    filtered_df = risky_df[
        (risky_df["risk_tag"].isin(risk_filter)) &
        (risky_df["payment_method"].isin(payment_filter)) &
        (risky_df["product_name"].isin(product_filter))
    ]

    filtered_short_address_df = short_address_df

    if file_type == "EasyEcom":
        filtered_short_address_df = short_address_df[
            (short_address_df["short_address_risk"].isin(short_address_risk_filter)) &
            (short_address_df["company_name"].isin(short_address_company_filter))
        ].copy()

    # =====================================================
    # METRICS
    # =====================================================

    st.subheader("Risk Summary")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Orders", len(scanner_df))
    col2.metric("Risky Orders", len(risky_df))
    col3.metric("High Risk", len(risky_df[risky_df["risk_tag"] == "High Risk"]))
    col4.metric("Medium Risk", len(risky_df[risky_df["risk_tag"] == "Medium Risk"]))

    st.write("Risk Distribution")

    risk_distribution = scanner_df["risk_tag"].value_counts().reset_index()
    risk_distribution.columns = ["Risk Type", "Order Count"]

    display_table(risk_distribution)

    if file_type == "EasyEcom":
        st.subheader("EasyEcom Company Classification")

        company_summary = scanner_df.groupby("company_name").agg(
            order_count=("order_id", "count"),
            risky_orders=("risk_flag", lambda x: x.isin(["JUNK", "SUSPICIOUS"]).sum()),
            total_amount=("order_price", "sum")
        ).reset_index().sort_values(by="order_count", ascending=False)

        display_table(company_summary, style=False)

        st.subheader(
            f"EasyEcom Short Shipping Address Line 1 Orders ({len(filtered_short_address_df)})"
        )

        short_address_visible_cols = [
            "order_id",
            "company_name",
            "short_address_risk",
            "ship_address_line_1_word_count",
            "address_line_1",
            "address_line_2",
            "cx_email",
            "shipping_city",
            "pincode",
            "shipping_state",
            "shipping_country",
            "cx_mobile",
            "payment_method",
            "risk_tag",
            "reasons"
        ]

        short_address_display_df = filtered_short_address_df[
            short_address_visible_cols
        ].rename(
            columns={
                "order_id": "Order ID",
                "company_name": "Company Name",
                "short_address_risk": "Short Address Risk",
                "ship_address_line_1_word_count": "Ship Address Line 1 Word Count",
                "address_line_1": "Shipping Address Line 1",
                "address_line_2": "Shipping Address Line 2",
                "cx_email": "Customer Email",
                "shipping_city": "Shipping City",
                "pincode": "Shipping Zip Code",
                "shipping_state": "Shipping State",
                "shipping_country": "Shipping Country",
                "cx_mobile": "Customer Mobile",
                "payment_method": "Payment Method",
                "risk_tag": "Risk Tag",
                "reasons": "Scanner Reasons"
            }
        )

        display_table(short_address_display_df)

        csv_short_address = short_address_display_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            "Download EasyEcom Short Address Orders",
            csv_short_address,
            "easyecom_short_address_orders.csv",
            "text/csv"
        )

    # =====================================================
    # CUSTOMER SEGREGATION
    # =====================================================

    st.subheader("Customer Segregation")

    col1, col2 = st.columns(2)

    with col1:
        st.write("Quantity More Than 1")

        quantity_df = scanner_df[scanner_df["quantity"] > 1].copy()
        quantity_display_df = scanner_display_df(quantity_df)

        display_table(quantity_display_df)

        csv_quantity = quantity_display_df.to_csv(index=False).encode("utf-8")

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

        display_table(payment_summary, style=False)

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

    display_table(product_summary, style=False)

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

    duplicate_df = duplicate_df.sort_values(
        by=["cx_mobile", "order_id"],
        ascending=True
    )

    if len(duplicate_df) == 0:
        st.success("No duplicate orders found")
    else:
        st.error(f"Found {len(duplicate_df)} orders with duplicate phone numbers")

        st.write("Duplicate Phone Summary")

        duplicate_summary = duplicate_df["cx_mobile"].value_counts().reset_index()
        duplicate_summary.columns = ["Phone Number", "Order Count"]

        display_table(duplicate_summary, style=False)

        st.write("Duplicate Order Details")

        duplicate_display_df = scanner_display_df(duplicate_df)

        display_table(duplicate_display_df)

        csv_dup = duplicate_display_df.to_csv(index=False).encode("utf-8")

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

    filtered_display_df = scanner_display_df(filtered_df)

    display_table(filtered_display_df)

    csv_risky = filtered_display_df.to_csv(index=False).encode("utf-8")

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

    scanner_display = scanner_display_df(scanner_df)

    display_table(scanner_display)

    csv_full = scanner_display.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download Full Standardized Data",
        csv_full,
        "full_standardized_orders.csv",
        "text/csv"
    )

else:
    st.info("Please select CSV format and upload a file to proceed.")
