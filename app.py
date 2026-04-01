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
@app.route('/patients')
def patients_list():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT PatientID, NationalID, FullName, BirthDate, gender, phone, blood_type FROM Patients")
    rows = cursor.fetchall()
    
    patients = []
    for row in rows:
        patients.append({
            'id': row.PatientID,
            'NationalID': row.NationalID,
            'name': row.FullName,
            'BirthDate': row.BirthDate,
            'gender': row.gender,
            'phone': row.phone,
            'blood_type': row.blood_type
        })
    conn.close()
    return render_template('patients.html', patients=patients)

# إضافة مريض جديد
@app.route('/patients/add', methods=['POST'])
def add_patient():
    if request.method == 'POST':
        national_id = request.form.get('NationalID')
        name = request.form.get('FullName')
        birth_date = request.form.get('birthDate')
        gender = request.form.get('gender')
        phone = request.form.get('phone')
        blood_type = request.form.get('blood_type')
        history = request.form.get('medical_history')

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO Patients (NationalID, FullName, BirthDate, gender, phone, blood_type, medical_history)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (national_id, name, birth_date, gender, phone, blood_type, history))
            conn.commit()
            conn.close()
            flash('تم تسجيل المريض بنجاح')
        except Exception as e:
            flash(f'خطأ في التسجيل: {str(e)}')
            
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



# بوابة المريض
@app.route('/patient/portal')
def patient_portal():
    return render_template('patient_portal.html')


# --- 3. تشغيل السيرفر (يجب أن يكون في آخر الملف) ---
if __name__ == '__main__':
    app.run(debug=True, threaded=True) # Threaded يجعل التعامل مع الطلبات أسرع