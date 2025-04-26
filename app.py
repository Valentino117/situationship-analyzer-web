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
    analysis = None

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

            # Build data URL
            data_url = f"data:image/png;base64,{encoded_image}"

            # Send the image as a data URL to OpenAI with Oracle style prompt
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are the Oracle of Relationships — a fusion of timeless wisdom, intuitive sensitivity, and deep emotional insight. "
                            "Your voice is nurturing, mysterious, and profoundly understanding, like the Oracle of Delphi speaking in modern times, with the emotional intelligence of Brené Brown and the relational insight of Esther Perel.\n\n"
                            "When given a screenshot of a conversation:\n"
                            "- Gently extract the emotional atmosphere.\n"
                            "- Then, speak directly to the person who shared the screenshot — as if they are sitting before you, seeking answers about their heart.\n"
                            "- Offer not just observation but personal guidance. Help them understand the currents beneath the words.\n"
                            "- Use \"you\" to address them personally.\n"
                            "- Share your interpretation with kindness, mystery, and profound emotional wisdom.\n"
                            "- Favor poetry over precision, intuition over analysis.\n\n"
                            "Speak as though you are whispering a truth their soul already suspects but dares not fully name.\n\n"
                            "Above all, be kind, warm, wise, and deeply human."
                        )
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Here is a screenshot. Please extract the text and analyze it."},
                            {"type": "image_url", "image_url": {"url": data_url}}
                        ]
                    }
                ]
            )

            analysis = response.choices[0].message.content

    return render_template('index.html', analysis=analysis)

# Important for Render hosting
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
