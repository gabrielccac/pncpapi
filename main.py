from flask import Flask, jsonify
from seleniumbase import Driver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from time import sleep
import threading
import queue

app = Flask(__name__)

class BrowserManager:
    def __init__(self):
        self.driver = None
        self.lock = threading.Lock()
        
    def get_driver(self):
        with self.lock:
            if self.driver is None:
                self.driver = Driver(uc=True, headless=True)
            return self.driver
            
    def close_driver(self):
        with self.lock:
            if self.driver:
                self.driver.quit()
                self.driver = None

browser_manager = BrowserManager()

def generate_token():
    driver = browser_manager.get_driver()
    result_queue = queue.Queue()
    
    try:
        driver.get("https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/compras")
        sleep(5)
        
        js_function = """
        var done = arguments[0];
        
        (async function generateCaptchaToken() {
            try {
                let attempts = 0;
                while (typeof hcaptcha === 'undefined' && attempts < 10) {
                    await new Promise(resolve => setTimeout(resolve, 1000));
                    attempts++;
                }
                
                const element = document.querySelector('[data-hcaptcha-widget-id]');
                if (!element) {
                    done('');
                    return;
                }

                const captchaId = element.getAttribute('data-hcaptcha-widget-id');
                console.log('Captcha ID:', captchaId);

                if (typeof hcaptcha === 'undefined') {
                    done('');
                    return;
                }
                
                try {
                    const response = await hcaptcha.execute(captchaId, { async: true });
                    done(response);
                } catch (err) {
                    console.error('hCaptcha execution error:', err);
                    done('');
                }
            } catch (error) {
                console.error('Error generating captcha token:', error);
                done('');
            }
        })();
        """
        
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'iframe[data-hcaptcha-widget-id]')))
        
        token = driver.execute_async_script(js_function)
        return token if token else ""
        
    except Exception as e:
        print(f"Error generating token: {str(e)}")
        return ""

@app.route('/get-token', methods=['GET'])
def get_token():
    try:
        token = generate_token()
        if token:
            return jsonify({"success": True, "token": token})
        else:
            return jsonify({"success": False, "error": "Failed to generate token"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.errorhandler(Exception)
def handle_error(error):
    return jsonify({"success": False, "error": str(error)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)

# Cleanup on shutdown
import atexit

@atexit.register
def cleanup():
    browser_manager.close_driver()