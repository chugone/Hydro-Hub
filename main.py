import os
from flask import Flask

# This initializes the web app
app = Flask(__name__)

# This tells the app what to show when someone visits the webpage
@app.route('/')
def home():
    # --- PUT YOUR SCRIPT LOGIC HERE ---
    message = "Your script successfully ran!"
    # ----------------------------------
    
    return f"<h1>Hello!</h1><p>{message}</p>"

# This starts the server on the correct port
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)