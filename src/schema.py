"""
Canonical schema for CMS Open Payments (Sunshine Act) General Payments data.

Two jobs:
  1. Define the tidy internal column names the rest of the codebase uses.
  2. Map the many real-world CMS raw column names (which drift across program years)
     onto those tidy names, so the SAME pipeline runs on the synthetic demo file and on
     a real CMS General Payments download.

Reference layout: CMS "OP_DTL_GNRL_PGYR<year>" detail files.
"""

# ---- tidy internal column names ----
PROGRAM_YEAR = "program_year"
RECIPIENT_TYPE = "recipient_type"
RECIPIENT_ID = "recipient_id"
NPI = "npi"
RECIPIENT_NAME = "recipient_name"
SPECIALTY = "specialty"
CITY = "city"
STATE = "state"
ZIP = "zip"
MANUFACTURER = "manufacturer"
AMOUNT = "amount"
DATE = "date"
N_PAYMENTS = "n_payments"
FORM = "form"
NATURE = "nature"
PRODUCT = "product"

TIDY_COLUMNS = [
    PROGRAM_YEAR, RECIPIENT_TYPE, RECIPIENT_ID, NPI, RECIPIENT_NAME, SPECIALTY,
    CITY, STATE, ZIP, MANUFACTURER, AMOUNT, DATE, N_PAYMENTS, FORM, NATURE, PRODUCT,
]

# ---- CMS raw -> tidy mapping (includes known variants across years) ----
# Many tidy fields have several possible source names; first present wins.
CMS_TO_TIDY = {
    PROGRAM_YEAR: ["Program_Year"],
    RECIPIENT_TYPE: ["Covered_Recipient_Type"],
    RECIPIENT_ID: [
        "Covered_Recipient_Profile_ID", "Physician_Profile_ID", "Teaching_Hospital_ID",
    ],
    NPI: ["Covered_Recipient_NPI", "Physician_NPI"],
    SPECIALTY: [
        "Covered_Recipient_Specialty_1", "Physician_Specialty",
        "Covered_Recipient_Primary_Type_1",
    ],
    CITY: ["Recipient_City"],
    STATE: ["Recipient_State"],
    ZIP: ["Recipient_Zip_Code"],
    MANUFACTURER: [
        "Applicable_Manufacturer_or_Applicable_GPO_Making_Payment_Name",
        "Submitting_Applicable_Manufacturer_or_Applicable_GPO_Name",
    ],
    AMOUNT: ["Total_Amount_of_Payment_USDollars"],
    DATE: ["Date_of_Payment"],
    N_PAYMENTS: ["Number_of_Payments_Included_in_Total_Amount"],
    FORM: ["Form_of_Payment_or_Transfer_of_Value"],
    NATURE: ["Nature_of_Payment_or_Transfer_of_Value"],
    PRODUCT: [
        "Name_of_Drug_or_Biological_or_Device_or_Medical_Supply_1",
        "Name_of_Associated_Covered_Drug_or_Biological1",
    ],
}

# Name parts (CMS stores recipient names in pieces; we assemble RECIPIENT_NAME in the loader).
NAME_PART_COLUMNS = {
    "first": ["Covered_Recipient_First_Name", "Physician_First_Name"],
    "last": ["Covered_Recipient_Last_Name", "Physician_Last_Name"],
    "hospital": ["Teaching_Hospital_Name"],
}

# ---- recipient-type normalization ----
PHYSICIAN = "Physician"
NPP = "Non-Physician Practitioner"
TEACHING_HOSPITAL = "Teaching Hospital"

RECIPIENT_TYPE_MAP = {
    "Covered Recipient Physician": PHYSICIAN,
    "Covered Recipient Non-Physician Practitioner": NPP,
    "Covered Recipient Teaching Hospital": TEACHING_HOSPITAL,
    "Non-covered Recipient Entity": TEACHING_HOSPITAL,
}

# ---- domain vocabularies (used by the synthetic generator; also documents the space) ----
NATURES = [
    "Food and Beverage",
    "Travel and Lodging",
    "Consulting Fee",
    "Compensation for serving as faculty or as a speaker",
    "Honoraria",
    "Education",
    "Gift",
    "Grant",
    "Royalty or License",
    "Charitable Contribution",
    "Entertainment",
    "Space rental or facility fees",
]

FORMS = [
    "In-kind items and services",
    "Cash or cash equivalent",
    "Dividend, profit or other return on investment",
]

SPECIALTIES = [
    "Allopathic & Osteopathic Physicians|Internal Medicine|Cardiovascular Disease",
    "Allopathic & Osteopathic Physicians|Orthopaedic Surgery",
    "Allopathic & Osteopathic Physicians|Internal Medicine|Endocrinology",
    "Allopathic & Osteopathic Physicians|Internal Medicine|Medical Oncology",
    "Allopathic & Osteopathic Physicians|Psychiatry & Neurology|Psychiatry",
    "Allopathic & Osteopathic Physicians|Family Medicine",
    "Allopathic & Osteopathic Physicians|Internal Medicine",
    "Allopathic & Osteopathic Physicians|Dermatology",
    "Allopathic & Osteopathic Physicians|Pediatrics",
    "Allopathic & Osteopathic Physicians|Neurological Surgery",
    "Allopathic & Osteopathic Physicians|Internal Medicine|Rheumatology",
    "Allopathic & Osteopathic Physicians|Internal Medicine|Gastroenterology",
]
