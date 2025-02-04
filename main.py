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
from time import sleep

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
        js_function = """
        var done = arguments[0];
        (async function() {
            try {
                const element = document.querySelector('[data-hcaptcha-widget-id]');
                if (!element) return done({error: 'Elemento não encontrado'});

                // Extrai o captchaId do atributo data-hcaptcha-widget-id
                const captchaId = element.getAttribute('data-hcaptcha-widget-id');
                if (!captchaId) return done({error: 'Captcha ID não encontrado'});

                // Cria uma promessa que rejeita após 30 segundos
                const timeoutPromise = new Promise((_, reject) => {
                    setTimeout(() => {
                        reject(new Error('Timeout: hCaptcha não respondeu em 30 segundos'));
                    }, 30000); // 30 segundos
                });

                // Executa o hCaptcha e compete com o timeout
                const hcaptchaPromise = hcaptcha.execute(captchaId, {async: true});

                // Usa Promise.race para definir o timeout
                const reponse = await Promise.race([hcaptchaPromise, timeoutPromise]);

                if (!reponse) return done({error: 'Erro ao executar hCaptcha'});

                done({token: reponse});
            } catch(error) {
                console.error('Erro:', error);
                done({error: error.message || 'Erro ao buscar captchaId'});
            }
        })();
        """

        try:
            # Executa o script para buscar o elemento
            result = driver.execute_async_script(js_function)

            # Captura o screenshot da página após a execução do hCaptcha
            sleep(3)  # Espera 3 segundos para garantir que a página esteja estável
            screenshot = driver.get_screenshot_as_png()
            screenshot_base64 = base64.b64encode(screenshot).decode('utf-8')

            # Verifica se houve erro no JavaScript
            if "error" in result:
                return {
                    "error": result["error"],
                    "screenshot": screenshot_base64  # Retorna o screenshot mesmo em caso de erro
                }

            return {
                "captcha": result["token"],
                "screenshot": screenshot_base64
            }

        except Exception as e:
            print("Erro na execução do script:", str(e))
            # Captura o screenshot mesmo em caso de exceção
            screenshot = driver.get_screenshot_as_png()
            screenshot_base64 = base64.b64encode(screenshot).decode('utf-8')
            return {
                "error": str(e),
                "screenshot": screenshot_base64
            }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)