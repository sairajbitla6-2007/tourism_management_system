import hashlib
from datetime import date, timedelta
import os
import secrets
import smtplib
import ssl
from email.message import EmailMessage

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



def send_password_reset_email(recipient, reset_url):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    sender = os.getenv("SMTP_FROM_EMAIL")
    use_ssl = os.getenv("SMTP_USE_SSL", "false").strip().lower() in {"1", "true", "yes"}

    if not smtp_host or not sender:
        raise RuntimeError("Password reset email settings are missing.")
    if bool(smtp_username) != bool(smtp_password):
        raise RuntimeError("SMTP username and password must be configured together.")

    message = EmailMessage()
    message["Subject"] = "Reset your Tourism Management password"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        "We received a request to reset the password for your account.\n\n"
        f"Use this link within 60 minutes to choose a new password:\n{reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )

    if use_ssl:
        server = smtplib.SMTP_SSL(
            smtp_host, smtp_port, timeout=10,
            context=ssl.create_default_context(),
        )
    else:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)

    with server:
        if not use_ssl:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
        if smtp_username:
            server.login(smtp_username, smtp_password)
        server.send_message(message)
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

    return render_template(
        "package_detail.html",
        package=packages[0],
        minimum_trip_date=date.today().isoformat(),
    )

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


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        should_send_email = False
        reset_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(reset_token.encode("utf-8")).hexdigest()
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            connection.start_transaction()
            cursor.execute(
                "SELECT id, email FROM users WHERE email = %s FOR UPDATE",
                (email,),
            )
            user = cursor.fetchone()

            if user:
                cursor.execute(
                    """
                    SELECT requested_at > UTC_TIMESTAMP() - INTERVAL 1 MINUTE
                        AS is_rate_limited
                    FROM password_reset_tokens
                    WHERE user_id = %s
                    FOR UPDATE
                    """,
                    (user["id"],),
                )
                recent_request = cursor.fetchone()
                is_rate_limited = (
                    recent_request is not None
                    and recent_request["is_rate_limited"]
                )

                if not is_rate_limited:
                    cursor.execute(
                        "DELETE FROM password_reset_tokens WHERE user_id = %s",
                        (user["id"],),
                    )
                    cursor.execute(
                        """
                        INSERT INTO password_reset_tokens
                            (user_id, token_hash, requested_at, expires_at)
                        VALUES (
                            %s, %s, UTC_TIMESTAMP(),
                            DATE_ADD(UTC_TIMESTAMP(), INTERVAL 60 MINUTE)
                        )
                        """,
                        (user["id"], token_hash),
                    )
                    should_send_email = True

            connection.commit()

        except mysql.connector.Error:
            connection.rollback()
            should_send_email = False
            app.logger.exception("Password reset request could not be saved.")

        finally:
            cursor.close()
            connection.close()

        if should_send_email:
            try:
                base_url = os.getenv("APP_BASE_URL", "").strip().rstrip("/")
                if not base_url:
                    raise RuntimeError("APP_BASE_URL is not configured.")
                reset_url = (
                    f"{base_url}{url_for('reset_password', token=reset_token)}"
                )
                send_password_reset_email(user["email"], reset_url)
            except Exception:
                app.logger.exception("Password reset email could not be sent.")

        flash(
            "If an account exists for that email, reset instructions will be sent."
        )
        return redirect(url_for("login"))

    return render_template("forgot_password.html")


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    if request.method == "POST":
        password = request.form.get("password", "")
        password_confirmation = request.form.get("password_confirmation", "")

        if len(password) < 8 or len(password) > 128:
            flash("Choose a password between 8 and 128 characters.")
            return render_template("reset_password.html", token=token)
        if password != password_confirmation:
            flash("The passwords do not match.")
            return render_template("reset_password.html", token=token)

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            connection.start_transaction()
            cursor.execute(
                """
                SELECT user_id
                FROM password_reset_tokens
                WHERE token_hash = %s AND expires_at > UTC_TIMESTAMP()
                FOR UPDATE
                """,
                (token_hash,),
            )
            reset_request = cursor.fetchone()

            if reset_request is None:
                connection.rollback()
                flash("This reset link is invalid or expired. Request a new one.")
                return redirect(url_for("forgot_password"))

            cursor.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (
                    generate_password_hash(password),
                    reset_request["user_id"],
                ),
            )
            cursor.execute(
                "DELETE FROM password_reset_tokens WHERE user_id = %s",
                (reset_request["user_id"],),
            )
            connection.commit()
            flash("Password updated. Please log in with your new password.")
            return redirect(url_for("login"))

        except mysql.connector.Error:
            connection.rollback()
            app.logger.exception("Password reset could not be completed.")
            flash("The password could not be reset. Please try again.")
            return redirect(url_for("forgot_password"))

        finally:
            cursor.close()
            connection.close()

    valid_tokens = fetch_all(
        """
        SELECT user_id
        FROM password_reset_tokens
        WHERE token_hash = %s AND expires_at > UTC_TIMESTAMP()
        """,
        (token_hash,),
    )
    if not valid_tokens:
        flash("This reset link is invalid or expired. Request a new one.")
        return redirect(url_for("forgot_password"))

    return render_template("reset_password.html", token=token)

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
    trip_date_text = request.form.get("trip_date", "").strip()

    try:
        trip_date = date.fromisoformat(trip_date_text)
        if len(trip_date_text) != 10 or trip_date.isoformat() != trip_date_text:
            raise ValueError
        if trip_date < date.today():
            raise ValueError
    except ValueError:
        flash("Choose a valid trip start date today or later.")
        return redirect(url_for("package_detail", package_id=package_id))

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
                (user_id, package_id, seats, trip_date, status, total_price)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                session["user_id"],
                package_id,
                seats,
                trip_date,
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
            b.trip_date,
            b.total_price,
            b.status,
            b.created_at,
            p.title,
            d.name AS destination,
            latest_action.action_type AS latest_admin_action,
            latest_action.reason AS latest_admin_reason,
            latest_action.created_at AS latest_admin_action_at
        FROM bookings AS b
        JOIN tour_packages AS p ON p.id = b.package_id
        JOIN destinations AS d ON d.id = p.destination_id
        LEFT JOIN booking_admin_actions AS latest_action
            ON latest_action.id = (
                SELECT MAX(action_log.id)
                FROM booking_admin_actions AS action_log
                WHERE action_log.booking_id = b.id
            )
        WHERE b.user_id = %s
        ORDER BY b.created_at DESC
        """,
        (session["user_id"],),
    )

    return render_template("bookings.html", bookings=bookings)

@app.post("/bookings/<int:booking_id>/cancel")
@login_required
def cancel_booking(booking_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        connection.start_transaction()

        cursor.execute(
            """
            SELECT id, package_id, seats, status
            FROM bookings
            WHERE id = %s AND user_id = %s
            FOR UPDATE
            """,
            (booking_id, session["user_id"]),
        )
        booking = cursor.fetchone()

        if booking is None:
            connection.rollback()
            abort(404)

        if booking["status"] != "confirmed":
            connection.rollback()
            flash("Only confirmed bookings can be cancelled.")
            return redirect(url_for("my_bookings"))

        cursor.execute(
            """
            UPDATE bookings
            SET status = 'cancelled'
            WHERE id = %s AND status = 'confirmed'
            """,
            (booking_id,),
        )

        if cursor.rowcount != 1:
            connection.rollback()
            flash("This booking can no longer be cancelled.")
            return redirect(url_for("my_bookings"))

        cursor.execute(
            """
            UPDATE tour_packages
            SET available_seats = available_seats + %s
            WHERE id = %s
            """,
            (booking["seats"], booking["package_id"]),
        )

        connection.commit()
        flash("Booking cancelled and seats returned to the package.")
        return redirect(url_for("my_bookings"))

    except mysql.connector.Error:
        connection.rollback()
        app.logger.exception("Booking cancellation could not be saved.")
        flash("The booking could not be cancelled. Please try again.")
        return redirect(url_for("my_bookings"))

    finally:
        cursor.close()
        connection.close()

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


@app.get("/admin/bookings")
@login_required
@admin_required
def admin_bookings():
    bookings = fetch_all("""
        SELECT
            b.id,
            u.full_name AS customer_name,
            p.title AS package_title,
            d.name AS destination,
            b.seats,
            b.trip_date,
            b.total_price,
            b.status,
            b.created_at
        FROM bookings AS b
        JOIN users AS u ON u.id = b.user_id
        JOIN tour_packages AS p ON p.id = b.package_id
        JOIN destinations AS d ON d.id = p.destination_id
        ORDER BY (b.status = 'confirmed') DESC,
                 b.trip_date IS NULL,
                 b.trip_date,
                 b.created_at DESC,
                 b.id DESC
    """)
    history = fetch_all("""
        SELECT
            a.booking_id,
            a.action_type,
            a.previous_trip_date,
            a.new_trip_date,
            a.reason,
            a.created_at,
            u.full_name AS admin_name
        FROM booking_admin_actions AS a
        JOIN users AS u ON u.id = a.admin_user_id
        ORDER BY a.booking_id, a.created_at DESC, a.id DESC
    """)

    actions_by_booking = {}
    for action in history:
        actions_by_booking.setdefault(action["booking_id"], []).append(action)
    today = date.today()
    for booking in bookings:
        booking["admin_actions"] = actions_by_booking.get(booking["id"], [])
        earliest_date = today
        if booking["trip_date"] is not None:
            earliest_date = max(today, booking["trip_date"] + timedelta(days=1))
        booking["minimum_postpone_date"] = earliest_date.isoformat()

    return render_template("admin_bookings.html", bookings=bookings)


@app.post("/admin/bookings/<int:booking_id>/postpone")
@login_required
@admin_required
def admin_postpone_booking(booking_id):
    new_trip_date_text = request.form.get("trip_date", "").strip()
    reason = request.form.get("reason", "").strip()
    try:
        new_trip_date = date.fromisoformat(new_trip_date_text)
        if len(new_trip_date_text) != 10 or new_trip_date.isoformat() != new_trip_date_text:
            raise ValueError
        if new_trip_date < date.today():
            raise ValueError
    except ValueError:
        flash("Choose a valid new trip date today or later.")
        return redirect(url_for("admin_bookings"))
    if not reason or len(reason) > 500:
        flash("Enter a reason of up to 500 characters for the postponement.")
        return redirect(url_for("admin_bookings"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        connection.start_transaction()
        cursor.execute(
            "SELECT id, trip_date, status FROM bookings WHERE id = %s FOR UPDATE",
            (booking_id,),
        )
        booking = cursor.fetchone()
        if booking is None:
            connection.rollback()
            abort(404)
        if booking["status"] != "confirmed":
            connection.rollback()
            flash("Only confirmed bookings can be postponed.")
            return redirect(url_for("admin_bookings"))
        if booking["trip_date"] is not None and new_trip_date <= booking["trip_date"]:
            connection.rollback()
            flash("A postponement must be later than the current trip date.")
            return redirect(url_for("admin_bookings"))

        cursor.execute(
            "UPDATE bookings SET trip_date = %s WHERE id = %s AND status = 'confirmed'",
            (new_trip_date, booking_id),
        )
        if cursor.rowcount != 1:
            connection.rollback()
            flash("This booking could not be postponed. Refresh and try again.")
            return redirect(url_for("admin_bookings"))
        cursor.execute(
            """
            INSERT INTO booking_admin_actions
                (booking_id, admin_user_id, action_type, previous_trip_date,
                 new_trip_date, reason)
            VALUES (%s, %s, 'postponed', %s, %s, %s)
            """,
            (
                booking_id,
                session["user_id"],
                booking["trip_date"],
                new_trip_date,
                reason,
            ),
        )
        connection.commit()
        flash("Trip date postponed and the reason recorded.")
    except mysql.connector.Error:
        connection.rollback()
        app.logger.exception("Admin could not postpone booking %s.", booking_id)
        flash("The trip date could not be postponed. Please try again.")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for("admin_bookings"))


@app.post("/admin/bookings/<int:booking_id>/cancel")
@login_required
@admin_required
def admin_cancel_booking(booking_id):
    reason = request.form.get("reason", "").strip()
    if not reason or len(reason) > 500:
        flash("Enter a reason of up to 500 characters for the cancellation.")
        return redirect(url_for("admin_bookings"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        connection.start_transaction()
        cursor.execute(
            """
            SELECT id, package_id, seats, trip_date, status
            FROM bookings
            WHERE id = %s
            FOR UPDATE
            """,
            (booking_id,),
        )
        booking = cursor.fetchone()
        if booking is None:
            connection.rollback()
            abort(404)
        if booking["status"] != "confirmed":
            connection.rollback()
            flash("Only confirmed bookings can be cancelled by an administrator.")
            return redirect(url_for("admin_bookings"))

        cursor.execute(
            "UPDATE bookings SET status = 'cancelled' WHERE id = %s AND status = 'confirmed'",
            (booking_id,),
        )
        if cursor.rowcount != 1:
            connection.rollback()
            flash("This booking could not be cancelled. Refresh and try again.")
            return redirect(url_for("admin_bookings"))
        cursor.execute(
            "UPDATE tour_packages SET available_seats = available_seats + %s WHERE id = %s",
            (booking["seats"], booking["package_id"]),
        )
        cursor.execute(
            """
            INSERT INTO booking_admin_actions
                (booking_id, admin_user_id, action_type, previous_trip_date,
                 new_trip_date, reason)
            VALUES (%s, %s, 'cancelled', %s, NULL, %s)
            """,
            (booking_id, session["user_id"], booking["trip_date"], reason),
        )
        connection.commit()
        flash("Booking cancelled, seats returned, and the reason recorded.")
    except mysql.connector.Error:
        connection.rollback()
        app.logger.exception("Admin could not cancel booking %s.", booking_id)
        flash("The booking could not be cancelled. Please try again.")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for("admin_bookings"))

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


@app.get("/admin/reports/bookings/<category>")
@login_required
@admin_required
def admin_report_bookings(category):
    report_options = {
        "all": ("All bookings", None),
        "confirmed": ("Confirmed bookings", "confirmed"),
        "cancelled": ("Cancelled bookings", "cancelled"),
        "value": ("Confirmed bookings contributing to value", "confirmed"),
    }
    if category not in report_options:
        abort(404)

    title, status = report_options[category]
    sql = """
        SELECT
            b.id,
            u.full_name AS customer_name,
            p.title AS package_title,
            d.name AS destination,
            b.seats,
            b.total_price,
            b.status,
            b.trip_date,
            b.created_at
        FROM bookings AS b
        JOIN users AS u ON u.id = b.user_id
        JOIN tour_packages AS p ON p.id = b.package_id
        JOIN destinations AS d ON d.id = p.destination_id
    """
    params = ()
    if status:
        sql += " WHERE b.status = %s"
        params = (status,)
    sql += " ORDER BY b.created_at DESC, b.id DESC"
    bookings = fetch_all(sql, params)

    return render_template(
        "admin_report_detail.html",
        title=title,
        category=category,
        bookings=bookings,
    )

if __name__ == "__main__":
    app.run(debug=True)
