# FaceAttend PRO

Default admin: **admin** / **admin123**

Windows:
1. Install Python 3.10-3.12.
2. Open CMD in this folder.
3. `python -m venv venv`
4. `venv\\Scripts\\activate`
5. `pip install -r requirements.txt`
6. `python app.py`
7. Open http://127.0.0.1:5000

Features: admin login, dashboard, student management, face registration, live recognition, duplicate prevention, date-wise present/absent report, Excel-compatible CSV export, responsive mobile UI, animated scan interface.

Liveness: the prototype provides a turn-head prompt and animated scan UI; this is not a production-grade anti-spoofing model. Production deployment should add a trained liveness model, HTTPS, consent, secure authentication and data-retention controls.
