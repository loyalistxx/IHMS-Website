from flask import Flask, render_template
import pyodbc

app = Flask(__name__)

# مسار صفحة تسجيل الدخول
@app.route('/')
def login():
    return render_template('login.html')

# مسار لوحة التحكم
@app.route('/dashboard')
def dashboard():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)