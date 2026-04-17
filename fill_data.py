import pyodbc
from faker import Faker
import random

# إعداد الاتصال
conn_str = (
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=ADHAM\\MSSQLSERVER01;"
    "Database=IHMS;"
    "Trusted_Connection=yes;"
)
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()
fake = Faker('ar_EG') # لدعم الأسماء العربية

def seed_data():
    print("جاري ملء البيانات... انتظر قليلاً")

    # 1. إضافة مرضى وهميين
    patients_ids = []
    for _ in range(20):
        # توليد رقم قومي عشوائي (14 رقم يبدأ بـ 2 أو 3)
        n_id = str(random.randint(2, 3)) + "".join([str(random.randint(0, 9)) for _ in range(13)])
        name = fake.name()
        phone = "01" + "".join([str(random.randint(0, 9)) for _ in range(9)])
        gender = random.choice(['ذكر', 'أنثى'])
        blood = random.choice(['A+', 'O-', 'B+', 'AB+'])
        birth = fake.date_of_birth(minimum_age=18, maximum_age=70).strftime('%Y-%m-%d')
        
        try:
            cursor.execute("""
                INSERT INTO Patients (NationalID, FullName, [Password], Phone, Gender, BirthDate, blood_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (n_id, name, '123456', phone, gender, birth, blood))
            patients_ids.append(n_id)
        except Exception as e:
            print(f"تخطي مريض بسبب خطأ: {e}")

    # 2. إضافة أصناف مخزون
    items = [
        ('MSK-001', 'كمامات طبية', 100, 'علبة'),
        ('GLV-002', 'قفازات لاتكس', 50, 'علبة'),
        ('ALC-003', 'كحول إيثيلي 70%', 30, 'زجاجة'),
        ('GZ-004', 'شاش معقم', 200, 'قطعة'),
        ('SYR-005', 'سرنجات 3 سم', 500, 'وحدة')
    ]
    for code, name, qty, unit in items:
        try:
            cursor.execute("""
                INSERT INTO Inventory (item_code, item_name, quantity, unit, expiry_date)
                VALUES (?, ?, ?, ?, '2027-12-31')
            """, (code, name, qty, unit))
        except Exception as e:
            print(f"تخطي صنف مخزون: {e}")

    # 3. إضافة مواعيد وهمية
    for _ in range(15):
        if not patients_ids: break
        p_id = random.choice(patients_ids)
        a_date = fake.date_this_month().strftime('%Y-%m-%d')
        a_time = f"{random.randint(9, 21)}:00"
        status = random.choice(['قادم', 'تم الكشف'])
        
        try:
            cursor.execute("""
                INSERT INTO appointments (PatientID, AppDate, AppTime, [Status], Notes)
                VALUES (?, ?, ?, ?, ?)
            """, (p_id, a_date, a_time, status, "فحص روتيني"))
        except Exception as e:
            print(f"تخطي موعد: {e}")

    conn.commit()
    print(f"تم بنجاح! تم إضافة {len(patients_ids)} مريض وبياناتهم.")

if __name__ == "__main__":
    seed_data()