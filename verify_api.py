import requests
import time

def test_api():
    url = "http://127.0.0.1:8000/"
    api_status_url = "http://127.0.0.1:8000/api/status"
    
    print("Waiting for server to start...")
    for i in range(5):
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                print(f"Server is UP! Root response length: {len(r.text)}")
                
                # Check status endpoint
                rs = requests.get(api_status_url, timeout=2)
                print(f"Status API Response: {rs.json()}")
                return True
        except Exception as e:
            print(f"Attempt {i+1}/5 failed: {e}")
            time.sleep(1)
            
    print("Server failed to respond in time.")
    return False

if __name__ == "__main__":
    test_api()
