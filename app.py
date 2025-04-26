import os
import base64
from flask import Flask, request, render_template
from openai import OpenAI

# Set up OpenAI client
client = OpenAI()

# Set up Flask app
app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return 'No file part'
        file = request.files['file']
        if file.filename == '':
            return 'No selected file'
        if file:
            filepath = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(filepath)

            # Read and encode the image bytes
            with open(filepath, "rb") as image_file:
                image_bytes = image_file.read()
            encoded_image = base64.b64encode(image_bytes).decode('utf-8')

            # Send image to OpenAI GPT-4o Vision
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an emotional intelligence analyst specializing in relationships and subtle communication patterns. "
                            "First, extract the text from the uploaded image carefully. "
                            "Then, analyze the emotional tone conveyed by the sender — not just in simple terms like Positive or Negative, "
                            "but in a more nuanced and conscientious way. Consider emotions such as hope, anxiety, confusion, longing, "
                            "avoidance, excitement, sadness, guilt, or uncertainty. "
                            "Write a short, thoughtful paragraph explaining what emotional dynamics might be happening, based on the content and tone of the message."
                        )
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Here is a screenshot. Please extract the text and analyze it."},
                            {"type": "image", "image": {"base64": encoded_image}}
                        ]
                    }
                ]
            )

            analysis = response.choices[0].message.content

            return f"<h2>Analysis Result:</h2><p>{analysis}</p>"

    return render_template('index.html')

# Important for Render hosting
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
