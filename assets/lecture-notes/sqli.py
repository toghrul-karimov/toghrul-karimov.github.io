from flask import Flask, request, render_template_string
import sqlite3
import os
import argparse

app = Flask(__name__)
DB_FILE = "names.db"

INDEX_HTML = """
<!doctype html>
<html>
	<head>
		<meta charset="utf-8">
		<title>SQLi Demo</title>
		<style>
			body {
				font-family: sans-serif;
				height: 100vh;
				margin: 0;
				display: flex;
				justify-content: center;
				align-items: center;
				background-color: #f5f5f5;
			}

			.container {
				text-align: center;
			}

			input, button {
				font-size: 16px;
				padding: 10px;
				margin: 5px;
			}
		</style>
	</head>
	<body>
		<div class="container">
			<h1>Name Check</h1>

			<form method="post">
				<input type="text" name="name">
				<br>
				<button type="submit">Submit</button>
			</form>
		</div>
	</body>
</html>
"""

RESULT_HTML = """
<!doctype html>
<html>
	<head>
		<meta charset="utf-8">
		<title>Result</title>
		<style>
			body {
				font-family: sans-serif;
				height: 100vh;
				margin: 0;
				display: flex;
				justify-content: center;
				align-items: center;
				background-color: #f5f5f5;
			}

			.container {
				text-align: center;
			}

			.message {
				font-size: 32px;
				margin-bottom: 20px;
			}

			button {
				font-size: 16px;
				padding: 10px 20px;
			}
		</style>
	</head>
	<body>
		<div class="container">
			<div class="message">{{ message }}</div>

			<form action="/" method="get">
				<button type="submit">Go Back</button>
			</form>
		</div>
	</body>
</html>
"""

def lookup_name(name: str):
	conn = sqlite3.connect(DB_FILE)
	cur = conn.cursor()

	cur.execute(f"SELECT 1 FROM users WHERE name = '{name}'")

	row = cur.fetchone()

	conn.close()

	return row is not None


@app.route("/", methods=["GET", "POST"])
def index():
	if request.method == "POST":
		name = request.form.get("name", "")

		if lookup_name(name):
			message = "Welcome!"
		else:
			message = "Sorry, I don't know you!"

		return render_template_string(
			RESULT_HTML,
			message=message
		)

	return render_template_string(INDEX_HTML)


def init_db():
	first_time = not os.path.exists(DB_FILE)

	conn = sqlite3.connect(DB_FILE)
	cur = conn.cursor()

	cur.execute("""
		CREATE TABLE IF NOT EXISTS users (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			name TEXT NOT NULL UNIQUE
		)
	""")

	if first_time:
		cur.execute(
			"INSERT INTO users (name) VALUES ('Alice'), ('Bob'), ('Charlie')"
		)

	conn.commit()
	conn.close()


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
