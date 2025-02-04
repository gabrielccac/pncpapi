import requests

def get_captcha_token():
    try:
        # Make GET request to the API endpoint
        response = requests.get('http://localhost:8000/get-token')
        
        # Check if request was successful
        response.raise_for_status()
        
        # Parse the JSON response
        data = response.json()
        
        # Return the token
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {str(e)}")
        return None
    except KeyError as e:
        print(f"Error parsing response: {str(e)}")
        return None

# Example usage
if __name__ == "__main__":
    token = get_captcha_token()
    if token:
        print(f"Successfully retrieved token: {token}")
    else:
        print("Failed to get token")