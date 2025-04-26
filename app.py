import os
import pytesseract
from flask import Flask, request, render_template
from PIL import Image
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

            # OCR: Extract text from the uploaded image
            image = Image.open(filepath)
            extracted_text = pytesseract.image_to_string(image)

            # Send extracted text to OpenAI for emotional analysis
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an emotional intelligence analyst. Based on the input text, classify the emotional tone as Positive, Negative, Uncertain, or Neutral, and provide a brief explanation."},
                    {"role": "user", "content": f"Here is the text:\n\n'{extracted_text}'"}
                ]
            )
            analysis = response.choices[0].message.content

            return f"<h2>Analysis Result:</h2><p>{analysis}</p>"

    return render_template('index.html')

if __name__ == "__main__":
    app.run(debug=True)
