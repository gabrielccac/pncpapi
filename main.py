from fastapi import FastAPI, HTTPException
from seleniumbase import Driver
from selenium.webdriver.support.ui import WebDriverWait
from contextlib import asynccontextmanager
import threading
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor

class CaptchaManager:
    def __init__(self):
        self.driver = None
        self.lock = threading.Lock()
        self.last_used = None
        self.error_count = 0
        self.max_errors = 3
        self.last_error_time = 0
        self.error_cooldown = 60

    def initialize_driver(self):
        try:
            if time.time() - self.last_error_time < self.error_cooldown:
                raise HTTPException(status_code=503, detail="Service cooling down")

            self.driver = Driver(
                uc=True,
                headless=True,
                chromium_arg=[
                    "--no-sandbox",
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                    "--disable-features=NetworkService",
                    "--window-size=1920x1080",
                ]
            )
            
            self.driver.set_page_load_timeout(30)
            print("Carregando página...")
            self.driver.get("https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/landing?destino=acompanhamento-compra&compra=15695605900832024")

            print("Aguardando hCaptcha...")
            WebDriverWait(self.driver, 20).until(lambda d: d.execute_script(
                "return typeof hcaptcha !== 'undefined' && document.querySelector('[data-hcaptcha-widget-id]') !== null"
            ))
            time.sleep(2)
            return True

        except Exception as e:
            print(f"Erro na inicialização: {str(e)}")
            self._handle_error()
            return False

    def _handle_error(self):
        self.error_count += 1
        self.last_error_time = time.time()
        
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

        if self.error_count >= self.max_errors:
            time.sleep(5)
            self.error_count = 0

    async def get_token(self):
        with self.lock:
            try:
                if not self.driver:
                    if not self.initialize_driver():
                        return ""

                self.last_used = time.time()

                js_code = """
                return new Promise((resolve) => {
                    (async function() {
                        try {
                            await new Promise(r => setTimeout(r, 1000));
                            const element = document.querySelector('[data-hcaptcha-widget-id]');
                            if (!element) return resolve('');
                            
                            const captchaId = element.getAttribute('data-hcaptcha-widget-id');
                            const response = await hcaptcha.execute(captchaId, {async: true});
                            resolve(response);
                        } catch(error) {
                            console.error('Erro:', error);
                            resolve('');
                        }
                    })();
                });
                """

                loop = asyncio.get_event_loop()
                with ThreadPoolExecutor() as executor:
                    token = await loop.run_in_executor(
                        executor,
                        lambda: WebDriverWait(self.driver, 25).until(
                            lambda d: d.execute_script(js_code)
                        )
                    )

                if token:
                    self.error_count = 0
                    await self._reset_captcha()
                return token or ""

            except Exception as e:
                print(f"Erro na geração do token: {str(e)}")
                self._handle_error()
                return ""

    async def _reset_captcha(self):
        try:
            self.driver.execute_script("""
                const element = document.querySelector('[data-hcaptcha-widget-id]');
                if (element && hcaptcha) {
                    hcaptcha.reset(element.getAttribute('data-hcaptcha-widget-id'));
                }
            """)
        except:
            pass

captcha_manager = CaptchaManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    if captcha_manager.driver:
        try:
            captcha_manager.driver.quit()
        except:
            pass

app = FastAPI(lifespan=lifespan)

@app.get("/get-token")
async def get_captcha_token():
    token = await captcha_manager.get_token()
    return {"token": token}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)