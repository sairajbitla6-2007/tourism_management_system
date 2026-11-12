import os

import mysql.connector
from decimal import Decimal, InvalidOperation
from functools import wraps
from dotenv import load_dotenv
from flask import (
    Flask, abort, flash, redirect, render_template,
    request, session, url_for
)
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY")

if not app.config["SECRET_KEY"]:
    raise RuntimeError("Add FLASK_SECRET_KEY to your .env file.")

csrf = CSRFProtect(app)


def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )


def fetch_all(sql, params=()):
    connection = get_db_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(sql, params)
            return cursor.fetchall()
        finally:
            cursor.close()
    finally:
        connection.close()

def login_required(view_function):
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in before making a booking.")
            return redirect(url_for("login"))
        return view_function(*args, **kwargs)

    return wrapped_view

def admin_required(view_function):
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if session.get("user_role") != "admin":
            flash("Admin access is required.")
            return redirect(url_for("home"))

        return view_function(*args, **kwargs)

    return wrapped_view


@app.get("/")
def home():
    search_text = request.args.get("q", "").strip()
    destination_id = request.args.get("destination_id", type=int)

    sql = """
        SELECT
            p.id,
            p.title,
            d.name AS destination,
            p.duration_days,
            p.price,
            p.available_seats
        FROM tour_packages AS p
        JOIN destinations AS d ON d.id = p.destination_id
        WHERE p.is_active = TRUE
    """
    params = []

    if search_text:
        sql += " AND (p.title LIKE %s OR d.name LIKE %s)"
        search_pattern = f"%{search_text}%"
        params.extend([search_pattern, search_pattern])

    if destination_id:
        sql += " AND d.id = %s"
        params.append(destination_id)

    sql += " ORDER BY p.id"

    packages = fetch_all(sql, tuple(params))
    destinations = fetch_all(
        "SELECT id, name FROM destinations ORDER BY name"
    )

    return render_template(
        "packages.html",
        packages=packages,
        destinations=destinations,
        search_text=search_text,
        selected_destination_id=destination_id,
    )


@app.get("/destinations")
def destinations_page():
    destinations = fetch_all("""
        SELECT
            d.id,
            d.name,
            d.country,
            d.description,
            COUNT(p.id) AS package_count
        FROM destinations AS d
        LEFT JOIN tour_packages AS p
            ON p.destination_id = d.id AND p.is_active = TRUE
        GROUP BY d.id, d.name, d.country, d.description
        ORDER BY d.name
    """)

    return render_template(
        "destinations.html",
        destinations=destinations,
    )


@app.get("/package/<int:package_id>")
def package_detail(package_id):
    packages = fetch_all("""
        SELECT
            p.id,
            p.title,
            p.duration_days,
            p.price,
            p.available_seats,
            d.name AS destination,
            d.country,
            d.description AS destination_description
        FROM tour_packages AS p
        JOIN destinations AS d ON d.id = p.destination_id
        WHERE p.id = %s AND p.is_active = TRUE
    """, (package_id,))

    if not packages:
        abort(404)

    return render_template("package_detail.html", package=packages[0])

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if (
            not full_name
            or "@" not in email
            or len(password) < 8
            or len(password) > 128
        ):
            flash("Enter your name, a valid email, and a password of 8–128 characters.")
            return render_template("register.html")

        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO users (full_name, email, password_hash)
                VALUES (%s, %s, %s)
                """,
                (full_name, email, generate_password_hash(password)),
            )
            connection.commit()

            session.clear()
            session["user_id"] = cursor.lastrowid
            session["user_name"] = full_name
            session["user_role"] = "customer"

            flash("Account created. You are now logged in.")
            return redirect(url_for("home"))

        except mysql.connector.IntegrityError:
            connection.rollback()
            flash("That email is already registered.")

        finally:
            cursor.close()
            connection.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            cursor.execute(
                """
                SELECT id, full_name, password_hash, role
                FROM users
                WHERE email = %s
                """,
                (email,),
            )
            user = cursor.fetchone()
        finally:
            cursor.close()
            connection.close()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["full_name"]
            session["user_role"] = user["role"]
            flash("You are logged in.")
            return redirect(url_for("home"))
        else:
            session.clear()
            flash("Email or password was not recognized.")

    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    flash("You are logged out.")
    return redirect(url_for("home"))

@app.post("/package/<int:package_id>/book")
@login_required
def book_package(package_id):
    seats = request.form.get("seats", type=int)

    if seats is None or seats < 1:
        flash("Enter a number of travelers of at least 1.")
        return redirect(url_for("package_detail", package_id=package_id))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        connection.start_transaction()

        cursor.execute(
            """
            SELECT id, title, price, available_seats
            FROM tour_packages
            WHERE id = %s AND is_active = TRUE
            FOR UPDATE
            """,
            (package_id,),
        )
        package = cursor.fetchone()

        if package is None:
            connection.rollback()
            flash("That package is no longer available.")
            return redirect(url_for("home"))

        if seats > package["available_seats"]:
            connection.rollback()
            flash(
                f"Only {package['available_seats']} seats remain for "
                f"{package['title']}."
            )
            return redirect(
                url_for("package_detail", package_id=package_id)
            )

        total_price = package["price"] * seats

        cursor.execute(
            """
            INSERT INTO bookings
                (user_id, package_id, seats, status, total_price)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                session["user_id"],
                package_id,
                seats,
                "confirmed",
                total_price,
            ),
        )

        cursor.execute(
            """
            UPDATE tour_packages
            SET available_seats = available_seats - %s
            WHERE id = %s
            """,
            (seats, package_id),
        )

        connection.commit()
        flash("Booking confirmed.")
        return redirect(url_for("my_bookings"))

    except mysql.connector.Error:
        connection.rollback()
        app.logger.exception("Booking could not be saved.")
        flash("The booking could not be saved. Please try again.")
        return redirect(url_for("package_detail", package_id=package_id))

    finally:
        cursor.close()
        connection.close()


@app.get("/my-bookings")
@login_required
def my_bookings():
    bookings = fetch_all(
        """
        SELECT
            b.id,
            b.seats,
            b.total_price,
            b.status,
            b.created_at,
            p.title,
            d.name AS destination
        FROM bookings AS b
        JOIN tour_packages AS p ON p.id = b.package_id
        JOIN destinations AS d ON d.id = p.destination_id
        WHERE b.user_id = %s
        ORDER BY b.created_at DESC
        """,
        (session["user_id"],),
    )

    return render_template("bookings.html", bookings=bookings)

@app.get("/admin")
@login_required
@admin_required
def admin_dashboard():
    stats = fetch_all("""
        SELECT
            (SELECT COUNT(*) FROM destinations) AS destination_count,
            (
                SELECT COUNT(*)
                FROM tour_packages
                WHERE is_active = TRUE
            ) AS active_package_count,
            (SELECT COUNT(*) FROM bookings) AS booking_count
    """)[0]

    destinations = fetch_all("""
        SELECT id, name, country, description
        FROM destinations
        ORDER BY name
    """)

    packages = fetch_all("""
        SELECT
            p.id,
            p.title,
            p.duration_days,
            p.price,
            p.available_seats,
            p.is_active,
            d.name AS destination
        FROM tour_packages AS p
        JOIN destinations AS d ON d.id = p.destination_id
        ORDER BY p.id DESC
    """)

    return render_template(
        "admin_dashboard.html",
        stats=stats,
        destinations=destinations,
        packages=packages,
    )

@app.post("/admin/destinations")
@login_required
@admin_required
def add_destination():
    name = request.form.get("name", "").strip()
    country = request.form.get("country", "").strip()
    description = request.form.get("description", "").strip()

    if not name or len(name) > 100 or not country or len(country) > 80:
        flash("Enter a destination name and country within the allowed lengths.")
        return redirect(url_for("admin_dashboard"))

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO destinations (name, country, description)
            VALUES (%s, %s, %s)
            """,
            (name, country, description or None),
        )
        connection.commit()
        flash("Destination added.")
    except mysql.connector.Error:
        connection.rollback()
        app.logger.exception("Could not add destination.")
        flash("The destination could not be added.")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("admin_dashboard"))


@app.post("/admin/packages")
@login_required
@admin_required
def add_package():
    destination_id = request.form.get("destination_id", type=int)
    title = request.form.get("title", "").strip()
    duration_days = request.form.get("duration_days", type=int)
    available_seats = request.form.get("available_seats", type=int)
    price_text = request.form.get("price", "").strip()

    if (
        not destination_id
        or not title
        or len(title) > 150
        or duration_days is None
        or duration_days < 1
        or available_seats is None
        or available_seats < 1
    ):
        flash("Enter a destination, title, duration, and positive seat count.")
        return redirect(url_for("admin_dashboard"))

    try:
        price = Decimal(price_text)
        if price <= 0:
            raise InvalidOperation
    except InvalidOperation:
        flash("Enter a valid price greater than zero.")
        return redirect(url_for("admin_dashboard"))

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO tour_packages
                (destination_id, title, duration_days, price, available_seats)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (destination_id, title, duration_days, price, available_seats),
        )
        connection.commit()
        flash("Tour package added.")
    except mysql.connector.Error:
        connection.rollback()
        app.logger.exception("Could not add tour package.")
        flash("The package could not be added. Check that the destination exists.")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("admin_dashboard"))


@app.post("/admin/packages/<int:package_id>/deactivate")
@login_required
@admin_required
def deactivate_package(package_id):
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE tour_packages
            SET is_active = FALSE
            WHERE id = %s
            """,
            (package_id,),
        )
        connection.commit()

        if cursor.rowcount:
            flash("Package deactivated.")
        else:
            flash("Package not found.")
    except mysql.connector.Error:
        connection.rollback()
        app.logger.exception("Could not deactivate package.")
        flash("The package could not be deactivated.")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("admin_dashboard"))

@app.get("/admin/reports")
@login_required
@admin_required
def admin_report():
    summary = fetch_all("""
        SELECT
            COUNT(*) AS total_bookings,
            COALESCE(SUM(
                CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END
            ), 0) AS confirmed_bookings,
            COALESCE(SUM(
                CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END
            ), 0) AS cancelled_bookings,
            COALESCE(SUM(
                CASE WHEN status = 'confirmed' THEN total_price ELSE 0 END
            ), 0) AS confirmed_booking_value
        FROM bookings
    """)[0]

    package_report = fetch_all("""
        SELECT
            p.title,
            d.name AS destination,
            COUNT(b.id) AS booking_count,
            COALESCE(SUM(
                CASE WHEN b.status = 'confirmed' THEN b.seats ELSE 0 END
            ), 0) AS confirmed_seats,
            COALESCE(SUM(
                CASE WHEN b.status = 'confirmed' THEN b.total_price ELSE 0 END
            ), 0) AS booking_value
        FROM tour_packages AS p
        JOIN destinations AS d ON d.id = p.destination_id
        LEFT JOIN bookings AS b ON b.package_id = p.id
        GROUP BY p.id, p.title, d.name
        ORDER BY booking_count DESC, p.title
    """)

    return render_template(
        "admin_report.html",
        summary=summary,
        package_report=package_report,
    )

if __name__ == "__main__":
    app.run(debug=True)