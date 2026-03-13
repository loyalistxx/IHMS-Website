from flask import Flask, render_template, request, redirect, url_for, flash
import pyodbc

app = Flask(__name__)
app.secret_key = "secret_key_for_session"

# --- 1. إعداد الاتصال بقاعدة البيانات ---
def get_db_connection():
    conn_str = (
        "Driver={SQL Server};"
        "Server=ADHAM\\MSSQLSERVER01;"
        "Database=IHMS;"
        "Trusted_Connection=yes;"
    )
    return pyodbc.connect(conn_str)
db = get_db_connection()
# --- 2. المسارات (Routes) ---

# صفحة تسجيل الدخول
@app.route('/')
def login():
    return render_template('login.html')

# معالجة عملية تسجيل الدخول
@app.route('/login', methods=['POST'])
def handle_login():
    username = request.form.get('username')
    password = request.form.get('password')
    role = request.form.get('userRole')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if role == 'admin':
            cursor.execute("SELECT * FROM Users WHERE Username = ? AND Password = ?", (username, password))
            user = cursor.fetchone()
            if user:
                return redirect(url_for('admin_dashboard'))
        else:
            cursor.execute("SELECT * FROM Patients WHERE NationalID = ? AND Password = ?", (username, password))
            patient = cursor.fetchone()
            if patient:
                return redirect(url_for('patient_portal'))

        flash("خطأ في اسم المستخدم أو كلمة المرور", "danger")
        return redirect(url_for('login'))

    except Exception as e:
        print(f"Database Error: {e}")
        flash("حدث خطأ في الاتصال بقاعدة البيانات", "warning")
        return redirect(url_for('login'))

# لوحة التحكم
@app.route('/admin/dashboard')
def admin_dashboard():
    return render_template('admin.html')

# إدارة المرضى (العرض + البحث) - دالة واحدة فقط
@app.route('/admin/patients')
def patients_list():
    search_query = request.args.get('search') 
    conn = None # تعريف المتغير خارج Try لضمان إغلاقه
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # أضفنا عمود Phone هنا لكي يعمل الـ Update Modal
        query = "SELECT NationalID, FullName, Gender, BirthDate, Phone FROM Patients"
        
        if search_query:
            cursor.execute(query + " WHERE NationalID LIKE ?", (f'%{search_query}%',))
        else:
            cursor.execute(query)
            
        data = cursor.fetchall()
        return render_template('patients.html', patients=data)
    except Exception as e:
        print(f"Database Error: {e}")
        return render_template('patients.html', patients=[])
    finally:
        if conn: conn.close() # إغلاق آمن وسريع

# إضافة مريض جديد
@app.route('/admin/add_patient', methods=['POST'])
def add_patient_action():
    fullname = request.form.get('fullname')
    national_id = request.form.get('national_id')
    gender = request.form.get('gender')
    birth_date = request.form.get('birth_date')
    phone = request.form.get('phone')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Patients (FullName, NationalID, Gender, BirthDate, Phone, Password) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (fullname, national_id, gender, birth_date, phone, 'p123'))
        conn.commit()
        flash("تم إضافة المريض بنجاح!", "success")
    except Exception as e:
        print(f"Error adding patient: {e}")
        flash("حدث خطأ أثناء الإضافة", "danger")
    conn.close()
    return redirect(url_for('patients_list'))

# حذف مريض
@app.route('/admin/delete_patient/<id>')
def delete_patient(id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Patients WHERE NationalID = ?", (id,))
        conn.commit()
        flash("تم حذف المريض بنجاح", "info")
    except Exception as e:
        print(f"Delete Error: {e}")
        flash("فشل حذف المريض", "danger")
    conn.close()
    return redirect(url_for('patients_list'))

# تعديل بيانات المريض
@app.route('/admin/edit_patient/<id>', methods=['POST'])
def edit_patient_action(id):
    fullname = request.form.get('fullname')
    gender = request.form.get('gender')
    birth_date = request.form.get('birth_date')
    phone = request.form.get('phone')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Patients 
            SET FullName = ?, Gender = ?, BirthDate = ?, Phone = ?
            WHERE NationalID = ?
        """, (fullname, gender, birth_date, phone, id))
        conn.commit()
        flash("تم تحديث بيانات المريض بنجاح", "success")
    except Exception as e:
        print(f"Update Error: {e}")
        flash("فشل في تحديث البيانات", "danger")
    conn.close()
    return redirect(url_for('patients_list'))
# إدارة المواعيد
@app.route('/admin/appointments')
def appointments_list():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. جلب المواعيد الموجودة (مع عمل JOIN لاسم المريض)
        query_apps = """
        SELECT a.AppointmentID, p.FullName, p.NationalID,
               CONVERT(VARCHAR, a.AppDate, 23) AS AppDate, 
               LEFT(CONVERT(VARCHAR, a.AppTime, 108), 5) AS AppTime, 
               a.[Status]
        FROM appointments a
        INNER JOIN patients p ON a.PatientID = p.NationalID
        ORDER BY a.AppDate ASC
        """
        cursor.execute(query_apps)
        columns_apps = [column[0] for column in cursor.description]
        appointments = [dict(zip(columns_apps, row)) for row in cursor.fetchall()]

        # 2. جلب قائمة المرضى للـ Dropdown (هذا هو الجزء المهم)
        # تأكد أن اسم الجدول هو patients وليس Patients (حسب ما هو عندك في DB)
        cursor.execute("SELECT NationalID, FullName FROM patients")
        columns_p = [column[0] for column in cursor.description]
        all_patients = [dict(zip(columns_p, row)) for row in cursor.fetchall()]
        
        return render_template('appointments.html', appointments=appointments, patients=all_patients)

    except Exception as e:
        print(f"Error: {e}")
        return render_template('appointments.html', appointments=[], patients=[])
    finally:
        if conn:
            conn.close()

# إضافة موعد جديد
@app.route('/add_appointment', methods=['POST'])
def add_appointment():
    # استلام البيانات من الـ Form في Modal المواعيد
    patient_id = request.form.get('patient_id')
    app_date = request.form.get('app_date')
    app_time = request.form.get('app_time')
    status = request.form.get('status', 'قادم')
    notes = request.form.get('notes', '')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # استعلام الإدخال
        query = """
        INSERT INTO appointments (PatientID, AppDate, AppTime, [Status], Notes)
        VALUES (?, ?, ?, ?, ?)
        """
        
        cursor.execute(query, (patient_id, app_date, app_time, status, notes))
        conn.commit() # حفظ التغييرات في SQL Server
        conn.close()
        
        flash("تم حجز الموعد بنجاح!", "success")
    except Exception as e:
        flash(f"حدث خطأ أثناء الحجز: {str(e)}", "danger")
        
    return redirect(url_for('appointments_list'))

# تعديل موعد موجود
@app.route('/edit_appointment/<int:id>', methods=['POST'])
def edit_appointment(id):
    app_date = request.form.get('app_date')
    app_time = request.form.get('app_time')
    status = request.form.get('status')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 1. تحديث بيانات الموعد
        query_update_app = """
        UPDATE appointments 
        SET AppDate = ?, AppTime = ?, [Status] = ?
        WHERE AppointmentID = ?
        """
        cursor.execute(query_update_app, (app_date, app_time, status, id))

        # 2. التحديث التلقائي لآخر زيارة 
        # نستخدم النص العادي 'تم الكشف' بدون N لأننا في بايثون
        if status == 'تم الكشف':
            query_update_patient = """
            UPDATE patients 
            SET LastVisit = ? 
            WHERE NationalID = (SELECT PatientID FROM appointments WHERE AppointmentID = ?)
            """
            cursor.execute(query_update_patient, (app_date, id))
        
        conn.commit()
        flash("تم تحديث الموعد بنجاح", "success")
    except Exception as e:
        conn.rollback()
        flash(f"حدث خطأ: {str(e)}", "danger")
    finally:
        conn.close()
        
    return redirect(url_for('appointments_list'))

# إدارة المواعيد
@app.route('/admin/appointments')
def appointments():
    return render_template('appointments.html')

# إدارة المخزون
@app.route('/admin/inventory')
def inventory():
    return render_template('inventory.html')

# بوابة المريض
@app.route('/patient/portal')
def patient_portal():
    return render_template('patient_portal.html')
# --- 3. تشغيل السيرفر (يجب أن يكون في آخر الملف) ---
if __name__ == '__main__':
    app.run(debug=True, threaded=True) # Threaded يجعل التعامل مع الطلبات أسرع