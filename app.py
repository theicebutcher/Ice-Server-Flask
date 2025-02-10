import os
import base64
from flask import Flask, render_template, request, jsonify
import openai
from dotenv import load_dotenv
import json

# Load FAQ data from a JSON file
# Load FAQ data from a JSON file with UTF-8 encoding


with open('faq.json', 'r', encoding='utf-8') as file:
    faq_data = json.load(file)

# # Create the custom prompt
# custom_prompt = f"""
# You are an AI assistant for an ice sculpture company named "Ice Butcher".
# This is the information and question answers you need to assist users based on this data:
# if user mentions order then show the order link otherwise dont show the order link. only show the required links, if all links are asked then skip the order link, only show order when asked explicitly.
# {json.dumps(faq_data, indent=2)}



# """




app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "static/uploads"

# Load environment variables from .env file
load_dotenv()

# Get the API key from the environment variable
api_key = os.getenv("OPENAI_API_KEY")

client = openai.OpenAI(api_key=api_key)

# Function to encode image to base64
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

# Load Images data
import json

def load_faq_data():
    with open('images2.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
    
    # Extract the list from the dictionary
    if isinstance(data, dict) and "standardSculptures" in data:
        return data["standardSculptures"]
    
    raise ValueError("Unexpected JSON structure. Expected 'standardSculptures' key.")

from rapidfuzz import process, fuzz


def find_top_matches(user_input, data):
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError("Data should be a list of dictionaries.")

    # Extract names from data and store a reference dictionary
    choices = {item.get("name", "").lower(): item for item in data if "name" in item}

    # Use process.extract to get top 100 matches with optimized scoring
    matches = process.extract(user_input.lower(), choices.keys(), scorer=fuzz.QRatio, limit=100)

    # Return sorted list based on similarity score
    sorted_matches = [choices[match[0]] for match in matches]

    return sorted_matches  # Returns top 100 matches


@app.route("/chatbot", methods=["POST"])
def chatbot():
    user_input = request.form.get("user_input", "").strip().lower()
    uploaded_file = request.files.get("image")

    try:
                # Load image data and find top matches
        image_data = load_faq_data()
        sorted_matches = find_top_matches(user_input, image_data)[:100]  # Get only the top 10 matches
        print(json.dumps(sorted_matches, indent=2, ensure_ascii=False))

        # Create the custom prompt with matched results
        custom_prompt = f"""
        You are an AI assistant for an ice sculpture company named "Ice Butcher".
        This is the information and question answers you need to assist users based on this data:
        If user mentions order then show the order link, otherwise don't show the order link.
        Only show the required links; if all links are asked, then skip the order link, Only show the order link when asked explicitly, otherwise don't.

        FAQ Data:
        {json.dumps(faq_data, indent=2, ensure_ascii=False)}

        Standard Sculptures (images urls of the sculptures, use these when user asks for a sculpture image):
        {json.dumps(sorted_matches, indent=2, ensure_ascii=False)}
        """


        # If there's an uploaded file (image)
        if uploaded_file:
            image_path = "uploaded_image.jpg"
            uploaded_file.save(image_path)
            
            instruction_text = """
            Describe the geometrical features of this image for an ice engraving.
            The engraving should be a 2D carving on a 5-inch thick ice block.
            The ice should have a natural texture with light refraction.
            """

            base64_image = encode_image(image_path)
            completion = client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": instruction_text},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }]
            )

            gpt_response = completion.choices[0].message.content
            if "https://theicebutcher.com/request/" in gpt_response:
                return jsonify({"image_url": "img.PNG"}) 

            dalle_prompt = f"""
            Create an image of an ice engraving.
            The engraving should be a 2D carving on a 5-inch thick ice block.
            The ice should have a natural texture with light refraction.
            {gpt_response}
            """
            if "https://theicebutcher.com/request/" in gpt_response:
                return jsonify({"image_url": "img.PNG"}) 

        # If the user input contains "generate", pass the prompt to DALL·E
        elif user_input.startswith("generate"):
            dalle_prompt = f"""
            Create images of ice Engraving.
            Every image should emphasize natural ice .
            Avoid adding too much details, keep it as simple as possible.
            
            {user_input}
            IMPORTANT: - The Ice Engraving primarily focuses on detailed carvings on the flat peace of ice block with 5 inches thick ice and around 4 feet tall and 5 feet wide.

            The ice engraving should appear carved from genuine translucent ice, with a natural, slightly imperfect finish.
            Place the engraving on a wooden table with a black background for contrast.
            Avoid intricate patterns, sharp edges, or overly fine details, it should be very basic as possible.
            Focus on natural ice textures, slight frost buildup, and subtle light refraction.
            The image should resemble a high-quality photograph taken with a professional DSLR camera, capturing the essence of an authentic, handcrafted ice engraving.
            The final image will only include the ice engraved sculpture , no human should be present in the image.
            

      
            """
        
        # Handle other chatbot input
        else:
            prompt_with_custom = f"{custom_prompt}\n{user_input}"
            completion = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt_with_custom}]
            )
            gpt_response = completion.choices[0].message.content
            return jsonify({"response": gpt_response})




        # Generate image with DALL-E 3
        response = client.images.generate(
            model="dall-e-3",
            prompt=dalle_prompt,
            size="1024x1024",
            quality="hd",
            n=1,
        )

        generated_image_url = response.data[0].url
        return jsonify({"response": "Here is your ice Sculpture:\n", "image_url": generated_image_url})

    except Exception as e:
        return jsonify({"response": f"Error: {str(e)}"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
