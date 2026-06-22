import os
from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors

def test_vertex_auth():
    # Force load `.env` from the same directory as this script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.join(current_dir, '.env')
    load_dotenv()

    project_id = os.environ.get("PROJECT_ID")
    location = os.environ.get("LOCATION")

    print("=" * 50)
    print("      VERTEX AI AUTHENTICATION TEST")
    print("=" * 50)
    print(f"Loaded Project ID : {project_id}")
    print(f"Loaded Location   : {location}")
    print("-" * 50)

    if not project_id or not location:
        print("❌ ERROR: PROJECT_ID or LOCATION is missing from your .env file!")
        return

    try:
        print("Initializing Vertex AI client...")
        client = genai.Client(vertexai=True, project=project_id, location=location)
        
        print("Sending lightweight test prompt to gemini-2.5-flash...")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents='Hello Vertex AI! Reply with the word "Success oooh" if you can hear me and add some quotes and memes .',
        )
        
        print("-" * 50)
        print(f"🎉 RESPONSE FROM VERTEX AI: {response.text.strip()}")
        print("-" * 50)
        print("✅ Success! Your authentication, billing, and API settings are 100% correct.")

    except genai_errors.APIError as e:
        print("\n❌ GOOGLE API ERROR DETECTED:")
        print(f"Status Code: {e.code}")
        print(f"Message: {e.message}")
        print("\nPossible culprits:")
        if "403" in str(e.code):
            print("- The Vertex AI API might still be propagating (wait 2 minutes).")
            print("- Or your active gcloud account does not have Owner/Editor roles on this project.")
        elif "404" in str(e.code):
            print("- Check if the project ID or region string in your .env has a typo.")
            print("- Or the model name is restricted/unavailable in this region.")
            
    except Exception as e:
        print(f"\n❌ UNEXPECTED PYTHON ERROR: {e}")

if __name__ == "__main__":
    test_vertex_auth()