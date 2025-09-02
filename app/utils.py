def build_student_id(dob: str, phone: str) -> str:
    """
    Build student management ID by concatenating DOB (YYYYMMDD) and phone digits.
    Precondition: dob is 8-digit string, phone is digits-only string.
    """
    if not (isinstance(dob, str) and len(dob) == 8 and dob.isdigit()):
        raise ValueError("Invalid dob: expect YYYYMMDD digits")
    if not (isinstance(phone, str) and phone.isdigit() and len(phone) >= 7):
        raise ValueError("Invalid phone: expect digits only >=7 length")
    return f"{dob}{phone}"
