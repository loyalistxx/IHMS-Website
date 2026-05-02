import pyodbc
import random
from faker import Faker

fake = Faker()

def fill_appointments_from_db():
    try:
        # 1. الاتصال بقاعدة البيانات (تأكد من بيانات الاتصال الخاصة بك)
        conn_str = (
        "Driver={ODBC Driver 17 for SQL Server};" # هذا التعريف أكثر استقراراً مع بايثون
        "Server=ADHAM\\MSSQLSERVER01;"
        "Database=IHMS;"
        "Trusted_Connection=yes;"
    )
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # 2. جلب الأرقام القومية الموجودة فعلياً في جدول Patients
        cursor.execute("SELECT NationalID FROM Patients")
        # تخزين الأرقام في قائمة
        existing_national_ids = [row[0] for row in cursor.fetchall()]

        if not existing_national_ids:
            print("❌ لا يوجد مرضى في القاعدة! أضف مرضى أولاً.")
            return

        print(f"✅ تم العثور على {len(existing_national_ids)} مريض. جاري إنشاء المواعيد...")

        statuses = ['قادم', 'تم الكشف', 'ملغي']
        sample_notes = ["Routine check-up", "Follow-up", "Needs surgery consultation", "Lab results review"]

        # 3. إنشاء 30 موعد عشوائي بناءً على البيانات الحقيقية
        for _ in range(30):
            # اختيار رقم قومي عشوائي من القائمة التي جلبناها
            n_id = random.choice(existing_national_ids)
            
            app_date = fake.date_between(start_date='-10d', end_date='+20d').isoformat()
            app_time = f"{random.randint(9, 21):02}:{random.choice(['00', '30'])}:00"
            status = random.choice(statuses)
            notes = random.choice(sample_notes)

            # تنفيذ الإدخال مباشرة
            # ملاحظة: إذا كان اسم العمود في جدول Appointments هو PatientID ولكنه يستقبل NationalID
            query = """
                INSERT INTO Appointments (PatientID, AppDate, AppTime, [Status], Notes)
                VALUES (?, ?, ?, N'{}', N'{}')
            """.format(status, notes)
            
            cursor.execute(query, (n_id, app_date, app_time))

        conn.commit()
        print("🚀 تم ملء 30 موعداً بنجاح دون أي تعارض!")
        
    except Exception as e:
        print(f"❌ حدث خطأ: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

# تشغيل الدالة
fill_appointments_from_db()