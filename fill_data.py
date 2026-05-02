import pyodbc
from faker import Faker
import random
from datetime import datetime

# إعداد Faker
fake = Faker('ar_EG') 

def seed_inventory_table(num_records=50): # رفعت العدد لـ 50 لتجربة أفضل
    conn_str = (
        "Driver={ODBC Driver 17 for SQL Server};" # هذا التعريف أكثر استقراراً مع بايثون
        "Server=ADHAM\\MSSQLSERVER01;"
        "Database=IHMS;"
        "Trusted_Connection=yes;"
    )
    
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # قائمة موسعة للأصناف الطبية (أدوية ومستلزمات)
        medical_items = [
            # أدوية (Tablets & Capsules)
            'Panadol Extra', 'Augmentin 1g', 'Concor 5mg', 'Brufen 600mg', 
            'Glucophage 1000mg', 'Ameloprex 5mg', 'Exforge 10/160mg', 'Diamicron MR 60mg',
            # محاليل وحقن (Vials & Ampoules)
            'Ceftriaxone 1g Vial', 'Dexamethasone Amp', 'Normal Saline 500ml', 'Glucose 5% 500ml',
            'Ringer Lactate 500ml', 'Insulin Mixtard 30/70', 'Voltaren Ampoules',
            # مستلزمات جراحية وطوارئ (Consumables)
            'Medical Syringe 3ml', 'Medical Syringe 5ml', 'IV Cannula G20 (Pink)', 
            'IV Cannula G22 (Blue)', 'Adhesive Plaster', 'Sterile Gauze 10x10', 
            'Elastic Bandage', 'Surgical Sutures 3-0', 'Surgical Gloves (Size 7.5)',
            # شراب ودهانات (Syrups & Topicals)
            'Zyrtec Syrup', 'Tusskan Syrup', 'Fucidin Cream', 'Betadine Antiseptic'
        ]

        # قائمة موسعة لوحدات القياس
        units = [
            'Box (علبة)', 'Bottle (زجاجة)', 'Strip (شريط)', 'Piece (قطعة)', 
            'Sachet (كيس)', 'Vial (فيال)', 'Ampoule (أمبول)', 'Roll (رول)', 
            'Pair (زوج)', 'Packet (باكيت)'
        ]

        for _ in range(num_records):
            item_code = f"ITM-{fake.unique.bothify(text='####')}"
            item_name = random.choice(medical_items)
            quantity = random.randint(5, 1000) # نطاق أوسع للكميات
            unit = random.choice(units)
            
            # تاريخ الصلاحية: بعضها قريب (للاختبار) وبعضها بعيد
            expiry_date = fake.date_between(start_date='+10d', end_date='+3y')
            created_at = datetime.now()

            query = """
                INSERT INTO Inventory (item_code, item_name, quantity, unit, expiry_date, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            cursor.execute(query, (item_code, item_name, quantity, unit, expiry_date, created_at))
        
        conn.commit()
        print(f"✅ Successfully generated {num_records} diverse medical records!")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

# تنفيذ التوليد
seed_inventory_table(40)