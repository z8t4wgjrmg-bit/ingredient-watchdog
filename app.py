import os
import json
import re
import base64
from flask import Flask, render_template, request, jsonify
import anthropic

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
PRICES_FILE = 'prices.json'

def load_prices():
    if not os.path.exists(PRICES_FILE):
        return {}
    with open(PRICES_FILE, 'r') as f:
        return json.load(f)

def save_prices(prices):
    with open(PRICES_FILE, 'w') as f:
        json.dump(prices, f, indent=2)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    try:
        file = request.files['file']
        image_bytes = file.read()
        print("IMAGE SIZE:", len(image_bytes))
        image_data = base64.b64encode(image_bytes).decode('utf-8')
        previous_prices = load_prices()

        client = anthropic.Anthropic()

        prompt = """Look at this invoice image. Return ONLY pure JSON starting with { and ending with }. No text before or after. No markdown.

Format:
{"items":[{"name":"Tomatoes","current_price":4.50,"unit":"kg","previous_price":null,"status":"new","badge":"New item","price_info":"AED 4.50/kg"}],"summary":"6 new items found."}

Status: new=never seen, ok=same/cheaper, warn=up 1-5%, alert=up more than 5%
Previous prices: """ + json.dumps(previous_prices)

        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_data
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }]
        )

        print("STOP REASON:", message.stop_reason)
        print("CONTENT COUNT:", len(message.content))
        raw = message.content[0].text.strip()
        print("RAW:", raw[:300])

        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'^```\s*', '', raw)
        raw = re.sub(r'```$', '', raw).strip()
        raw = raw[raw.find('{'):raw.rfind('}')+1]

        result = json.loads(raw)

        for item in result.get('items', []):
            name = item['name'].lower().strip()
            previous_prices[name] = {
                "price": item['current_price'],
                "unit": item.get('unit', '')
            }
        save_prices(previous_prices)
        return jsonify(result)

    except Exception as e:
        print("ERROR:", str(e))
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "items": [], "summary": "Error: " + str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)