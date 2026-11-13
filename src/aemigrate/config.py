"""Reference data and constants. All codes are SYNTHETIC (not real MedDRA / WHODrug)."""
import re

LEGACY_COLUMNS = [
    "case_id", "receive_date", "patient_initials", "patient_dob", "patient_sex",
    "patient_weight_kg", "drug_code", "drug_name", "dose_mg", "therapy_start",
    "therapy_end", "event_code", "event_term", "event_onset", "seriousness",
    "outcome", "reporter_name", "reporter_type", "reporter_country",
]

# How each legacy field is canonicalised before checksumming (see reconcile.canon)
FIELD_KINDS = {c: "text" for c in LEGACY_COLUMNS}
FIELD_KINDS.update({
    "receive_date": "date", "patient_dob": "date", "therapy_start": "date",
    "therapy_end": "date", "event_onset": "date",
    "patient_weight_kg": "dec1", "dose_mg": "dec2",
})

MANDATORY_FIELDS = ["case_id", "receive_date", "drug_code", "event_code", "seriousness"]
DATE_FIELDS = ["receive_date", "patient_dob", "therapy_start", "therapy_end", "event_onset"]
CASE_ID_RE = re.compile(r"AE-\d{6}")

_DRUG_NAMES = ["Zorvamab", "Calixetine", "Neprolid", "Tavorin", "Brelixan", "Omnitrol",
               "Vexadine", "Lumirax", "Quenotab", "Hydrazol", "Pentavir", "Duralex",
               "Fenoprim", "Ixarel", "Mavotin", "Selvarin", "Trexonil", "Olvanta",
               "Cardizen", "Rilumab"]
DRUG_CODES = {f"DRG{i:03d}": n for i, n in enumerate(_DRUG_NAMES, start=1)}

_EVENT_TERMS = ["Nausea", "Headache", "Dizziness", "Rash", "Fatigue", "Vomiting",
                "Diarrhoea", "Pyrexia", "Hypertension", "Hypotension", "Insomnia",
                "Arthralgia", "Pruritus", "Dyspnoea", "Palpitations", "Anaemia",
                "Abdominal pain", "Cough", "Alopecia", "Tremor", "Syncope",
                "Oedema peripheral", "Hepatic enzyme increased",
                "Anaphylactic reaction", "Thrombocytopenia"]
EVENT_CODES = {f"EVT{i:03d}": t for i, t in enumerate(_EVENT_TERMS, start=1)}

SERIOUSNESS = ("Serious", "Non-serious")
OUTCOMES = ("Recovered", "Recovering", "Not recovered", "Fatal", "Unknown")
SEX = ("M", "F", "U")
REPORTER_TYPES = ("Physician", "Pharmacist", "Nurse", "Consumer")
COUNTRIES = ("IN", "US", "GB", "DE", "FR", "JP")
