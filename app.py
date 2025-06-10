from map_dashboard import app

if __name__ == "__main__":
    # Locally this will run on http://localhost:8050
   # app.run_server(host="0.0.0.0", port=8050, debug=False)
    app.run(host="0.0.0.0", port=8050, debug=False)
