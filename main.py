from fastapi import FastAPI
from seleniumbase import Driver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from contextlib import asynccontextmanager
import threading
import time

# Variáveis globais para gerenciar o driver, lock e último uso
driver = None
driver_lock = threading.Lock()
last_used_time = None
TIMEOUT = 300  # 5 minutos de inatividade

@asynccontextmanager
async def lifespan(app: FastAPI):
    global driver, last_used_time
    driver = None
    last_used_time = time.time()
    yield
    # Encerra o driver no shutdown
    if driver:
        driver.quit()

app = FastAPI(lifespan=lifespan)

def initialize_driver():
    global driver, last_used_time
    driver = Driver(uc=True, headless=True)
    driver.get("https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/landing?destino=acompanhamento-compra&compra=15695605900832024")

    # Espera explícita pelo carregamento do hCaptcha
    try:
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, 'iframe[data-hcaptcha-widget-id]')
        ))
    except Exception as e:
        print("Erro na inicialização:", str(e))
        driver.quit()
        driver = None

def close_driver_if_inactive():
    global driver, last_used_time
    if driver and (time.time() - last_used_time) > TIMEOUT:
        print("Fechando navegador por inatividade...")
        driver.quit()
        driver = None

@app.get("/get-token")
async def get_captcha_token():
    global driver, driver_lock, last_used_time

    with driver_lock:
        # Verifica se o navegador deve ser fechado por inatividade
        close_driver_if_inactive()

        # Se o navegador não estiver aberto, inicializa um novo
        if not driver:
            print("Inicializando novo navegador...")
            initialize_driver()

        # Atualiza o tempo da última requisição
        last_used_time = time.time()

        js_function = """
        var done = arguments[0];
        (async function() {
            try {
                const element = document.querySelector('[data-hcaptcha-widget-id]');
                if (!element) return done('');
                
                const captchaId = element.getAttribute('data-hcaptcha-widget-id');
                const response = await hcaptcha.execute(captchaId, {async: true});
                done(response);
            } catch(error) {
                console.error('Erro:', error);
                done('');
            }
        })();
        """

        try:
            # Executa o script para gerar o token
            token = driver.execute_async_script(js_function)

            # Reseta o captcha para próxima requisição
            driver.execute_script("""
                const element = document.querySelector('[data-hcaptcha-widget-id]');
                if (element && hcaptcha) {
                    hcaptcha.reset(element.getAttribute('data-hcaptcha-widget-id'));
                }
            """)

            return {"token": token or ""}

        except Exception as e:
            print("Erro na geração do token:", str(e))
            return {"token": ""}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)