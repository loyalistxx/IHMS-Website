from flask import Flask, render_template, request, redirect, url_for, flash, session
import pyodbc
from datetime import date

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

# --- 2. المسارات (Routes) ---
db = get_db_connection()

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
                session['admin_logged_in'] = True # إضافة علامة للأدمن
                return redirect(url_for('admin_dashboard'))
        else:
            # تسجيل دخول المريض من الصفحة الرئيسية
            cursor.execute("SELECT * FROM Patients WHERE NationalID = ? AND [Password] = ?", (username, password))
            patient = cursor.fetchone()
            if patient:
                session['patient_id'] = patient.NationalID
                session['patient_name'] = patient.FullName
                # التوجيه للـ Dashboard وليس الـ Portal القديم
                return redirect(url_for('patient_dashboard'))

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
@app.route('/patients')
def patients_list():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # استخدام الأسماء الأصلية للأعمدة كما هي في SQL Server
        cursor.execute("SELECT PatientID, NationalID, FullName, BirthDate, Gender, Phone, blood_type FROM Patients")
        rows = cursor.fetchall()
        
        patients = []
        for row in rows:
            patients.append({
                'id': row.PatientID,
                'national_id': row.NationalID, # لاحظ استخدام الاسم الأصلي هنا
                'name': row.FullName,
                'birth_date': row.BirthDate,
                'gender': row.Gender,
                'phone': row.Phone,
                'blood_type': row.blood_type
            })
        conn.close()
        return render_template('patients.html', patients=patients)
    except Exception as e:
        print(f"Error fetching patients: {e}")
        return f"حدث خطأ أثناء جلب البيانات: {e}"

# إضافة مريض جديد
@app.route('/patients/add', methods=['POST'])
def add_patient():
    if request.method == 'POST':
        # استخراج كافة البيانات من النموذج
        national_id = request.form.get('national_id')
        full_name = request.form.get('full_name')
        password = request.form.get('password')
        phone = request.form.get('phone')
        gender = request.form.get('gender')
        birth_date = request.form.get('birth_date')
        blood_type = request.form.get('blood_type')
        medical_history = request.form.get('medical_history')

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # إدخال البيانات مع مراعاة أسماء الأعمدة الدقيقة في جدولك
            query = """
                INSERT INTO Patients (NationalID, FullName, [Password], Phone, Gender, BirthDate, blood_type, medical_history)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            cursor.execute(query, (national_id, full_name, password, phone, gender, birth_date, blood_type, medical_history))
            
            conn.commit()
            conn.close()
            flash('تم تسجيل المريض بنجاح بكافة بياناته')
        except Exception as e:
            print(f"Database Error: {e}")
            flash(f'خطأ في الإضافة: {str(e)}')
            
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
    # استقبال البيانات الجديدة من الـ Modal
    fullname = request.form.get('fullname')
    phone = request.form.get('phone')
    gender = request.form.get('gender')
    birth_date = request.form.get('birth_date')
    blood_type = request.form.get('blood_type')
    medical_history = request.form.get('medical_history')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # تحديث الجدول باستخدام NationalID كمعرف (id)
        query = """
            UPDATE Patients 
            SET FullName = ?, Phone = ?, Gender = ?, BirthDate = ?, blood_type = ?, medical_history = ?
            WHERE NationalID = ?
        """
        cursor.execute(query, (fullname, phone, gender, birth_date, blood_type, medical_history, id))
        
        conn.commit()
        conn.close()
        flash("تم تحديث بيانات المريض بنجاح", "success")
    except Exception as e:
        print(f"Update Error: {e}")
        flash("فشل في تحديث البيانات", "danger")
        
    return redirect(url_for('patients_list'))

# إدارة المواعيد
@app.route('/admin/appointments')
def appointments_list():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # جلب المواعيد مع اسم المريض باستخدام JOIN
        # ملاحظة: نربط a.PatientID بـ p.NationalID حسب تصميمك
        query_apps = """
        SELECT a.AppointmentID, p.FullName, p.NationalID,
               CONVERT(VARCHAR, a.AppDate, 23) AS AppDate, 
               LEFT(CONVERT(VARCHAR, a.AppTime, 108), 5) AS AppTime, 
               a.[Status], a.Notes
        FROM appointments a
        INNER JOIN Patients p ON a.PatientID = p.NationalID
        ORDER BY a.AppDate ASC, a.AppTime ASC
        """
        cursor.execute(query_apps)
        rows = cursor.fetchall()
        appointments = []
        for row in rows:
            appointments.append({
                'id': row.AppointmentID,
                'patient_name': row.FullName,
                'national_id': row.NationalID,
                'date': row.AppDate,
                'time': row.AppTime,
                'status': row.Status,
                'notes': row.Notes
            })

        # جلب قائمة المرضى لاستخدامها في الـ Dropdown عند إضافة موعد
        cursor.execute("SELECT NationalID, FullName FROM Patients")
        all_patients = [{"id": r.NationalID, "name": r.FullName} for r in cursor.fetchall()]
        
        conn.close()
        return render_template('appointments.html', appointments=appointments, patients=all_patients)

    except Exception as e:
        print(f"Error: {e}")
        return f"حدث خطأ في جلب المواعيد: {e}"

# إضافة موعد جديد
@app.route('/add_appointment', methods=['POST'])
def add_appointment():
    patient_id = request.form.get('patient_id') # هذا هو NationalID المختار
    app_date = request.form.get('app_date')
    app_time = request.form.get('app_time')
    notes = request.form.get('notes', '')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # الحالة الافتراضية عند الحجز هي 'قادم'
        query = """
        INSERT INTO appointments (PatientID, AppDate, AppTime, [Status], Notes)
        VALUES (?, ?, ?, ?, ?)
        """
        cursor.execute(query, (patient_id, app_date, app_time, 'قادم', notes))
        conn.commit()
        conn.close()
        flash("تم حجز الموعد بنجاح!", "success")
    except Exception as e:
        print(f"Error: {e}")
        flash(f"حدث خطأ: {str(e)}", "danger")
        
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

# تحديث حالة الموعد فقط (مثلاً من قائمة المواعيد)
@app.route('/admin/update_appointment_status/<int:id>', methods=['POST'])
def update_appointment_status(id):
    new_status = request.form.get('status')
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE appointments SET Status = ? WHERE AppointmentID = ?", (new_status, id))
        conn.commit()
        conn.close()
        flash("تم تحديث حالة الموعد", "success")
    except Exception as e:
        flash(f"خطأ: {e}", "danger")
    return redirect(url_for('appointments_list'))

# إدارة المخزون
@app.route('/inventory')
def inventory():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. تأكد من جلب العمود 'id' من الجدول
    cursor.execute("SELECT id, item_code, item_name, quantity, unit, expiry_date FROM Inventory")
    rows = cursor.fetchall()
    
    items = []
    low_stock_count = 0
    out_of_stock_count = 0
    
    for row in rows:
        item = {
            'id': row.id,              # 2. هذا هو السطر الناقص الذي يسبب الخطأ
            'code': row.item_code,
            'name': row.item_name,
            'quantity': row.quantity,
            'unit': row.unit,
            'expiry_date': row.expiry_date
        }
        items.append(item)
        
        if row.quantity <= 0:
            out_of_stock_count += 1
        elif row.quantity < 20:
            low_stock_count += 1

    conn.close()
    return render_template('inventory.html', 
                           items=items, 
                           total_items=len(items), 
                           low_stock_count=low_stock_count, 
                           out_of_stock_count=out_of_stock_count)
    
# إضافة صنف جديد إلى المخزون
@app.route('/inventory/add', methods=['POST'])
def add_inventory_item():
    if request.method == 'POST':
        item_code = request.form.get('item_code')
        item_name = request.form.get('item_name')
        quantity = request.form.get('quantity')
        unit = request.form.get('unit')
        expiry_date = request.form.get('expiry_date')

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # إدخال البيانات في الجدول
            cursor.execute("""
                INSERT INTO Inventory (item_code, item_name, quantity, unit, expiry_date)
                VALUES (?, ?, ?, ?, ?)
            """, (item_code, item_name, quantity, unit, expiry_date))
            
            conn.commit()
            conn.close()
            
            flash('تمت إضافة الصنف بنجاح في SQL Server!')
            
            # ملاحظة: هنا يمكنك إضافة كود المزامنة مع Odoo API مستقبلاً
            
        except Exception as e:
            flash(f'حدث خطأ أثناء الحفظ: {str(e)}')
        
        return redirect(url_for('inventory'))
    
# تعديل بيانات صنف موجود
@app.route('/inventory/update', methods=['POST'])
def update_inventory():
    if request.method == 'POST':
        item_id = request.form.get('item_id') # نحتاج الـ ID للتعديل
        item_name = request.form.get('item_name')
        quantity = request.form.get('quantity')
        unit = request.form.get('unit')
        expiry_date = request.form.get('expiry_date')

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE Inventory 
                SET item_name = ?, quantity = ?, unit = ?, expiry_date = ?
                WHERE id = ?
            """, (item_name, quantity, unit, expiry_date, item_id))
            conn.commit()
            conn.close()
            flash('تم تحديث بيانات الصنف بنجاح')
        except Exception as e:
            flash(f'خطأ في التحديث: {str(e)}')
            
        return redirect(url_for('inventory'))

# حذف صنف من المخزون
@app.route('/inventory/delete/<int:id>')
def delete_item(id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # تنفيذ أمر الحذف بناءً على الـ ID
        cursor.execute("DELETE FROM Inventory WHERE id = ?", (id,))
        
        conn.commit()
        conn.close()
        flash('تم حذف الصنف بنجاح')
    except Exception as e:
        flash(f'حدث خطأ أثناء الحذف: {str(e)}')
    
    return redirect(url_for('inventory'))
    
# إدارة المواعيد
@app.route('/admin/appointments')
def appointments():
    return render_template('appointments.html')


# تسجيل دخول المريض
@app.route('/patient/login', methods=['GET', 'POST'])
def patient_login():
    if request.method == 'POST':
        national_id = request.form.get('national_id')
        password = request.form.get('password')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        # نستخدم الحقول التي أضفتها أنت في الجدول [NationalID] و [Password]
        cursor.execute("SELECT * FROM Patients WHERE NationalID = ? AND [Password] = ?", (national_id, password))
        patient = cursor.fetchone()
        conn.close()
        
        if patient:
            # تخزين بيانات المريض في الجلسة (Session) للتعرف عليه في الـ Dashboard
            session['patient_id'] = patient.NationalID
            session['patient_name'] = patient.FullName
            return redirect(url_for('patient_dashboard'))
        else:
            flash("الرقم القومي أو كلمة المرور غير صحيحة", "danger")
            
    return render_template('login.html')

# لوحة تحكم المريض
@app.route('/patient/dashboard')
def patient_dashboard():
    # منع الدخول المباشر بدون تسجيل دخول
    if 'patient_id' not in session:
        return redirect(url_for('patient_login'))
    
    p_id = session['patient_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # جلب بيانات الملف الشخصي
    cursor.execute("SELECT * FROM Patients WHERE NationalID = ?", (p_id,))
    profile = cursor.fetchone()
    
    # جلب المواعيد الخاصة بهذا المريض فقط
    cursor.execute("SELECT AppointmentID, CONVERT(VARCHAR, AppDate, 23) as AppDate, LEFT(CONVERT(VARCHAR, AppTime, 108), 5) as AppTime, [Status] FROM appointments WHERE PatientID = ? ORDER BY AppDate DESC", (p_id,))
    apps = cursor.fetchall()
    
    conn.close()
    return render_template('patient_portal.html', profile=profile, appointments=apps)

# حجز موعد جديد من قبل المريض
@app.route('/patient/book', methods=['GET', 'POST'])
def book_appointment():
    # التأكد من أن المريض مسجل دخوله
    if 'patient_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        app_date = request.form.get('app_date')
        app_time = request.form.get('app_time')
        notes = request.form.get('notes')
        p_id = session['patient_id']

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # إدخال الموعد الجديد بـ Status افتراضي 'قادم'
            query = """
                INSERT INTO appointments (PatientID, AppDate, AppTime, [Status], Notes)
                VALUES (?, ?, ?, 'قادم', ?)
            """
            cursor.execute(query, (p_id, app_date, app_time, notes))
            conn.commit()
            conn.close()
            
            flash("تم حجز موعدك بنجاح! يمكنك رؤيته في جدول مواعيدك الآن.", "success")
            return redirect(url_for('patient_portal'))
            
        except Exception as e:
            print(f"Booking Error: {e}")
            flash("حدث خطأ أثناء الحجز، يرجى المحاولة مرة أخرى.", "danger")
            return redirect(url_for('book_appointment'))

    # لإرسال تاريخ اليوم لمنع الحجز في الماضي في الـ HTML
    return render_template('book_appointment.html', current_date=date.today().isoformat())

# تسجيل الخروج
@app.route('/patient/logout')
def patient_logout():
    session.clear()
    return redirect(url_for('patient_login'))


# --- 3. تشغيل السيرفر (يجب أن يكون في آخر الملف) ---
if __name__ == '__main__':
    app.run(debug=True, threaded=True) # Threaded يجعل التعامل مع الطلبات أسرع