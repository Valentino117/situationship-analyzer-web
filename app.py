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
        
        files = request.files.getlist('file')
        if not files or files[0].filename == '':
            return 'No files selected'

        image_urls = []
        for file in files:
            filepath = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(filepath)

            with open(filepath, "rb") as image_file:
                image_bytes = image_file.read()
            encoded_image = base64.b64encode(image_bytes).decode('utf-8')
            data_url = f"data:image/png;base64,{encoded_image}"
            image_urls.append({"type": "image_url", "image_url": {"url": data_url}})

        # Send all screenshots in one message to GPT-4o
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are the Oracle of Relationships — a fusion of timeless wisdom, intuitive sensitivity, and deep emotional insight. "
                        "Your voice is nurturing, mysterious, and profoundly understanding, like the Oracle of Delphi speaking in modern times, with the emotional intelligence of Brené Brown and the relational insight of Esther Perel.\n\n"
                        "When given screenshots of a conversation:\n"
                        "- Gently extract the emotional atmosphere.\n"
                        "- Then, speak directly to the person who shared the images — as if they are sitting before you, seeking answers about their heart.\n"
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
                        {"type": "text", "text": "Here are screenshots from my situationship. Please help me understand what's going on emotionally."}
                    ] + image_urls
                }
            ]
        )

        analysis = response.choices[0].message.content

    return render_template('index.html', analysis=analysis)

# Important for Render hosting
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
