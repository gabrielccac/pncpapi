from fastapi import FastAPI
from seleniumbase import Driver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from contextlib import asynccontextmanager
import threading
import time
import base64
from io import BytesIO
import undetected_chromedriver as uc  # Importe o undetected_chromedriver

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

    # Inicializa o driver com as opções configuradas
    driver = Driver(uc=True, headless=True)
    
    driver.set_window_size(1200, 600)
    driver.get("https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/compras")

    # Espera explícita pelo carregamento do hCaptcha com timeout maior
    try:
        wait = WebDriverWait(driver, 30)  # Aumentado para 30 segundos
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'iframe[data-hcaptcha-widget-id]')))
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

        # Código JavaScript simplificado para retornar o elemento do hCaptcha
        js_function = js_function = """
        var done = arguments[0];
        (async function() {
            try {
                const element = document.querySelector('[data-hcaptcha-widget-id]');
                if (!element) return done('Elemento não encontrado');
                
                // Extrai o captchaId do atributo data-hcaptcha-widget-id
                const captchaId = element.getAttribute('data-hcaptcha-widget-id');
                if (!captchaId) return done('Captcha ID não encontrado');
                
                done(captchaId);


            } catch(error) {
                console.error('Erro:', error);
                done('Erro ao buscar captchaId');
            }
        })();
        """

        try:
            # Executa o script para buscar o elemento
            token = driver.execute_async_script(js_function)
            return {"captcha": token}

        except Exception as e:
            print("Erro na execução do script:", str(e))
            return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)