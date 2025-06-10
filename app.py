import os
from map_dashboard import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 8050)), debug=False)
