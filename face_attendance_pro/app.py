import os,sqlite3,hashlib,secrets,base64,io,csv,shutil
from datetime import datetime,date,timedelta
from functools import wraps
import cv2,numpy as np
from flask import Flask,render_template,request,redirect,url_for,session,jsonify,send_file,flash
BASE=os.path.dirname(__file__); DB=BASE+"/attendance.db"; DATA=BASE+"/dataset"; MODEL=BASE+"/trainer.yml"
app=Flask(__name__); app.secret_key=secrets.token_hex(32)
CASCADE=cv2.CascadeClassifier(cv2.data.haarcascades+"haarcascade_frontalface_default.xml")
def db(): c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def hp(p,s): return hashlib.pbkdf2_hmac("sha256",p.encode(),s.encode(),120000).hex()
def init():
 c=db(); c.execute("CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY,username TEXT UNIQUE,password TEXT,salt TEXT)")
 c.execute("CREATE TABLE IF NOT EXISTS students(id INTEGER PRIMARY KEY AUTOINCREMENT,roll_no TEXT UNIQUE,name TEXT,email TEXT,phone TEXT,course TEXT,created_at TEXT)")
 c.execute("CREATE TABLE IF NOT EXISTS attendance(id INTEGER PRIMARY KEY AUTOINCREMENT,student_id INTEGER,date TEXT,time TEXT,UNIQUE(student_id,date))")
 if not c.execute("SELECT 1 FROM admins").fetchone():
  s=secrets.token_hex(12); c.execute("INSERT INTO admins(username,password,salt) VALUES(?,?,?)",("admin",hp("admin123",s),s))
 c.commit();c.close();os.makedirs(DATA,exist_ok=True)
def auth(f):
 @wraps(f)
 def w(*a,**k):
  if not session.get("admin"): return redirect("/login")
  return f(*a,**k)
 return w
def dec(x): return cv2.imdecode(np.frombuffer(base64.b64decode(x.split(",")[-1]),np.uint8),cv2.IMREAD_COLOR)
def train():
 if not hasattr(cv2,"face"): raise RuntimeError("opencv-contrib-python is required")
 fs=[];ls=[];c=db()
 for s in c.execute("SELECT id FROM students"):
  d=f"{DATA}/{s['id']}"
  if os.path.isdir(d):
   for f in os.listdir(d):
    im=cv2.imread(d+"/"+f,0)
    if im is not None:fs.append(im);ls.append(s["id"])
 c.close()
 if not fs: raise RuntimeError("No registered faces")
 r=cv2.face.LBPHFaceRecognizer_create();r.train(fs,np.array(ls));r.write(MODEL)
def recog(im):
 if not os.path.exists(MODEL): return None,"Model not trained"
 g=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY); faces=CASCADE.detectMultiScale(g,1.15,5,minSize=(80,80))
 if not len(faces):return None,"No face detected"
 r=cv2.face.LBPHFaceRecognizer_create();r.read(MODEL);best=min((r.predict(g[y:y+h,x:x+w]) for x,y,w,h in faces),key=lambda z:z[1])
 if best[1]>62:return None,"Face not recognized"
 c=db();s=c.execute("SELECT * FROM students WHERE id=?",(best[0],)).fetchone();c.close()
 return (dict(s) if s else None),"Recognized"
@app.route("/login",methods=["GET","POST"])
def login():
 if request.method=="POST":
  c=db();a=c.execute("SELECT * FROM admins WHERE username=?",(request.form["username"],)).fetchone();c.close()
  if a and hp(request.form["password"],a["salt"])==a["password"]:session["admin"]=a["username"];return redirect("/")
  flash("Invalid login")
 return render_template("login.html")
@app.route("/logout")
def logout():session.clear();return redirect("/login")
@app.route("/")
@auth
def home():
 c=db();total=c.execute("SELECT COUNT(*) n FROM students").fetchone()["n"];present=c.execute("SELECT COUNT(*) n FROM attendance WHERE date=?",(str(date.today()),)).fetchone()["n"];records=c.execute("SELECT COUNT(*) n FROM attendance").fetchone()["n"];recent=c.execute("SELECT s.name,s.roll_no,a.date,a.time FROM attendance a JOIN students s ON s.id=a.student_id ORDER BY a.id DESC LIMIT 8").fetchall();c.close()
 return render_template("dashboard.html",total=total,present=present,records=records,recent=recent)
@app.route("/students")
@auth
def students():
 c=db();x=c.execute("SELECT * FROM students ORDER BY id DESC").fetchall();c.close();return render_template("students.html",students=x)
@app.route("/register")
@auth
def register():return render_template("register.html")
@app.route("/api/register",methods=["POST"])
@auth
def reg():
 d=request.get_json(); imgs=d.get("images",[])
 if not d.get("name") or not d.get("roll_no") or len(imgs)<10:return jsonify(ok=False,message="Name, roll and 10+ samples are required")
 c=db()
 try:
  cur=c.execute("INSERT INTO students(roll_no,name,email,phone,course,created_at) VALUES(?,?,?,?,?,?)",(d["roll_no"],d["name"],d.get("email",""),d.get("phone",""),d.get("course","BCA"),datetime.now().isoformat()));sid=cur.lastrowid;c.commit()
 except sqlite3.IntegrityError:c.close();return jsonify(ok=False,message="Roll number already exists")
 c.close();folder=f"{DATA}/{sid}";os.makedirs(folder);saved=0
 for z in imgs:
  im=dec(z);g=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY);faces=CASCADE.detectMultiScale(g,1.15,5,minSize=(80,80))
  if len(faces):
   x,y,w,h=max(faces,key=lambda q:q[2]*q[3]);cv2.imwrite(f"{folder}/{saved}.jpg",g[y:y+h,x:x+w]);saved+=1
 if saved<5:return jsonify(ok=False,message="Not enough face samples; use better lighting")
 train();return jsonify(ok=True,message=f"{d['name']} registered successfully")
@app.route("/student/delete/<int:sid>",methods=["POST"])
@auth
def delete(sid):
 c=db();c.execute("DELETE FROM attendance WHERE student_id=?",(sid,));c.execute("DELETE FROM students WHERE id=?",(sid,));c.commit();c.close();shutil.rmtree(f"{DATA}/{sid}",ignore_errors=True)
 try:train()
 except:pass
 return redirect("/students")
@app.route("/attendance")
@auth
def attendance():return render_template("attendance.html")
@app.route("/api/recognize",methods=["POST"])
@auth
def recognize():
 s,msg=recog(dec(request.get_json()["image"]))
 if not s:return jsonify(ok=False,message=msg)
 n=datetime.now();d=str(n.date());t=n.strftime("%H:%M:%S");c=db()
 try:c.execute("INSERT INTO attendance(student_id,date,time) VALUES(?,?,?)",(s["id"],d,t));c.commit();marked=True
 except sqlite3.IntegrityError:marked=False
 c.close();return jsonify(ok=True,student=s,marked=marked,message="Attendance marked" if marked else "Already marked today")
@app.route("/reports")
@auth
def reports():
 d=request.args.get("date",str(date.today()));c=db();ss=c.execute("SELECT * FROM students ORDER BY roll_no").fetchall();aa={r["student_id"]:r for r in c.execute("SELECT * FROM attendance WHERE date=?",(d,))};c.close()
 rows=[(s["name"],s["roll_no"],"Present" if s["id"] in aa else "Absent",aa[s["id"]]["time"] if s["id"] in aa else "-") for s in ss]
 return render_template("reports.html",rows=rows,selected=d)
@app.route("/api/export")
@auth
def export():
 d=request.args.get("date",str(date.today()));c=db();rows=c.execute("SELECT s.name,s.roll_no,s.email,s.course,a.date,a.time FROM attendance a JOIN students s ON s.id=a.student_id WHERE a.date=?",(d,)).fetchall();c.close()
 out=io.StringIO();w=csv.writer(out);w.writerow(["Name","Roll No","Email","Course","Date","Time"]);w.writerows([tuple(r) for r in rows])
 return send_file(io.BytesIO(out.getvalue().encode()),mimetype="text/csv",as_attachment=True,download_name=f"attendance_{d}.csv")
@app.route("/api/stats")
@auth
def stats():
 c=db();out=[]
 for i in range(6,-1,-1):
  d=date.today()-timedelta(days=i);out.append({"date":str(d),"count":c.execute("SELECT COUNT(*) n FROM attendance WHERE date=?",(str(d),)).fetchone()["n"]})
 c.close();return jsonify(out)
if __name__=="__main__":init();app.run(host="0.0.0.0",port=5000)
