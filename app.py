from flask import Flask, render_template, request, redirect, url_for, flash, session
import pyodbc
from datetime import datetime, date

app = Flask(__name__)

app.secret_key = "secret_key_for_session"

#  إعداد الاتصال بقاعدة البيانات
def get_db_connection():
    conn_str = (
        "Driver={ODBC Driver 17 for SQL Server};" # هذا التعريف أكثر استقراراً مع بايثون
        "Server=ADHAM\\MSSQLSERVER01;"
        "Database=IHMS;"
        "Trusted_Connection=yes;"
    )
    # إذا لم يعمل Driver 17، جرب SQL Server Native Client 11.0
    return pyodbc.connect(conn_str)

# صفحة الرئيسية
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    return render_template('login.html')

# معالجة عملية تسجيل الدخول
@app.route('/login', methods=['POST'])
def handle_login():
    username = request.form.get('username')
    password = request.form.get('password')
    role = request.form.get('role')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if role == 'admin':
            # نبحث عن المدير في جدول Users
            cursor.execute("SELECT Username, FullName FROM Users WHERE Username = ? AND Password = ?", (username, password))
            admin = cursor.fetchone()
            
            if admin:
                session['admin_logged_in'] = True
                # تخزين اسم المستخدم أو الاسم الكامل لعرضه في الترحيب
                session['admin_username'] = admin.Username
                session['admin_name'] = admin.FullName if hasattr(admin, 'FullName') else admin.Username
                
                return redirect(url_for('admin_dashboard'))
        else:
            # تسجيل دخول المريض
            cursor.execute("SELECT NationalID, FullName FROM Patients WHERE NationalID = ? AND [Password] = ?", (username, password))
            patient = cursor.fetchone()
            
            if patient:
                session['patient_id'] = patient.NationalID
                session['patient_name'] = patient.FullName
                return redirect(url_for('patient_portal'))

        # إذا لم يجد المستخدم في الحالتين
        flash("خطأ في اسم المستخدم أو كلمة المرور", "danger")
        return redirect(url_for('login'))

    except Exception as e:
        print(f"Database Error: {e}")
        flash("حدث خطأ في الاتصال بقاعدة البيانات", "warning")
        return redirect(url_for('login'))
    finally:
        conn.close()
# لوحة التحكم
# لوحة التحكم المحدثة
@app.route('/admin/dashboard')
def admin_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. إجمالي المرضى
    cursor.execute("SELECT COUNT(*) FROM Patients")
    total_patients = cursor.fetchone()[0]

    # 2. مواعيد اليوم
    cursor.execute("SELECT COUNT(*) FROM appointments WHERE AppDate = CAST(GETDATE() AS DATE)")
    today_apps = cursor.fetchone()[0]

    # 3. نواقص المخزون (الأصناف التي كميتها أقل من 20 مثلاً)
    cursor.execute("SELECT COUNT(*) FROM Inventory WHERE quantity > 0 AND quantity < 20")
    low_stock = cursor.fetchone()[0]

    # 4. كشوفات تمت (إجمالي المواعيد التي حالتها 'تم الكشف')
    cursor.execute("SELECT COUNT(*) FROM appointments WHERE [Status] = N'تم الكشف'")
    completed_apps = cursor.fetchone()[0]

    # 5. جلب آخر 5 مواعيد لعرضها في الجدول
    query_latest = """
    SELECT TOP 5 p.FullName, 
           CONVERT(VARCHAR, a.AppDate, 23) AS AppDate, 
           LEFT(CONVERT(VARCHAR, a.AppTime, 108), 5) AS AppTime, 
           a.[Status]
    FROM appointments a
    INNER JOIN Patients p ON a.PatientID = p.NationalID
    ORDER BY a.AppDate DESC, a.AppTime DESC
    """
    cursor.execute(query_latest)
    rows = cursor.fetchall()
    
    latest_appointments = []
    for row in rows:
        latest_appointments.append({
            'patient_name': row[0],
            'date': row[1],
            'time': row[2],
            'status': row[3]
        })

    conn.close()
    return render_template('admin.html', 
                           total_patients=total_patients,
                           today_apps=today_apps,
                           low_stock=low_stock,
                           completed_apps=completed_apps,
                           latest_appointments=latest_appointments)

# إدارة المرضى (العرض + البحث) - دالة واحدة فقط
@app.route('/admin/patients')
def patients_list():
    search_query = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT item_name FROM Inventory WHERE quantity > 0")
    inventory_meds = [r[0] for r in cursor.fetchall()]

    cursor.execute("SELECT Username, FullName FROM Users WHERE role = 'Doctor'")
    staff_members = [{"username": r[0], "name": r[1]} for r in cursor.fetchall()]

    # استعلام البحث
    if search_query:
        sql = """
            SELECT * FROM Patients 
            WHERE FullName LIKE ? OR NationalID LIKE ? OR Phone LIKE ?
            ORDER BY FullName
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """
        params = (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%', offset, per_page)
        
        # حساب إجمالي النتائج للبحث
        cursor.execute("SELECT COUNT(*) FROM Patients WHERE FullName LIKE ? OR NationalID LIKE ? OR Phone LIKE ?", 
                       (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
    else:
        sql = "SELECT * FROM Patients ORDER BY FullName OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
        params = (offset, per_page)
        cursor.execute("SELECT COUNT(*) FROM Patients")

    total_patients = cursor.fetchone()[0]
    cursor.execute(sql, params)
    patients_data = cursor.fetchall()
    
    total_pages = (total_patients + per_page - 1) // per_page

    # تحويل البيانات لتناسب القالب
    patients = []
    for p in patients_data:
        patients.append({
            'national_id': p.NationalID,
            'name': p.FullName,
            'gender': p.Gender,
            'phone': p.Phone,
            'blood_type': p.blood_type,     
            'birth_date': p.BirthDate,
            'medical_history': p.medical_history 
        })

    return render_template('patients.html', 
                           patients=patients, 
                           staff=staff_members,
                           inventory_meds=inventory_meds,
                           page=page, 
                           total_pages=total_pages, 
                           search_query=search_query)
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
            flash('تم تسجيل المريض بنجاح بكافة بياناته', 'success')
        except Exception as e:
            print(f"Database Error: {e}")
            flash(f'خطأ في الإضافة: {str(e)}', 'danger')
            
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
@app.route('/admin/edit_patient/<id>', methods=['GET', 'POST'])
def edit_patient_action(id):
    if request.method == 'POST':
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
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. حساب إجمالي عدد المواعيد
    cursor.execute("SELECT COUNT(*) FROM appointments")
    total_appointments = cursor.fetchone()[0]
    total_pages = (total_appointments + per_page - 1) // per_page

    # 2. جلب المواعيد للصفحة الحالية فقط
    query_apps = """
    SELECT a.AppointmentID, p.FullName, p.NationalID,
           CONVERT(VARCHAR, a.AppDate, 23) AS AppDate, 
           LEFT(CONVERT(VARCHAR, a.AppTime, 108), 5) AS AppTime, 
           a.[Status], a.Notes
    FROM appointments a
    INNER JOIN Patients p ON a.PatientID = p.NationalID
    ORDER BY 
        CASE WHEN a.AppDate = CAST(GETDATE() AS DATE) THEN 0 ELSE 1 END, -- مواعيد اليوم أولاً
        a.AppDate ASC, -- ثم باقي المواعيد مرتبة تصاعدياً حسب التاريخ
        a.AppTime ASC  -- ثم حسب الوقت
    OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
    """
    cursor.execute(query_apps, (offset, per_page))
    rows = cursor.fetchall()
    
    # تحويل البيانات (باستخدام القواميس لتجنب الأخطاء السابقة)
    appointments = []
    for row in rows:
            # الوصول عبر الترتيب الرقمي أضمن وسيلة لتجنب مشاكل الأسماء
            appointments.append({
                'id': row[0],           # AppointmentID
                'patient_name': row[1], # FullName
                'national_id': row[2],  # NationalID
                'date': row[3],         # AppDate
                'time': row[4],         # AppTime
                'status': row[5],       # Status (هذا هو المفتاح المهم)
                'notes': row[6]         # Notes
            })

    # 3. جلب قائمة المرضى للـ Dropdown
    cursor.execute("SELECT NationalID, FullName FROM Patients")
    all_patients = [{"id": r[0], "name": r[1]} for r in cursor.fetchall()]

    conn.close()
    return render_template('appointments.html', 
                           appointments=appointments, 
                           patients=all_patients,
                           page=page,
                           total_pages=total_pages)
    
# تحديث حالة الموعد (مثلاً من "قادم" إلى "تم الكشف")
@app.route('/admin/update_appointment_status/<int:app_id>', methods=['POST'])
def update_appointment_status(app_id):
    new_status = request.form.get('status')
    
    # هذه هي القائمة التي اقترحتها لتكون "فلتر" أمان في الكود
    allowed_statuses = ['قادم', 'تم الكشف', 'الغاء'] 
    
    if new_status not in allowed_statuses:
        flash('خطأ: الحالة المرسلة غير مدعومة', 'danger')
        return redirect(url_for('appointments_list'))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE appointments SET Status = ? WHERE AppointmentID = ?", (new_status, app_id))
        conn.commit()
        flash('تم تحديث الحالة بنجاح', 'success')
    except pyodbc.IntegrityError:
        # هذا الخطأ سيحدث فقط إذا نسيت تحديث الـ Constraint في SQL Server
        flash('خطأ: قاعدة البيانات ترفض هذه الحالة (تأكد من تعديل الـ Constraint)', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('appointments_list'))

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

# تأكيد الكشف وتحديث سجل المريض تلقائياً من قبل الأدمن
@app.route('/admin/complete_appointment/<int:app_id>')
def complete_appointment(app_id):
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # نستخدم الكلمة المطابقة تماماً للـ Constraint
        new_status = 'تم الكشف' 

        # التعديل هنا: نستخدم N قبل علامة الاستهام في الاستعلام لضمان قبول Unicode
        cursor.execute("""
            UPDATE appointments 
            SET [Status] = ? 
            OUTPUT inserted.PatientID, inserted.AppDate
            WHERE AppointmentID = ?
        """, (new_status, app_id))
        
        result = cursor.fetchone()
        
        if result:
            p_id, app_date = result
            cursor.execute("UPDATE Patients SET LastVisit = ? WHERE NationalID = ?", (app_date, p_id))
            # تأكد أن id=1 موجود فعلاً في المخزون
            # إذا كان "مستلزمات عامة" مثلاً الـ ID بتاعه هو 5
            cursor.execute("UPDATE Inventory SET quantity = quantity - 1 WHERE id = 2 AND quantity > 0")
            
        conn.commit()
        conn.close()
        flash("تم تأكيد الكشف بنجاح", "success")
    except Exception as e:
        flash(f"حدث خطأ: {str(e)}", "danger")
        
    return redirect(url_for('appointments_list'))

# إدارة المخزون
@app.get('/inventory')
def inventory():
    # 1. جلب متغيرات البحث والصفحة من الرابط
    search_query = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 2. بناء استعلام البحث (البحث في الاسم أو الكود)
    base_sql = "FROM Inventory"
    params = []
    
    if search_query:
        base_sql += " WHERE item_name LIKE ? OR item_code LIKE ?"
        params.extend([f'%{search_query}%', f'%{search_query}%'])

    # 3. حساب إجمالي العناصر بناءً على البحث
    cursor.execute(f"SELECT COUNT(*) {base_sql}", params)
    total_items = cursor.fetchone()[0]
    total_pages = (total_items + per_page - 1) // per_page if total_items > 0 else 1

    # 4. جلب البيانات المفلترة مع Pagination (متوافق مع SQL Server)
    # نكرر البارامترات لأننا نستخدمها مرة أخرى في استعلام البيانات
    data_params = params + [offset, per_page]
    query = f"""
        SELECT id, item_code, item_name, quantity, unit, expiry_date 
        {base_sql}
        ORDER BY id DESC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
    """
    cursor.execute(query, data_params)
    rows = cursor.fetchall()
    
    # 5. حساب النواقص (للمخزن بالكامل بغض النظر عن البحث)
    cursor.execute("SELECT COUNT(*) FROM Inventory WHERE quantity > 0 AND quantity < 20")
    low_stock_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM Inventory WHERE quantity <= 0")
    out_of_stock_count = cursor.fetchone()[0]

    items = []
    for row in rows:
        items.append({
            'id': row.id,
            'code': row.item_code,
            'name': row.item_name,
            'quantity': row.quantity,
            'unit': row.unit,
            'expiry_date': row.expiry_date
        })

    conn.close()
    
    return render_template('inventory.html', 
                           items=items, 
                           total_items=total_items, 
                           low_stock_count=low_stock_count, 
                           out_of_stock_count=out_of_stock_count,
                           page=page,
                           total_pages=total_pages,
                           search_query=search_query) # نرسل نص البحث ليبقى في الخانة
    
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
            return redirect(url_for('patient_portal'))
        else:
            flash("الرقم القومي أو كلمة المرور غير صحيحة", "danger")
            
    return render_template('login.html')

# لوحة تحكم المريض
# تغيير اسم الدالة ليتوافق مع ما تريده
@app.route('/patient/dashboard')
def patient_portal():
    patient_id = session.get('patient_id')
    if not patient_id:
        return redirect(url_for('login'))
    
    now_date = datetime.now().strftime('%Y-%m-%d')
    
    p_id = session['patient_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT TOP 1 AppDate, AppTime, Status 
        FROM Appointments 
        WHERE PatientID = ? 
        AND Status = N'قادم' 
        AND AppDate >= ?
        ORDER BY AppDate ASC, AppTime ASC
    """, (patient_id, now_date))
    
    upcoming_appointment = cursor.fetchone()
    
    # 1. بيانات المريض
    cursor.execute("SELECT * FROM Patients WHERE NationalID = ?", (p_id,))
    patient = cursor.fetchone()

    # 2. التشخيصات
    cursor.execute("SELECT TOP 3 Diagnosis, VisitDate FROM MedicalRecords WHERE PatientID = ? ORDER BY VisitDate DESC", (p_id,))
    diagnoses = cursor.fetchall()

    # 3. الأدوية
    cursor.execute("SELECT TOP 5 MedicationName, Dosage FROM Medications WHERE PatientID = ?", (p_id,))
    medications = cursor.fetchall()

    # 4. نتائج التحاليل
    cursor.execute("SELECT TOP 3 TestName, Result FROM LabResults WHERE PatientID = ? ORDER BY TestDate DESC", (p_id,))
    lab_results = cursor.fetchall()

    # 5. المواعيد (ده الجزء اللي كان ناقص ومسبب الخطأ)
    cursor.execute("SELECT TOP 3 AppDate, Status FROM Appointments WHERE PatientID = ? ORDER BY AppDate DESC", (p_id,))
    appointments = cursor.fetchall()

    conn.close()
    
    # تأكد من إضافة appointments=appointments هنا
    return render_template('patient_portal.html',
                           appointment=upcoming_appointment, 
                           profile=patient, 
                           diagnoses=diagnoses, 
                           medications=medications, 
                           lab_results=lab_results,
                           appointments=appointments)

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
                VALUES (?, ?, ?, N'قادم', ?)
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

# عرض مواعيد المريض في صفحة الـ Dashboard الخاصة به
@app.route('/patient/my-appointments')
def my_appointments():
    if 'patient_id' not in session:
        return redirect(url_for('patient_login'))
    
    p_id = session['patient_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT AppointmentID, 
               CONVERT(VARCHAR, AppDate, 23) as AppDate, 
               LEFT(CONVERT(VARCHAR, AppTime, 108), 5) as AppTime, 
               [Status], Notes
        FROM appointments 
        WHERE PatientID = ? 
        ORDER BY AppDate DESC, AppTime DESC
    """, (p_id,))
    
    # تحويل البيانات لقاموس لسهولة التعامل في HTML
    apps = []
    for row in cursor.fetchall():
        apps.append({
            'id': row.AppointmentID,
            'date': row.AppDate,
            'time': row.AppTime,
            'status': row.Status,
            'notes': row.Notes
        })
    
    conn.close()
    return render_template('my_appointments.html', appointments=apps)

@app.route('/cancel_appointment/<int:appointment_id>')
def cancel_appointment(appointment_id):
    patient_id = session.get('patient_id')
    if not patient_id:
        return redirect(url_for('login'))

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # تحويل المعرفات إلى int للتأكد من توافقها مع قاعدة البيانات
        app_id = int(appointment_id)
        p_id = int(patient_id)

        # تنفيذ التحديث
        cursor.execute("""
            UPDATE Appointments 
            SET Status = N'ملغي' 
            WHERE AppointmentID = ? AND PatientID = ? AND Status = N'قادم'
        """, (app_id, p_id))
        
        conn.commit()
        
        # التأكد إذا كان هناك سطر تأثر فعلاً (لو لم يتأثر سطر يعني الشرط لم يتحقق)
        if cursor.rowcount == 0:
            flash("لم يتم العثور على الموعد أو لا يمكن إلغاؤه", "warning")
        else:
            flash("تم إلغاء الموعد بنجاح", "success")

    except Exception as e:
        # هذا السطر سيطبع لك الخطأ الحقيقي في شاشة الـ VS Code أو الـ CMD
        print("SQL Error details:", str(e)) 
        flash(f"حدث خطأ برمجى: {str(e)}", "danger")
    finally:
        if conn:
            conn.close()
            
    return redirect(url_for('my_appointments'))

# عرض الملف الشخصي للمريض
@app.route('/patient/profile')
def patient_profile():
    if 'patient_id' not in session:
        return redirect(url_for('patient_login'))
    
    p_id = session['patient_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query_basic = """
    SELECT p.*, 
           (SELECT TOP 1 AppDate FROM appointments WHERE PatientID = p.NationalID ORDER BY AppDate DESC) as LastVisit,
           (SELECT TOP 1 Notes FROM appointments WHERE PatientID = p.NationalID AND Notes IS NOT NULL AND Notes != '' ORDER BY AppDate DESC) as LastNotes
    FROM Patients p WHERE p.NationalID = ?
    """
    
    cursor.execute(query_basic, (p_id,))
    columns = [column[0] for column in cursor.description]
    row = cursor.fetchone()
    patient_data = dict(zip(columns, row)) if row else None
    
    if not patient_data:
        conn.close()
        return redirect(url_for('patient_portal'))

    # 2. جلب التشخيصات (النتائج)
    cursor.execute("SELECT Diagnosis, VisitDate FROM MedicalRecords WHERE PatientID = ? ORDER BY VisitDate DESC", (p_id,))
    diagnoses = [{"diagnosis": r[0], "date": r[1]} for r in cursor.fetchall()]

    # 3. جلب الأدوية
    cursor.execute("SELECT MedicationName, Dosage FROM Medications WHERE PatientID = ?", (p_id,))
    medications = [{"name": r[0], "dosage": r[1]} for r in cursor.fetchall()]

    # 4. جلب نتائج التحاليل (التقارير)
    cursor.execute("SELECT TestName, Result FROM LabResults WHERE PatientID = ? ORDER BY TestDate DESC", (p_id,))
    lab_results = [{"test": r[0], "result": r[1]} for r in cursor.fetchall()]

    conn.close()
    
    return render_template('patient_profile.html',
                           patient=patient_data, 
                           diagnoses=diagnoses, 
                           medications=medications, 
                           lab_results=lab_results)
    
# إدارة التشخيصات (إضافة/حذف) من قبل الأدمن    
@app.route('/admin/diagnosis/<action>/<patient_id>', methods=['POST'])
def manage_diagnosis(action, patient_id):
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if action == 'add':
            diagnosis = request.form.get('diagnosis')
            # جدول MedicalRecords اللي إنت بتستخدمه في الـ Dashboard
            cursor.execute("""
                INSERT INTO MedicalRecords (PatientID, Diagnosis, VisitDate) 
                VALUES (?, ?, GETDATE())
            """, (patient_id, diagnosis))
            flash("تم إضافة التشخيص بنجاح", "success")
            
        elif action == 'delete':
            # هنمسح بناءً على معرف السجل الفرعي (لو متاح) أو آخر سجل للمريض
            record_id = request.form.get('record_id')
            cursor.execute("DELETE FROM MedicalRecords WHERE RecordID = ?", (record_id,))
            flash("تم حذف التشخيص", "info")
            
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error in manage_diagnosis: {e}")
        flash("حدث خطأ أثناء معالجة البيانات", "danger")
    finally:
        conn.close()
        
    return redirect(url_for('patients_list'))

@app.route('/admin/lab_results/<action>/<patient_id>', methods=['POST'])
def manage_lab_results(action, patient_id):
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if action == 'add':
            test_name = request.form.get('test_name')
            result = request.form.get('result')
            added_by = request.form.get('added_by')
            
            cursor.execute("""
                INSERT INTO LabResults (PatientID, TestName, Result, TestDate, AddedBy) 
                VALUES (?, ?, ?, GETDATE(), ?)
            """, (patient_id, test_name, result, added_by))
            flash("تم تسجيل نتيجة التحليل بنجاح", "success")
            
        elif action == 'delete':
            # الحذف بيتم عن طريق معرف السجل الفريد للتحليل
            lab_id = request.form.get('lab_id')
            cursor.execute("DELETE FROM LabResults WHERE LabID = ?", (lab_id,))
            flash("تم حذف نتيجة التحليل", "info")
            
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error in manage_lab_results: {e}")
        flash("حدث خطأ أثناء معالجة بيانات التحاليل", "danger")
    finally:
        conn.close()
        
    return redirect(url_for('patients_list'))

@app.route('/admin/medications/<action>/<patient_id>', methods=['POST'])
def manage_medications(action, patient_id):
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if action == 'add':
            med_name = request.form.get('medication_name')
            dosage = request.form.get('dosage')
            prescribed_by = request.form.get('prescribed_by')
            
            # تأكد من أن أسماء الأعمدة (PatientID, MedicationName...) 
            # هي نفس الأسماء الموجودة في جدول Medications عندك
            cursor.execute("""
                INSERT INTO Medications (PatientID, MedicationName, Dosage, PrescribedBy, DatePrescribed) 
                VALUES (?, ?, ?, ?, GETDATE())
            """, (patient_id, med_name, dosage, prescribed_by))
            
            flash("تم إضافة الدواء للروشتة بنجاح", "success")
            
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error Details: {e}") # هذا سيطبع الخطأ الحقيقي في الـ Terminal عندك
        flash("حدث خطأ أثناء معالجة بيانات الأدوية", "danger")
    finally:
        conn.close()
        
    return redirect(url_for('patients_list'))

# تسجيل الخروج
@app.route('/patient/logout')
def patient_logout():
    session.clear() # مسح كل بيانات الجلسة
    flash("تم تسجيل الخروج بنجاح", "info")
    return redirect(url_for('patient_login'))


# --- 3. تشغيل السيرفر (يجب أن يكون في آخر الملف) ---
if __name__ == '__main__':
    app.run(debug=True, threaded=True) # Threaded يجعل التعامل مع الطلبات أسرع