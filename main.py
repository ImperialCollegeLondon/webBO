from website import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="localhost", port=8081, debug=True)