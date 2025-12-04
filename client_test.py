import requests

BASE_URL = "http://localhost:8000"

def test_chat():
    print("=== Testing /chat ===")
    resp = requests.post(
        f"{BASE_URL}/chat",
        json={"text": "Which Jubaili product is used for rice blast?"},
        timeout=30,
    )
    print(resp.status_code, resp.json())

def test_diagnose_image(image_path, crop_name=None):
    print("=== Testing /diagnose-simple ===")
    files = {"file": open(image_path, "rb")}
    data = {}
    if crop_name:
        data["crop_name"] = crop_name
    resp = requests.post(
        f"{BASE_URL}/diagnose-simple",
        files=files,
        data=data,
        timeout=60,
    )
    print(resp.status_code)
    print(resp.json())

if __name__ == "__main__":
    test_chat()
    # Replace with an actual local image path
    test_diagnose_image("/Users/ahdghazal/Desktop/sickcriop.jpg")
