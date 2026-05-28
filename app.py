import os
from datetime import datetime
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from aws_dynamo import DynamoService
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

db = DynamoService()


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login to continue.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped


def role_required(role):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if session.get("role") != role:
                flash("You are not authorized to access this page.", "danger")
                return redirect(url_for("home"))
            return view_func(*args, **kwargs)

        return wrapped

    return decorator


@app.route("/")
def home():
    if "user_id" in session:
        if session.get("role") == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("customer_dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "customer")

        if role not in {"admin", "customer"}:
            role = "customer"
        if not all([name, email, phone, password]):
            flash("All fields are required.", "danger")
            return redirect(url_for("register"))

        existing = db.get_user_by_email(email)
        if existing:
            flash("Email already registered.", "warning")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)
        db.create_user(name, email, phone, password_hash, role)
        flash("Registration successful. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = db.get_user_by_email(email)
        if not user or not check_password_hash(user["password"], password):
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))

        session["user_id"] = user["user_id"]
        session["name"] = user["name"]
        session["role"] = user["role"]
        flash("Login successful.", "success")

        if user["role"] == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("customer_dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("home"))


@app.route("/customer/dashboard")
@login_required
@role_required("customer")
def customer_dashboard():
    user_id = session["user_id"]
    vehicles = db.get_vehicles_by_user(user_id)
    appointments = db.get_appointments_by_user(user_id)

    next_service_msg = "No service history available yet."
    latest_due_date = None
    for vehicle in vehicles:
        latest = db.get_latest_history_for_vehicle(vehicle["vehicle_id"])
        if latest:
            due = latest.get("next_service_date")
            if due and (latest_due_date is None or due < latest_due_date):
                latest_due_date = due
    if latest_due_date:
        next_service_msg = f"Your next service is due on: {latest_due_date}"

    return render_template(
        "customer_dashboard.html",
        vehicles=vehicles,
        appointments=appointments,
        next_service_msg=next_service_msg,
    )


@app.route("/customer/vehicle/add", methods=["GET", "POST"])
@login_required
@role_required("customer")
def add_vehicle():
    if request.method == "POST":
        vehicle_number = request.form.get("vehicle_number", "").strip().upper()
        model = request.form.get("model", "").strip()
        brand = request.form.get("brand", "").strip()
        year = request.form.get("year", "").strip()

        if not all([vehicle_number, model, brand, year]):
            flash("All fields are required.", "danger")
            return redirect(url_for("add_vehicle"))

        db.create_vehicle(session["user_id"], vehicle_number, model, brand, year)
        flash("Vehicle added successfully.", "success")
        return redirect(url_for("customer_dashboard"))

    return render_template("add_vehicle.html")


@app.route("/customer/book-service", methods=["GET", "POST"])
@login_required
@role_required("customer")
def book_service():
    user_id = session["user_id"]
    vehicles = db.get_vehicles_by_user(user_id)

    if request.method == "POST":
        vehicle_id = request.form.get("vehicle_id", "")
        service_date = request.form.get("service_date", "")
        service_type = request.form.get("service_type", "").strip()

        if not all([vehicle_id, service_date, service_type]):
            flash("All fields are required.", "danger")
            return redirect(url_for("book_service"))

        try:
            datetime.strptime(service_date, "%Y-%m-%d")
        except ValueError:
            flash("Invalid service date format.", "danger")
            return redirect(url_for("book_service"))

        db.create_appointment(user_id, vehicle_id, service_date, service_type)
        flash("Service appointment booked successfully.", "success")
        return redirect(url_for("customer_dashboard"))

    return render_template("book_service.html", vehicles=vehicles)


@app.route("/customer/service-history")
@login_required
@role_required("customer")
def service_history():
    vehicles = db.get_vehicles_by_user(session["user_id"])
    selected_vehicle_id = request.args.get("vehicle_id")

    history = []
    if selected_vehicle_id:
        history = db.get_history_by_vehicle(selected_vehicle_id)

    return render_template(
        "service_history.html",
        vehicles=vehicles,
        history=history,
        selected_vehicle_id=selected_vehicle_id,
    )


@app.route("/customer/invoice/<appointment_id>")
@login_required
@role_required("customer")
def invoice(appointment_id):
    appointment = db.get_appointment(appointment_id)
    if not appointment or appointment.get("user_id") != session["user_id"]:
        flash("Invoice not found.", "danger")
        return redirect(url_for("customer_dashboard"))

    bill = db.get_bill_by_appointment(appointment_id)
    if not bill:
        flash("Bill not generated yet.", "warning")
        return redirect(url_for("customer_dashboard"))

    vehicle = db.get_vehicle(appointment["vehicle_id"])
    return render_template("invoice.html", appointment=appointment, bill=bill, vehicle=vehicle)


@app.route("/admin/dashboard")
@login_required
@role_required("admin")
def admin_dashboard():
    appointments = db.get_all_appointments()
    users = db.get_all_users()
    vehicles = db.get_all_vehicles()
    mechanics = db.get_all_mechanics()
    mechanic_map = {m["mechanic_id"]: m["name"] for m in mechanics}

    return render_template(
        "admin_dashboard.html",
        appointments=appointments,
        users=users,
        vehicles=vehicles,
        mechanics=mechanics,
        mechanic_map=mechanic_map,
    )


@app.route("/admin/appointment/<appointment_id>/update", methods=["POST"])
@login_required
@role_required("admin")
def update_appointment(appointment_id):
    status = request.form.get("status", "Pending")
    mechanic_id = request.form.get("mechanic_id", "")
    cost = request.form.get("cost", "0").strip()

    valid_status = {"Pending", "In Progress", "Completed"}
    if status not in valid_status:
        flash("Invalid status selected.", "danger")
        return redirect(url_for("admin_dashboard"))

    appointment = db.get_appointment(appointment_id)
    if not appointment:
        flash("Appointment not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    db.update_appointment_status(appointment_id, status, mechanic_id)

    if status == "Completed":
        existing_bill = db.get_bill_by_appointment(appointment_id)
        if not existing_bill:
            service_item = db.add_service_history(
                vehicle_id=appointment["vehicle_id"],
                service_date=appointment["service_date"],
                details=appointment["service_type"],
                cost=cost or "0",
            )
            db.create_bill(appointment_id=appointment_id, amount=cost or "0", payment_status="Pending")
            flash(
                f"Service completed. Next service date: {service_item['next_service_date']}. Bill generated.",
                "success",
            )
        else:
            flash("Status updated. Bill already exists for this appointment.", "info")
    else:
        flash("Appointment updated successfully.", "success")

    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    db.seed_default_mechanics()
    port = int(os.getenv("PORT", "5055"))
    app.run(host="0.0.0.0", port=port, debug=True)
