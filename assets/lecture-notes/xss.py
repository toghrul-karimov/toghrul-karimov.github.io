from flask import Flask, request, redirect, url_for, render_template_string, jsonify
import sqlite3
import argparse

app = Flask(__name__)

DB_NAME = "inputs.db"

# In-memory website switch. It resets to True when the server process restarts.
website_enabled = True

# Turn this off if you do not want full HTTP logging in the terminal.
DEBUG_HTTP_LOGGING = True

SESSION_TABLE = "session_inputs"
PERSISTENT_TABLE = "persistent_inputs"


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Creates both tables.

    persistent_inputs keeps every input across restarts.
    session_inputs is cleared every time the server starts/restarts.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {PERSISTENT_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {SESSION_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # This makes the current session equivalent to a fresh server start.
    clear_session_inputs(cursor)

    conn.commit()
    conn.close()


def clear_session_inputs(cursor=None):
    """Clear only the current-session table."""
    own_connection = cursor is None

    if own_connection:
        conn = get_db_connection()
        cursor = conn.cursor()

    cursor.execute(f"DELETE FROM {SESSION_TABLE}")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name = ?", (SESSION_TABLE,))

    if own_connection:
        conn.commit()
        conn.close()


def get_inputs(table_name):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(f"SELECT id, text, created_at FROM {table_name} ORDER BY id ASC")
    rows = cursor.fetchall()

    conn.close()
    return [dict(row) for row in rows]


def get_session_inputs():
    return get_inputs(SESSION_TABLE)


def get_persistent_history():
    return get_inputs(PERSISTENT_TABLE)


def save_input(text):
    """Save one input to both the persistent history and the current session."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        f"INSERT INTO {PERSISTENT_TABLE} (text) VALUES (?)",
        (text,)
    )

    cursor.execute(
        f"INSERT INTO {SESSION_TABLE} (text) VALUES (?)",
        (text,)
    )

    conn.commit()
    conn.close()


def website_is_off_response():
    """Response used when the site has been turned off."""
    if request.path.startswith("/api/"):
        return jsonify({
            "status": "off",
            "message": "The website is currently turned off. No input is being accepted."
        }), 503

    return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Website Off</title>
            <style>
                body {
                    text-align: center;
                    font-family: Arial, sans-serif;
                }
            </style>
        </head>
        <body>
            <h1>Website is turned off</h1>
            <p>No input is currently being accepted.</p>
        </body>
        </html>
    """), 503


@app.before_request
def log_request_info():
    """Print the full incoming HTTP request to the terminal."""
    if not DEBUG_HTTP_LOGGING:
        return None

    print("\n--- HTTP REQUEST ---")
    print(f"Method: {request.method}")
    print(f"Path: {request.path}")
    print(f"Full URL: {request.url}")
    print(f"Endpoint: {request.endpoint}")
    print(f"Remote address: {request.remote_addr}")

    print("Headers:")
    for key, value in request.headers.items():
        print(f"  {key}: {value}")

    if request.args:
        print("Query parameters:")
        print(dict(request.args))

    # Cache the raw body so Flask can still parse form data / JSON afterwards.
    raw_body = request.get_data(as_text=True, cache=True)

    if request.form:
        print("Form data:")
        print(dict(request.form))

    if request.is_json:
        print("JSON body:")
        print(request.get_json(silent=True))

    if raw_body:
        print("Raw body:")
        print(raw_body)

    print("--- END REQUEST ---\n")
    return None


@app.before_request
def block_requests_when_website_is_off():
    """
    When the website is off, do not process anything except the endpoint
    that turns it back on.
    """
    if not website_enabled and request.endpoint != "turn_website_on":
        return website_is_off_response()

    return None


@app.after_request
def log_response_info(response):
    """Print the full outgoing HTTP response to the terminal."""
    if not DEBUG_HTTP_LOGGING:
        return response

    print("\n--- HTTP RESPONSE ---")
    print(f"Status: {response.status}")

    print("Headers:")
    for key, value in response.headers.items():
        print(f"  {key}: {value}")

    content_type = response.content_type or ""
    printable_content_types = ["text", "json", "html", "xml", "javascript"]

    if any(kind in content_type for kind in printable_content_types):
        try:
            body = response.get_data(as_text=True)
            print("Body:")
            print(body)
        except RuntimeError:
            print("Body: <streaming response; body not printed>")
    else:
        print(f"Body: <not printed for content type {content_type}>")

    print("--- END RESPONSE ---\n")
    return response


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        user_text = request.form.get("user_text", "").strip()

        if user_text:
            save_input(user_text)

        return redirect(url_for("index"))

    inputs = get_session_inputs()

    return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Input List</title>
            <style>
                body {
                    text-align: center;
                    font-family: Arial, sans-serif;
                }

                ul {
                    list-style-position: inside;
                    padding: 0;
                }
            </style>
        </head>
        <body>
            <h1>Submit Text</h1>

            <form method="POST">
                <input type="text" name="user_text" placeholder="Enter something" required>
                <button type="submit">Submit</button>
            </form>

            <ul>
                <li><strong>POST /api/session/reset</strong> - Reset the current session inputs.</li>
                <li><strong>POST /api/website/off</strong> - Turn the website off.</li>
                <li><strong>POST /api/website/on</strong> - Turn the website on.</li>
                <li><strong>GET /api/history</strong> - Retrieve the persistent input history.</li>
            </ul>

            <h2>Current Session Inputs</h2>
            <ul>
                {% for item in inputs %}
                    <li>{{ item.text|safe }}</li>
                {% endfor %}
            </ul>
        </body>
        </html>
    """, inputs=inputs)


@app.route("/api/session/reset", methods=["POST"])
def reset_current_session():
    """
    Reset the current session without deleting persistent history.
    This is equivalent to what happens to the session table on restart.
    """
    clear_session_inputs()
    return jsonify({
        "status": "ok",
        "message": "Current session has been reset. Persistent history was not deleted."
    })


@app.route("/api/website/off", methods=["POST"])
def turn_website_off():
    global website_enabled
    website_enabled = False
    return jsonify({
        "status": "ok",
        "message": "Website has been turned off."
    })


@app.route("/api/website/on", methods=["POST"])
def turn_website_on():
    global website_enabled
    website_enabled = True
    return jsonify({
        "status": "ok",
        "message": "Website has been turned on."
    })


@app.route("/api/history", methods=["GET"])
def get_whole_persistent_history():
    return jsonify({
        "history": get_persistent_history()
    })


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("--host", default="127.0.0.1")
	parser.add_argument("--port", type=int, default=5000)

	args = parser.parse_args()

	init_db()

	app.run(
		host=args.host,
		port=args.port,
		debug=True
	)
