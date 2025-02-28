- [x] Phase 1.
    - [x] Create a python script to extract Json data from excel (file location: /assets/combined_data.xlsx) file: combined_data.json.

- [X] Phase 1 course corrections (edit the a python script extract_excel_to_json.py to do the following)
    - [X] Make the limit optional.
    - [X] instead of making a single file as "combined_data.json" let's make multiple files and an index file to keep track of which file is completed | Inprogress | Not started.

- [x] Phase 2 (Create a python script to do the following)
    - [x] Go to all download_url on at a time. (Make sure add some buffer time between each request to avoid getting blocked by the server.)
    - [x] Get the capcha image (html id = "capt").
    - [x] Save the image in /assets/images folder. (Temporarily save it as {id}.png)
    - [x] send it mistral AI api to get the values. (implementation for this is given below)
        ```python
        import base64
            import requests
            import os
            from mistralai import Mistral

            def encode_image(image_path):
                """Encode the image to base64."""
                try:
                    with open(image_path, "rb") as image_file:
                        return base64.b64encode(image_file.read()).decode('utf-8')
                except FileNotFoundError:
                    print(f"Error: The file {image_path} was not found.")
                    return None
                except Exception as e:  # Added general exception handling
                    print(f"Error: {e}")
                    return None

            # Path to your image
            image_path = "path_to_your_image.jpg"

            # Getting the base64 string
            base64_image = encode_image(image_path)

            # Retrieve the API key from environment variables
            api_key = os.environ["MISTRAL_API_KEY"]

            # Specify model
            model = "pixtral-12b-2409"

            # Initialize the Mistral client
            client = Mistral(api_key=api_key)

            # Define the messages for the chat
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "What's in this image?"
                        },
                        {
                            "type": "image_url",
                            "image_url": f"data:image/jpeg;base64,{base64_image}" 
                        }
                    ]
                }
            ]

            # Get the chat response
            chat_response = client.chat.complete(
                model=model,
                messages=messages
            )

            # Print the content of the response
            print(chat_response.choices[0].message.content)
        ```
    - [x] Fill the value in the form (html id for the input field = "t1")
    - [x] Submit it (html id for the submit button = "show_corp").
    - [x] after submitting the form, it will download the pdf file.
    - [x] Save the pdf file in /assets/pdfs folder.

- [x] Phase 2 course corrections (Create a new python script phase2-corrections.py to do the following, refer to phase2.py for reference)
    - [x] Now the data is being handled batch by batch so, let's change the script to accoidate it. (refer to extract_excel_to_json.py for reference)
    - [x] The file structure is assets/batches (inside this there are multiple files) and assets/batch_index.json (index file to keep track of which file is completed | Inprogress | Not started.) 
    - [x] Add a variable to skip first 2000 entries in the combined_data.json file. (keep it optional and This number may change in the future so keep it as variable)
    - [x] Create multiple batch json files for the data each file will contain 500 entries. (This number may change in the future so keep it as variable)
    - [x] It need to store the downladed file based on it's data example structure eg: "assets/pdfs/{district}/{block_name}/{village_name}/"
    - [x] It need to also change the name of file based on it's data eg: {name}.pdf (make sure to add - in between the words instead of space and keep the file format as it is)
    

- [X] Phase 2 gemini. (Create a python script "phase2-gemini.py" to do the following, refer to phase2-corrections.py for reference)
    - [X] let's implemet the gemini instead of mistral AI.
    - [X] here is the gemini implementation
     ```python
        from google import genai
        from google.genai import types

        import requests

        image_path = "https://goo.gle/instrument-img"
        image = requests.get(image_path)

        client = genai.Client(api_key="GEMINI_API_KEY")
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=["What is this image?",
                    types.Part.from_bytes(data=image.content, mime_type="image/png")])

        print(response.text)
    ```
    - [X] update requirements.txt


- [ ] Phase 3 (Create a python script to do the following)
    - [ ] Extract png image from pdf file.

- [ ]Phase 4 (Create a python script to do the following)
    - [ ] Send it to google AI api to the information and store it in a json format.


!! inportant !!
- Make sure add some buffer time between each request to avoid getting blocked by the server.
- Add a field in every entry of combined_data.json to keep track of the status of the entry. (whether it is processed or not).