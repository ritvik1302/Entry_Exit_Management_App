from flask import Flask, render_template, request, redirect, url_for, session
from pymongo import MongoClient
import hashlib
from datetime import datetime
import base64
from flask import jsonify
from bson import ObjectId

app = Flask(__name__)
app.secret_key = "your_secret_key"
client = MongoClient("mongodb://localhost:27017/")
db = client["user_database"]

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username and password:
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            existing_user = db.users.find_one({"username": username})

            if existing_user:
                if existing_user["password"] == hashed_password:
                    session["username"] = username
                    return redirect(url_for("dashboard"))
                else:
                    return render_template("login.html", message="Wrong password. Please try again.")

            new_user = {"username": username, "password": hashed_password}
            db.users.insert_one(new_user)
            session["username"] = username
            return redirect(url_for("dashboard"))

    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "username" in session:
        return render_template("dashboard.html", username=session["username"])
    return redirect(url_for("login"))


@app.route("/new-entry")
def new_entry():
    return render_template("new_entry.html")

import qrcode
from PIL import Image
from io import BytesIO

@app.route("/submit-new-entry", methods=["POST"])
def submit_new_entry():
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]
    mobile_no = request.form.get("mobile_no")

    existing_entry = db.entries.find_one({"username": username, "mobile_no": mobile_no})

    if existing_entry:
        db.entries.update_one(
            {"_id": ObjectId(existing_entry["_id"])},
            {
                "$set": {
                    "name": request.form.get("name"),
                    "vehicle_no": request.form.get("vehicle_no"),
                    "where_to_go": request.form.get("where_to_go"),
                    "purpose": request.form.get("purpose"),
                    "no_of_persons": int(request.form.get("no_of_persons")),
                    "vehicle_type": request.form.get("vehicle_type"),
                    "remark": request.form.get("remark"),
                    "in_time": datetime.now(),
                    "inside": True,
                    "out_time": None,
                }
            }
        )
        entry_id = existing_entry["_id"]
        qr = generate_qr_code(entry_id)
        qr_base64 = base64.b64encode(qr.getvalue()).decode('utf-8')

        return render_template("qr_page.html", qr_base64=qr_base64)
    else:
        entry_data = {
            "name": request.form.get("name"),
            "vehicle_no": request.form.get("vehicle_no"),
            "mobile_no": mobile_no,
            "where_to_go": request.form.get("where_to_go"),
            "purpose": request.form.get("purpose"),
            "no_of_persons": int(request.form.get("no_of_persons")),
            "vehicle_type": request.form.get("vehicle_type"),
            "remark": request.form.get("remark"),
            "username": username,
            "in_time": datetime.now(),
            "inside": True,
            "out_time": None,
        }

        result = db.entries.insert_one(entry_data)

        entry_id = result.inserted_id
        qr = generate_qr_code(entry_id)
        qr_base64 = base64.b64encode(qr.getvalue()).decode('utf-8')

        return render_template("qr_page.html", qr=qr_base64)

def generate_qr_code(entry_id):
    entry_id_str = str(entry_id)
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(entry_id_str)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img_byte_array = BytesIO()
    img.save(img_byte_array)
    img_byte_array.seek(0)

    return img_byte_array

@app.route("/all-entries")
def all_entries():
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]

    all_entries_data = list(db.entries.find({"username": username}))

    for entry in all_entries_data:
        entry["in_time"] = entry["in_time"].strftime("%Y-%m-%d %H:%M:%S")
        if entry["out_time"]:
            entry["out_time"] = entry["out_time"].strftime("%Y-%m-%d %H:%M:%S")

    return render_template("all_entries.html", entries=all_entries_data)

@app.route("/current-visitors")
def current_visitors():
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]

    current_visitors_data = list(db.entries.find({"username": username, "inside": True}))

    for visitor in current_visitors_data:
        visitor["in_time"] = visitor["in_time"].strftime("%Y-%m-%d %H:%M:%S")

    return render_template("current_visitors.html", visitors=current_visitors_data)


@app.route("/exit-visitor")
def exit_visitor():
    return render_template("exit_visitor.html")

@app.route("/submit-exit-visitor", methods=["POST"])
def submit_exit_visitor():
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]
    mobile_no = request.form.get("mobile_no")

    entry = db.entries.find_one({"username": username, "mobile_no": mobile_no, "inside": True})

    if entry:
        db.entries.update_one(
            {"_id": ObjectId(entry["_id"])},
            {
                "$set": {
                    "inside": False,
                    "out_time": datetime.now()
                }
            }
        )
        return "Visitor exited successfully!"

    return "Visitor not found or already exited."

@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
