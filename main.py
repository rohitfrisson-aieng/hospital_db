from fastapi import FastAPI
from typing import Optional
from pydantic import BaseModel
import psycopg2
import uvicorn
import os
from dotenv import load_dotenv

load_dotenv()

host = os.getenv("host")
database = os.getenv("database")
user = os.getenv("user")
password = os.getenv("password")
port = os.getenv("port")
# ------------------ FastAPI INIT ------------------ #
app = FastAPI(title="Hospital Management API", version="1.0.0")

DB_CONFIG = {
    "host": "host",
    "database": "database",
    "user": "user",
    "password": "password",
    "port": "port"
}



def get_connection():
    return psycopg2.connect(**DB_CONFIG)

# ------------------ Helper Functions ------------------ #

def check_patient_exist_in_db(patient_name: str, phone: str):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM Patients WHERE name = %s AND phone = %s", (patient_name, phone))
        patient = cursor.fetchone()
        if patient:
            return {
                "success": True,
                "exists": True,
                "patient_id": patient[0],
                "name": patient[1],
                "phone": patient[2],
                "email": patient[3],
                "age": patient[4],
                "gender": patient[5],
                "address": patient[6]
            }
        else:
            return {"success": True, "exists": False, "message": "Please register the patient first"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        cursor.close()
        conn.close()


def add_patient(name, phone, email, age, gender, address):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO Patients (name, phone, email, age, gender, address)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (name, phone, email, age, gender, address))
        conn.commit()
        return {"status": "success", "message": f"{name} added successfully"}
    except Exception as e:
        return {"status": "failed", "message": str(e)}
    finally:
        cursor.close()
        conn.close()


def get_patient_detail(patient_name, patient_mobile):
    result = check_patient_exist_in_db(patient_name, patient_mobile)
    if result.get("exists"):
        return {"status": "success", "patient_id": result["patient_id"]}
    return {"status": "failed", "message": "Please register the patient first"}


def get_doctor_by_name(doctor_name):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT doctor_id FROM Doctors WHERE name = %s", (doctor_name,))
    doctor = cursor.fetchone()
    cursor.close()
    conn.close()
    if doctor:
        return {"status": "success", "doctor_id": doctor[0]}
    return {"status": "failed", "message": "No doctor found"}


def push_appointment_to_db(patient_id, doctor_id, patient_mobile, date, time, notes=""):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO Appointments (patient_id, doctor_id, patient_mobile, appointment_date, appointment_time, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (patient_id, doctor_id, patient_mobile, date, time, notes))
        conn.commit()
        return {"success": True, "message": "Appointment booked successfully"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        cursor.close()
        conn.close()

# ------------------ Main Functions ------------------ #

def book_appointment(patient_name, patient_mobile, doctor_name, date, time,
                     email, age, gender, address, notes=""):
    patient_detail = get_patient_detail(patient_name, patient_mobile)
    if patient_detail["status"] == "failed":
        add_result = add_patient(patient_name, patient_mobile, email, age, gender, address)
        if add_result["status"] == "failed":
            return {"success": False, "message": "Unable to register patient. Please try again later."}
        patient_detail = get_patient_detail(patient_name, patient_mobile)

    patient_id = patient_detail["patient_id"]

    doctor_result = get_doctor_by_name(doctor_name)
    if doctor_result["status"] == "failed":
        return {"success": False, "message": "No doctor found"}
    doctor_id = doctor_result["doctor_id"]

    return push_appointment_to_db(patient_id, doctor_id, patient_mobile, date, time, notes)


def get_specialities_from_doctor_table():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT specialty FROM Doctors")
        speciality = [row[0] for row in cursor.fetchall()]
        return {"specialities": speciality}
    except Exception as e:
        return {"specialities": [], "error": str(e)}
    finally:
        cursor.close()
        conn.close()


def check_patient_appointment(patient_name: Optional[str] = None,
                              appointment_id: Optional[int] = None,
                              doctor_name: Optional[str] = None,
                              date: Optional[str] = None):
    conn = get_connection()
    cursor = conn.cursor()
    base_query = """
    SELECT a.appointment_id, p.name, d.name, a.appointment_date, a.appointment_time, a.status
    FROM Appointments a
    JOIN Patients p ON a.patient_id = p.patient_id
    JOIN Doctors d ON a.doctor_id = d.doctor_id
    WHERE 1=1
    """
    params = []

    if patient_name:
        base_query += " AND LOWER(p.name) LIKE %s"
        params.append(f"%{patient_name.lower()}%")
    if appointment_id:
        base_query += " AND a.appointment_id = %s"
        params.append(appointment_id)
    if doctor_name:
        base_query += " AND LOWER(d.name) LIKE %s"
        params.append(f"%{doctor_name.lower()}%")
    if date:
        base_query += " AND a.appointment_date = %s"
        params.append(date)

    cursor.execute(base_query, tuple(params))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    results = [
        {
            "appointment_id": row[0],
            "patient_name": row[1],
            "doctor_name": row[2],
            "date": row[3],
            "time": row[4],
            "status": row[5]
        }
        for row in rows
    ]
    return {"appointments": results}


def get_doctors_by_speciality(speciality: str):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM Doctors WHERE specialty = %s", (speciality,))
        doctors = cursor.fetchall()
        return [{
            "name": doc[1],
            "specialty": doc[2],
            "phone": doc[3],
            "email": doc[4],
            "consultation_fee": doc[5],
            "available_from": doc[6],
            "available_to": doc[7],
            "working_days": doc[8]
        } for doc in doctors]
    except Exception as e:
        return {"error": str(e), "doctors": []}
    finally:
        cursor.close()
        conn.close()

# ------------------ API Routes ------------------ #


@app.get("/")
def welcome_message():
    return "WELCOME TO HOSPITAL SERVER"

@app.get("/specialities")
def api_get_specialities():
    return get_specialities_from_doctor_table()

@app.get("/appointments")
def api_check_appointment(patient_name: Optional[str] = None,
                          appointment_id: Optional[int] = None,
                          doctor_name: Optional[str] = None,
                          date: Optional[str] = None):
    return check_patient_appointment(patient_name, appointment_id, doctor_name, date)

@app.get("/doctors/{speciality}")
def api_get_doctors(speciality: str):
    return get_doctors_by_speciality(speciality)

class AppointmentRequest(BaseModel):
    patient_name: str
    patient_mobile: str
    doctor_name: str
    date: str
    time: str
    email: str
    age: int
    gender: str
    address: str
    notes: Optional[str] = ""

@app.post("/book-appointment")
def api_book_appointment(req: AppointmentRequest):
    return book_appointment(
        req.patient_name,
        req.patient_mobile,
        req.doctor_name,
        req.date,
        req.time,
        req.email,
        req.age,
        req.gender,
        req.address,
        req.notes,
    )

if __name__ =="__main__":
    uvicorn.run(
        host = "0.0.0.0",
        app = app,
        port = 8000
    )
