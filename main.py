import os

from website import create_app

os.environ["BAYBE_TELEMETRY_ENABLED"] = "false"

app = create_app()

if __name__ == "__main__":
    app.run(host="localhost", port=8054, debug=True)
